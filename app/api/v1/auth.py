from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.auth import (
    SignUpRequest, SignUpResponse,
    LoginRequest, TokenResponse,
    RefreshRequest, RefreshResponse,
    MyInfoResponse, UpdateNicknameRequest, ChangePasswordRequest,
    SocialLoginResponse,
    PasswordResetRequest, PasswordResetConfirmRequest, PasswordResetVerifyResponse,
)
from app.schemas.contract import MessageResponse
from app.services.auth_service import (
    signup, login, refresh_access_token, update_nickname, change_password,
    request_password_reset, verify_reset_token, confirm_password_reset,
    get_google_auth_url, google_login,
    get_naver_auth_url, naver_login,
    get_kakao_auth_url, kakao_login,
)

router = APIRouter()


@router.post("/signup", response_model=SignUpResponse, status_code=201, summary="회원가입")
def api_signup(body: SignUpRequest, db: Session = Depends(get_db)):
    user = signup(email=body.email, nickname=body.nickname, password=body.password, db=db, marketing_agreed=body.marketing_agreed)
    return SignUpResponse(id=user.id, email=user.email, nickname=user.nickname, marketing_agreed=user.marketing_agreed, created_at=user.created_at)


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
    return MyInfoResponse(
        id=user.id,
        email=user.email,
        nickname=user.nickname,
        has_password=user.password_hash is not None,
        marketing_agreed=user.marketing_agreed,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.patch("/me/nickname", response_model=MyInfoResponse, summary="닉네임 변경")
def api_update_nickname(body: UpdateNicknameRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    updated = update_nickname(user, body.nickname, db)
    return MyInfoResponse(
        id=updated.id,
        email=updated.email,
        nickname=updated.nickname,
        has_password=updated.password_hash is not None,
        marketing_agreed=updated.marketing_agreed,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.patch("/me/password", response_model=MessageResponse, summary="비밀번호 변경")
def api_change_password(body: ChangePasswordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    change_password(user=user, current_password=body.current_password, new_password=body.new_password, db=db)
    return MessageResponse(message="비밀번호가 변경되었습니다.")


# ── 비밀번호 재설정 (비로그인 상태에서 이메일 링크로) ─────────────────────────

@router.post("/password-reset/request", response_model=MessageResponse, summary="비밀번호 재설정 요청 (메일 발송)")
async def api_request_password_reset(body: PasswordResetRequest, db: Session = Depends(get_db)):
    # 보안상 사용자 존재 여부와 무관하게 동일 메시지 반환
    await request_password_reset(email=body.email, db=db)
    return MessageResponse(message="입력하신 이메일로 재설정 안내가 발송되었습니다. 메일이 오지 않으면 스팸함을 확인해주세요.")


@router.get("/password-reset/verify", response_model=PasswordResetVerifyResponse, summary="재설정 토큰 유효성 검증")
def api_verify_reset_token(token: str, db: Session = Depends(get_db)):
    user = verify_reset_token(raw_token=token, db=db)
    return PasswordResetVerifyResponse(valid=True, email=user.email)


@router.post("/password-reset/confirm", response_model=MessageResponse, summary="비밀번호 재설정 확정")
def api_confirm_password_reset(body: PasswordResetConfirmRequest, db: Session = Depends(get_db)):
    confirm_password_reset(raw_token=body.token, new_password=body.new_password, db=db)
    return MessageResponse(message="비밀번호가 재설정되었습니다. 새 비밀번호로 로그인해주세요.")


# ── Google ────────────────────────────────────────────────────────────────────

@router.get("/google", summary="구글 소셜 로그인 시작")
def api_google_login():
    return RedirectResponse(url=get_google_auth_url())


@router.get("/google/callback", response_model=SocialLoginResponse, summary="구글 소셜 로그인 콜백")
def api_google_callback(code: str, db: Session = Depends(get_db)):
    return google_login(code=code, db=db)


# ── Naver ─────────────────────────────────────────────────────────────────────

@router.get("/naver", summary="네이버 소셜 로그인 시작")
def api_naver_login():
    return RedirectResponse(url=get_naver_auth_url())


@router.get("/naver/callback", response_model=SocialLoginResponse, summary="네이버 소셜 로그인 콜백")
def api_naver_callback(code: str, state: str, db: Session = Depends(get_db)):
    return naver_login(code=code, state=state, db=db)


# ── Kakao ─────────────────────────────────────────────────────────────────────

@router.get("/kakao", summary="카카오 소셜 로그인 시작")
def api_kakao_login():
    return RedirectResponse(url=get_kakao_auth_url())


@router.get("/kakao/callback", response_model=SocialLoginResponse, summary="카카오 소셜 로그인 콜백")
def api_kakao_callback(code: str, db: Session = Depends(get_db)):
    return kakao_login(code=code, db=db)
