from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    database_url: str = "postgresql+psycopg://postgres:change_me@localhost:5432/licitia_dev"
    frontend_url: str = "http://localhost:5173"
    licitia_data_dir: str = ".licitia-data"
    licitia_local_ai_enabled: bool = True
    licitia_ollama_base_url: str = "http://127.0.0.1:11434"
    licitia_ollama_vision_model: str = "qwen3-vl:4b-instruct"
    licitia_ollama_timeout_seconds: float = 180.0
    licitia_vision_max_pages: int = 4
    licitia_vision_render_zoom: float = 2.0
    licitia_vision_min_render_zoom: float = 1.0
    licitia_vision_render_max_image_bytes: int = 8_388_608
    licitia_vision_render_max_dimension_px: int = 2800
    licitia_vision_structure_scope_max_output_tokens: int = Field(default=600, ge=128, le=2000)
    licitia_vision_detail_transcription_max_output_tokens: int = Field(default=1000, ge=256, le=4000)
    licitia_vision_retry_malformed_json: int = Field(default=0, ge=0, le=1)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
