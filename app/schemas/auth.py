from pydantic import BaseModel, EmailStr, field_validator, model_validator
from datetime import datetime
from typing import Optional


class SignUpRequest(BaseModel):
    email: EmailStr
    nickname: str
    password: str
    password_confirm: str
    marketing_agreed: bool = False

    @field_validator("nickname")
    @classmethod
    def nickname_length(cls, v):
        v = v.strip()
        if len(v) < 2 or len(v) > 20:
            raise ValueError("닉네임은 2자 이상 20자 이하로 입력해주세요.")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("비밀번호는 8자 이상이어야 합니다.")
        return v

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.password_confirm:
            raise ValueError("비밀번호가 일치하지 않습니다.")
        return self


class SignUpResponse(BaseModel):
    id: int
    email: str
    nickname: str
    marketing_agreed: bool
    created_at: datetime
    message: str = "회원가입이 완료되었습니다."
    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserInfo"


class UserInfo(BaseModel):
    id: int
    email: str
    nickname: str
    model_config = {"from_attributes": True}


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MyInfoResponse(BaseModel):
    id: int
    email: str
    nickname: str
    has_password: bool
    marketing_agreed: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class SocialLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserInfo"
    is_new_user: bool


class UpdateNicknameRequest(BaseModel):
    nickname: str

    @field_validator("nickname")
    @classmethod
    def nickname_length(cls, v):
        v = v.strip()
        if len(v) < 2 or len(v) > 20:
            raise ValueError("닉네임은 2자 이상 20자 이하로 입력해주세요.")
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("새 비밀번호는 8자 이상이어야 합니다.")
        return v


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str
    new_password_confirm: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("새 비밀번호는 8자 이상이어야 합니다.")
        return v

    @model_validator(mode="after")
    def passwords_match(self):
        if self.new_password != self.new_password_confirm:
            raise ValueError("비밀번호가 일치하지 않습니다.")
        return self


class PasswordResetVerifyResponse(BaseModel):
    valid: bool
    email: Optional[str] = None
