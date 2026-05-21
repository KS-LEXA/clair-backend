import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, quote
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session
import httpx
from app.core.config import settings
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.models.user import User
from app.models.social_account import SocialAccount
from app.models.password_reset import PasswordResetToken
from app.models.email_verification import EmailVerification
from app.integrations.email_client import send_email


PROFILE_IMAGE_SUBDIR = "profile_images"


def profile_image_url(user: User) -> Optional[str]:
    """DB의 상대 경로를 backend_base_url과 조합한 절대 URL로 변환. 없으면 None."""
    if not user.profile_image_path:
        return None
    return f"{settings.backend_base_url.rstrip('/')}/{user.profile_image_path.lstrip('/')}"


def signup(email: str, nickname: str, password: str, db: Session, marketing_agreed: bool = False) -> User:
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 가입된 이메일입니다.")

    # 가입 전 이메일 인증 통과 여부 확인 — verified 레코드는 가입 시점에 1회용으로 소비.
    verification = db.query(EmailVerification).filter(EmailVerification.email == email).first()
    if not verification or verification.verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이메일 인증이 필요합니다. 인증 코드를 먼저 확인해주세요.",
        )

    user = User(
        email=email,
        nickname=nickname.strip(),
        password_hash=hash_password(password),
        marketing_agreed=marketing_agreed,
        email_verified_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.delete(verification)  # 인증 레코드는 가입 시 소비
    db.commit()
    db.refresh(user)
    return user


def login(email: str, password: str, db: Session) -> dict:
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
    return {
        "access_token": create_access_token(user.id, user.email),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
        "user": {"id": user.id, "email": user.email, "nickname": user.nickname},
    }


def refresh_access_token(refresh_token: str, db: Session) -> dict:
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh Token이 아닙니다.")
    user = db.query(User).filter(User.id == int(payload.get("sub"))).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="존재하지 않는 사용자입니다.")
    return {"access_token": create_access_token(user.id, user.email), "token_type": "bearer", "expires_in": settings.access_token_expire_minutes * 60}


def update_nickname(user: User, new_nickname: str, db: Session) -> User:
    user.nickname = new_nickname.strip()
    db.commit()
    db.refresh(user)
    return user


async def update_profile_image(user: User, file: UploadFile, db: Session) -> User:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="파일명이 없습니다.")
    ext = Path(file.filename).suffix.lower()
    if ext not in settings.profile_image_allowed_extensions_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"지원하지 않는 이미지 형식입니다: {ext} (허용: {settings.profile_image_allowed_extensions})",
        )

    profile_dir = Path(settings.upload_dir) / PROFILE_IMAGE_SUBDIR
    profile_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{user.id}_{uuid.uuid4().hex}{ext}"
    file_path = profile_dir / stored_filename

    size = 0
    try:
        with open(file_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.profile_image_max_size_bytes:
                    f.close()
                    os.remove(file_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"이미지 크기가 {settings.profile_image_max_size_mb}MB를 초과합니다.",
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        if file_path.exists():
            os.remove(file_path)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"파일 저장 중 오류: {e}")

    old_relative = user.profile_image_path
    user.profile_image_path = f"{PROFILE_IMAGE_SUBDIR}/{stored_filename}"
    db.commit()
    db.refresh(user)

    if old_relative:
        old_path = Path(settings.upload_dir) / old_relative
        try:
            if old_path.is_file():
                old_path.unlink()
        except OSError:
            pass

    return user


def change_password(user: User, current_password: str, new_password: str, db: Session) -> None:
    if not user.password_hash:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="소셜 로그인 계정은 비밀번호를 변경할 수 없습니다.")
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="현재 비밀번호가 올바르지 않습니다.")
    if current_password == new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="새 비밀번호가 현재 비밀번호와 동일합니다.")
    user.password_hash = hash_password(new_password)
    db.commit()


# ── 비밀번호 재설정 (이메일 링크 방식) ────────────────────────────────────────

