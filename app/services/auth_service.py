import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, quote
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
import httpx
from app.core.config import settings
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.models.user import User
from app.models.social_account import SocialAccount
from app.models.password_reset import PasswordResetToken
from app.integrations.email_client import send_email


def signup(email: str, nickname: str, password: str, db: Session, marketing_agreed: bool = False) -> User:
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 가입된 이메일입니다.")
    user = User(email=email, nickname=nickname.strip(), password_hash=hash_password(password), marketing_agreed=marketing_agreed)
    db.add(user)
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


# ── 공통 소셜 로그인 처리 ──────────────────────────────────────────────────────

def _social_login(provider: str, provider_id: str, email: str, nickname: str, db: Session) -> dict:
    """소셜 계정으로 유저 찾기 → 없으면 생성, JWT 발급"""
    social = (
        db.query(SocialAccount)
        .filter(SocialAccount.provider == provider, SocialAccount.provider_id == provider_id)
        .first()
    )

    is_new_user = False

    if social:
        user = social.user
    else:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(email=email, nickname=nickname[:20], password_hash=None)
            db.add(user)
            db.flush()  # user.id 확보
            is_new_user = True

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
