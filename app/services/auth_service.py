from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.models.user import User


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
    if not user or not verify_password(password, user.password_hash):
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
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="현재 비밀번호가 올바르지 않습니다.")
    if current_password == new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="새 비밀번호가 현재 비밀번호와 동일합니다.")
    user.password_hash = hash_password(new_password)
    db.commit()
