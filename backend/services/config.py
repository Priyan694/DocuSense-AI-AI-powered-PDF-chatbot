from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


class Settings(BaseSettings):
    minimax_api_key: str = Field(default="")
    minimax_model: str = Field(default="minimax-text-01")
    minimax_base_url: str = Field(default="https://api.minimaxi.chat/v1")
    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="llama-3.3-70b-versatile")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1")
    embedding_model_name: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    vector_db_path: str = Field(default=str(BASE_DIR / "chroma_db"))
    frontend_origin: str = Field(default="http://localhost:5173")
    max_upload_size_mb: int = Field(default=20)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

