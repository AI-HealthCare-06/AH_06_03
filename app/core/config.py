from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DB_USER: str = "paeon"
    DB_PASSWORD: str = "change-me"
    DB_HOST: str = "localhost"
    DB_PORT: str = "3306"
    DB_NAME: str = "paeon"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
