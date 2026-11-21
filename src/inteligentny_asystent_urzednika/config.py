"""Konfiguracja aplikacji (zmienne środowiskowe z prefiksem ASYSTENT_ lub plik .env)."""

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

KATALOG_PROJEKTU = Path(__file__).resolve().parents[2]


class Ustawienia(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASYSTENT_", env_file=".env", extra="ignore")

    katalog_danych: Path = KATALOG_PROJEKTU / "dane"
    baza_url: str = ""  # pusty = SQLite w katalogu danych

    # Model językowy: "lokalny" (Ollama, bez internetu), "groq" (chmura, tylko na hackathonie
    # z danymi testowymi) albo "atrapa" (deterministyczne odpowiedzi do testów i pracy nad UI).
    llm_backend: Literal["lokalny", "groq", "atrapa"] = "atrapa"
    # Embeddingi do wyszukiwania: "lokalny" (Ollama) albo "atrapa" (haszowanie słów, bez modelu).
    embed_backend: Literal["lokalny", "atrapa"] = "atrapa"

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M"
    ollama_model_embed: str = "nomic-embed-text"

    groq_model: str = "openai/gpt-oss-120b"
    groq_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("AI_API_KEY", "GROQ_API_KEY", "ASYSTENT_GROQ_API_KEY")
    )

    @property
    def url_bazy(self) -> str:
        if self.baza_url:
            return self.baza_url
        return f"sqlite:///{(self.katalog_danych / 'asystent.db').as_posix()}"


ustawienia = Ustawienia()
