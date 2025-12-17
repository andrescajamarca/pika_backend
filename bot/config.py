import os
from typing import List

class Config:
    # PostgreSQL
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "pika_user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "pika_secret_2024")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "pika_db")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "db")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_SECRET_TOKEN: str = os.getenv("TELEGRAM_SECRET_TOKEN", "")
    
    @property
    def TELEGRAM_ALLOWED_USERS(self) -> List[int]:
        users_str = os.getenv("TELEGRAM_ALLOWED_USERS", "")
        if not users_str:
            return []
        return [int(u.strip()) for u in users_str.split(",") if u.strip()]
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8080"))


config = Config()
