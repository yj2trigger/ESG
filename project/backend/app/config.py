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
    smartthings_device_id: str = ""  # fallback single device
    smartthings_machine_id: int = 1  # fallback single machine id
    smartthings_device_map: str = ""  # "machine_id:st_device_id,..." e.g. "1:7c805ce1-..."
    power_threshold_w: float = 100.0  # W 이상이면 세탁기 가동 중으로 판정

    model_config = {"env_file": ".env", "extra": "ignore"}  # type: ignore[misc]


settings = Settings()
