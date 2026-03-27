from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.auth import SignUpRequest, SignUpResponse, LoginRequest, TokenResponse, RefreshRequest, RefreshResponse, MyInfoResponse, UpdateNicknameRequest, ChangePasswordRequest
from app.schemas.contract import MessageResponse
from app.services.auth_service import signup, login, refresh_access_token, update_nickname, change_password

router = APIRouter()


@router.post("/signup", response_model=SignUpResponse, status_code=201, summary="회원가입")
def api_signup(body: SignUpRequest, db: Session = Depends(get_db)):
    user = signup(email=body.email, nickname=body.nickname, password=body.password, db=db)
    return SignUpResponse(id=user.id, email=user.email, nickname=user.nickname, created_at=user.created_at)


@router.post("/login", summary="로그인 (Swagger 자물쇠 겸용)")
def api_login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return login(email=form_data.username, password=form_data.password, db=db)


@router.post("/login/json", response_model=TokenResponse, summary="로그인 (JSON)")
def api_login_json(body: LoginRequest, db: Session = Depends(get_db)):
    return login(email=body.email, password=body.password, db=db)


@router.post("/refresh", response_model=RefreshResponse, summary="토큰 갱신")
def api_refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    return refresh_access_token(refresh_token=body.refresh_token, db=db)


@router.get("/me", response_model=MyInfoResponse, summary="내 정보 조회")
def api_my_info(user: User = Depends(get_current_user)):
    return MyInfoResponse(id=user.id, email=user.email, nickname=user.nickname, created_at=user.created_at, updated_at=user.updated_at)


@router.patch("/me/nickname", response_model=MyInfoResponse, summary="닉네임 변경")
def api_update_nickname(body: UpdateNicknameRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    updated = update_nickname(user, body.nickname, db)
    return MyInfoResponse(id=updated.id, email=updated.email, nickname=updated.nickname, created_at=updated.created_at, updated_at=updated.updated_at)


@router.patch("/me/password", response_model=MessageResponse, summary="비밀번호 변경")
def api_change_password(body: ChangePasswordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    change_password(user=user, current_password=body.current_password, new_password=body.new_password, db=db)
    return MessageResponse(message="비밀번호가 변경되었습니다.")