def _hash_token(raw_token: str) -> str:
    """토큰은 항상 SHA-256 해시 형태로 DB에 저장 — DB 유출 시 raw 토큰 노출 방지."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


async def request_password_reset(email: str, db: Session) -> None:
    """
    이메일로 재설정 링크 발송.
    보안상 사용자 존재 여부는 응답으로 노출하지 않음 — 호출자는 항상 동일한 응답.
    소셜 전용 계정도 조용히 무시 (메일에서 "소셜 로그인 사용해주세요" 같은 정보 노출 X).
    """
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.password_hash:
        return  # 조용히 무시

    # 충분히 긴 URL-safe 토큰 — raw는 메일에만, DB엔 해시만
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_token_expire_minutes)

    db.add(PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    db.commit()

    reset_url = f"{settings.frontend_base_url.rstrip('/')}{settings.password_reset_path}?token={quote(raw_token)}"
    await send_email(
        to=user.email,
        subject="[CLAIR] 비밀번호 재설정 안내",
        template="password_reset.html",
        context={
            "nickname": user.nickname,
            "reset_url": reset_url,
            "expire_minutes": settings.password_reset_token_expire_minutes,
        },
    )


def _find_valid_token(raw_token: str, db: Session) -> PasswordResetToken:
    token_hash = _hash_token(raw_token)
    record = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="유효하지 않은 토큰입니다.")
    if record.used_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="이미 사용된 토큰입니다.")

    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="만료된 토큰입니다. 비밀번호 재설정을 다시 요청해주세요.")

    return record


def verify_reset_token(raw_token: str, db: Session) -> User:
    """프론트엔드가 재설정 페이지 진입 시 토큰 유효성 사전 검증용."""
    record = _find_valid_token(raw_token, db)
    return record.user


def confirm_password_reset(raw_token: str, new_password: str, db: Session) -> None:
    """토큰 검증 + 비밀번호 변경 + 토큰 1회 사용 처리."""
    record = _find_valid_token(raw_token, db)
    user = record.user
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="사용자를 찾을 수 없습니다.")

    user.password_hash = hash_password(new_password)
    record.used_at = datetime.now(timezone.utc)
    db.commit()


# ── 회원가입 이메일 인증 (가입 전 6자리 코드 확인) ─────────────────────────────

def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _generate_code() -> str:
    """6자리 숫자 코드 — secrets로 균등 분포."""
    return f"{secrets.randbelow(1_000_000):06d}"


async def request_email_verification(email: str, db: Session) -> None:
    """
    이메일로 6자리 인증 코드 발송.
    이메일당 활성 레코드 1개 — 재요청 시 기존 레코드의 코드/만료/시도횟수를 새로 채움.
    이미 가입된 이메일이면 정보 노출 회피 위해 그대로 진행 (가입은 signup 단계에서 막힘).
    """
    code = _generate_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.email_verification_code_expire_minutes)

    record = db.query(EmailVerification).filter(EmailVerification.email == email).first()
    if record:
        record.code_hash = _hash_code(code)
        record.expires_at = expires_at
        record.attempt_count = 0
        record.verified_at = None
    else:
        record = EmailVerification(email=email, code_hash=_hash_code(code), expires_at=expires_at)
        db.add(record)
    db.commit()

    await send_email(
        to=email,
        subject="[CLAIR] 이메일 인증 코드",
        template="email_verification.html",
        context={
            "code": code,
            "expire_minutes": settings.email_verification_code_expire_minutes,
        },
    )


def confirm_email_verification(email: str, code: str, db: Session) -> None:
    """
    코드 검증 → 성공 시 verified_at 채움. 실패 누적 5회 시 코드 무효.
    한 트랜잭션 내에서 attempt_count도 함께 증가시켜야 무차별 대입을 막을 수 있음.
    """
    record = db.query(EmailVerification).filter(EmailVerification.email == email).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="인증 요청 내역이 없습니다. 코드를 다시 요청해주세요.",
        )

    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="만료된 코드입니다. 인증 코드를 다시 요청해주세요.",
        )

    if record.attempt_count >= settings.email_verification_max_attempts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="시도 횟수를 초과했습니다. 인증 코드를 다시 요청해주세요.",
        )

    if record.code_hash != _hash_code(code):
        record.attempt_count += 1
        db.commit()
        remaining = settings.email_verification_max_attempts - record.attempt_count
        if remaining <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="시도 횟수를 초과했습니다. 인증 코드를 다시 요청해주세요.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"인증 코드가 올바르지 않습니다. (남은 시도 {remaining}회)",
        )

    record.verified_at = datetime.now(timezone.utc)
    db.commit()


# ── 공통 소셜 로그인 처리 ──────────────────────────────────────────────────────

def _social_login(provider: str, provider_id: str, email: str, nickname: str, db: Session) -> dict:
    """소셜 계정으로 유저 찾기 → 없으면 생성, JWT 발급. 소셜 유저는 IdP 신뢰로 자동 verified."""
    social = (
        db.query(SocialAccount)
        .filter(SocialAccount.provider == provider, SocialAccount.provider_id == provider_id)
        .first()
    )

    is_new_user = False
    now = datetime.now(timezone.utc)

    if social:
        user = social.user
        # 기존 이메일 가입자가 같은 이메일로 소셜 연결한 케이스: 아직 미인증이면 이번에 채움.
        if user.email_verified_at is None:
            user.email_verified_at = now
    else:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(email=email, nickname=nickname[:20], password_hash=None, email_verified_at=now)
            db.add(user)
            db.flush()  # user.id 확보
            is_new_user = True
        elif user.email_verified_at is None:
            user.email_verified_at = now

        social = SocialAccount(user_id=user.id, provider=provider, provider_id=str(provider_id))
        db.add(social)
        db.commit()
        db.refresh(user)

    return {
        "access_token": create_access_token(user.id, user.email),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
        "user": {"id": user.id, "email": user.email, "nickname": user.nickname},
        "is_new_user": is_new_user,
    }


# ── Google ────────────────────────────────────────────────────────────────────

def get_google_auth_url() -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def google_login(code: str, db: Session) -> dict:
    token_res = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    if token_res.status_code != 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="구글 인증에 실패했습니다.")

    userinfo_res = httpx.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {token_res.json().get('access_token')}"},
    )
    if userinfo_res.status_code != 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="구글 사용자 정보를 가져오지 못했습니다.")

    info = userinfo_res.json()
    return _social_login(
        provider="google",
        provider_id=info["id"],
        email=info["email"],
        nickname=info.get("name") or info["email"].split("@")[0],
        db=db,
    )


# ── Naver ─────────────────────────────────────────────────────────────────────

def get_naver_auth_url() -> str:
    params = {
        "client_id": settings.naver_client_id,
        "redirect_uri": settings.naver_redirect_uri,
        "response_type": "code",
        "state": secrets.token_urlsafe(16),
    }
    return f"https://nid.naver.com/oauth2.0/authorize?{urlencode(params)}"


def naver_login(code: str, state: str, db: Session) -> dict:
    token_res = httpx.post(
        "https://nid.naver.com/oauth2.0/token",
        params={
            "grant_type": "authorization_code",
            "client_id": settings.naver_client_id,
            "client_secret": settings.naver_client_secret,
            "code": code,
            "state": state,
        },
    )
    if token_res.status_code != 200 or "access_token" not in token_res.json():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="네이버 인증에 실패했습니다.")

    userinfo_res = httpx.get(
        "https://openapi.naver.com/v1/nid/me",
        headers={"Authorization": f"Bearer {token_res.json()['access_token']}"},
    )
    if userinfo_res.status_code != 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="네이버 사용자 정보를 가져오지 못했습니다.")

    profile = userinfo_res.json().get("response", {})
    email = profile.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="네이버 계정에 이메일 정보가 없습니다.")

    return _social_login(
        provider="naver",
        provider_id=profile["id"],
        email=email,
        nickname=profile.get("nickname") or profile.get("name") or email.split("@")[0],
        db=db,
    )


# ── Kakao ─────────────────────────────────────────────────────────────────────

def get_kakao_auth_url() -> str:
    params = {
        "client_id": settings.kakao_client_id,
        "redirect_uri": settings.kakao_redirect_uri,
        "response_type": "code",
    }
    return f"https://kauth.kakao.com/oauth/authorize?{urlencode(params)}"


def kakao_login(code: str, db: Session) -> dict:
    token_data = {
        "grant_type": "authorization_code",
        "client_id": settings.kakao_client_id,
        "redirect_uri": settings.kakao_redirect_uri,
        "code": code,
    }
    if settings.kakao_client_secret:
        token_data["client_secret"] = settings.kakao_client_secret

    token_res = httpx.post(
        "https://kauth.kakao.com/oauth/token",
        data=token_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if token_res.status_code != 200 or "access_token" not in token_res.json():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="카카오 인증에 실패했습니다.")

    userinfo_res = httpx.get(
        "https://kapi.kakao.com/v2/user/me",
        headers={"Authorization": f"Bearer {token_res.json()['access_token']}"},
    )
    if userinfo_res.status_code != 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="카카오 사용자 정보를 가져오지 못했습니다.")

    info = userinfo_res.json()
    kakao_account = info.get("kakao_account", {})
    email = kakao_account.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="카카오 계정에 이메일 정보가 없습니다. 이메일 동의가 필요합니다.")

    nickname = (
        kakao_account.get("profile", {}).get("nickname")
        or info.get("properties", {}).get("nickname")
        or email.split("@")[0]
    )

    return _social_login(
        provider="kakao",
        provider_id=str(info["id"]),
        email=email,
        nickname=nickname,
        db=db,
    )
