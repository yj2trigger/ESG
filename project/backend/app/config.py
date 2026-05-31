from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://esg_user:esg_pass@db:5432/esg_db"
    secret_key: str = "dev-secret-key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080  # 7 days
    cors_origins: str = "http://localhost:5173"
    resend_api_key: str = ""
    gmail_user: str = ""
    gmail_app_password: str = ""
    iot_device_key: str = ""

    # 감지 임계값 (관리자 표시 + IoT 엔드포인트 로그 활용)
    power_threshold_w: float = 10.0
    stop_threshold_w: float = 5.0

    # GitHub Actions 릴레이 폴링 주기 (프론트엔드 표시용)
    relay_poll_sec: int = 12

    model_config = {"env_file": ".env", "extra": "ignore"}  # type: ignore[misc]


settings = Settings()
