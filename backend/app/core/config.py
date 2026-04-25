from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_title: str = "VehInsight API"
    api_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    google_application_credentials: str = ""
    cors_origins: str = "http://localhost:3000"
    max_colors: int = 5
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/vehinsight"
    yolo_model_path: str = "yolov8n.pt"
    queue_max_size: int = 256

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def parsed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
