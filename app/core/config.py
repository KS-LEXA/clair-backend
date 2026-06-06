from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List

# 프로젝트 루트(.env 위치). uvicorn을 다른 작업 디렉터리에서 실행해도
# .env 를 항상 찾도록 절대경로로 고정한다. config.py = app/core/config.py 이므로 parents[2] 가 루트.
_ENV_FILE = str(Path(__file__).resolve().parents[2] / ".env")


class Settings(BaseSettings):
    app_name: str = "Clair Backend"
    debug: bool = True

    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "clair_db"

    upload_dir: str = "./uploads"
    max_file_size_mb: int = 20
    allowed_extensions: str = ".pdf,.png,.jpg,.jpeg,.txt,.docx"

    backend_base_url: str = "http://localhost:8000"
    profile_image_max_size_mb: int = 5
    profile_image_allowed_extensions: str = ".png,.jpg,.jpeg,.webp"

    secret_key: str = "change-this-to-random-secret-key"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    jwt_algorithm: str = "HS256"

    gemini_api_key: str = ""
    ai_service_url: str = "http://localhost:8001"
    ai_service_timeout: float = 120.0   # OCR+LLM 분석은 최대 2분 허용
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:3000"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    naver_client_id: str = ""
    naver_client_secret: str = ""
    naver_redirect_uri: str = "http://localhost:8000/api/v1/auth/naver/callback"

    kakao_client_id: str = ""
    kakao_client_secret: str = ""
    kakao_redirect_uri: str = "http://localhost:8000/api/v1/auth/kakao/callback"

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = ""
    mail_from_name: str = "CLAIR"

    frontend_base_url: str = "http://localhost:5173"
    social_callback_path: str = "/social-callback"
    password_reset_path: str = "/password-reset"
    password_reset_token_expire_minutes: int = 30

    email_verification_code_expire_minutes: int = 10
    email_verification_max_attempts: int = 5

    share_path: str = "/share"
    share_token_default_expire_days: int = 7
    share_access_token_expire_minutes: int = 60

    @property
    def database_url(self) -> str:
        return f"mysql+pymysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip() for ext in self.allowed_extensions.split(",")]

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def profile_image_allowed_extensions_list(self) -> List[str]:
        return [ext.strip() for ext in self.profile_image_allowed_extensions.split(",")]

    @property
    def profile_image_max_size_bytes(self) -> int:
        return self.profile_image_max_size_mb * 1024 * 1024

    model_config = {"env_file": _ENV_FILE, "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
