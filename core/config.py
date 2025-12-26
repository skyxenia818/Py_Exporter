from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PORT: int = 9000
    DEV: bool = False

settings = Settings()