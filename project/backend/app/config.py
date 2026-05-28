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
    # 세탁기 가동 판단 기준: 급수 밸브(15~30W)부터 감지, 대기(1~8W)와 구분
    # 냉수 세탁 드럼 회전(50~200W)도 안정적으로 포착. fly.toml [env] 또는 PATCH /admin/settings로 변경 가능
    power_threshold_w: float = 20.0

    model_config = {"env_file": ".env", "extra": "ignore"}  # type: ignore[misc]


settings = Settings()
