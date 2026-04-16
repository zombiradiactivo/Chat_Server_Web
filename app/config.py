from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    APP_NAME: str = "ChatServer"
    DEBUG: bool = True
    SECRET_KEY: str = "chat-server-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    DATABASE_URL: str = "sqlite:///./chat_server.db"

    MEDIA_DIR: str = "./media"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024

    VOICE_PORT_START: int = 50000
    VOICE_PORT_END: int = 60000

    DEFAULT_ENCODER: str = "libx264"
    DEFAULT_VIDEO_BITRATE: int = 2500000
    DEFAULT_AUDIO_BITRATE: int = 128000

    class Config:
        env_file = ".env"


settings = Settings()

os.makedirs(settings.MEDIA_DIR, exist_ok=True)
os.makedirs(f"{settings.MEDIA_DIR}/images", exist_ok=True)
os.makedirs(f"{settings.MEDIA_DIR}/audio", exist_ok=True)
os.makedirs(f"{settings.MEDIA_DIR}/files", exist_ok=True)
os.makedirs(f"{settings.MEDIA_DIR}/servers", exist_ok=True)