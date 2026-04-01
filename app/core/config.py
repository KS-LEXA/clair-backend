from pydantic_settings import BaseSettings
from typing import List


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

    secret_key: str = "change-this-to-random-secret-key"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    jwt_algorithm: str = "HS256"

    gemini_api_key: str = ""
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    naver_client_id: str = ""
    naver_client_secret: str = ""
    naver_redirect_uri: str = "http://localhost:8000/api/v1/auth/naver/callback"

    kakao_client_id: str = ""
    kakao_client_secret: str = ""
    kakao_redirect_uri: str = "http://localhost:8000/api/v1/auth/kakao/callback"

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
