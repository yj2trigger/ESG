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
    # 감지 임계값
    power_threshold_w: float = 10.0   # 시작: 급수 밸브(15~30W) 캐치
    stop_threshold_w: float = 5.0    # 정지: 완전 대기(1~5W)만 해당
    # polling 간격 (초)
    fast_poll_sec: float = 30.0      # 우선 기기 3대 (soft_reserved / 층별 1대 남은 세탁기)
    slow_poll_sec: float = 300.0     # 나머지 기기

    model_config = {"env_file": ".env", "extra": "ignore"}  # type: ignore[misc]


settings = Settings()
