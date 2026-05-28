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

    smartthings_pat: str = ""
    # 시작 임계값: available/soft_reserved → in_use (급수 뱸브 15~30W부터 감지)
    power_threshold_w: float = 20.0
    # 정지 임계값: in_use → available (완전 대기 1~5W만 해당, 사이클 중간 정지 3~15W 오전환 방지)
    stop_threshold_w: float = 5.0

    model_config = {"env_file": ".env", "extra": "ignore"}  # type: ignore[misc]


settings = Settings()
