import secrets
from urllib.parse import urlencode
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
import httpx
from app.core.config import settings
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.models.user import User
from app.models.social_account import SocialAccount


def signup(email: str, nickname: str, password: str, db: Session) -> User:
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 가입된 이메일입니다.")
    user = User(email=email, nickname=nickname.strip(), password_hash=hash_password(password))
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
