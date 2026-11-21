"""Jedyny punkt kontaktu z modelami językowymi.

Reszta kodu woła tylko `generuj()` i `osadz()`. Backend wybiera konfiguracja (ASYSTENT_LLM_BACKEND,
ASYSTENT_EMBED_BACKEND), więc przejście na model lokalny bez internetu nie wymaga zmian w kodzie.

- "lokalny": Ollama na tym samym komputerze (np. Bielik) – docelowy tryb w urzędzie, dane nie opuszczają maszyny,
- "groq": otwarty model (gpt-oss-120b) w chmurze Groq – tylko na hackathonie i tylko z danymi testowymi,
- "atrapa": deterministyczne odpowiedzi bez modelu – testy i praca nad UI.
"""

import hashlib
import json
import math
import re
import urllib.request
from functools import cache
from typing import Protocol

from .config import Ustawienia, ustawienia

WYMIAR_ATRAPY = 256


class BladLLM(RuntimeError):
    pass


class ModelTekstowy(Protocol):
    def generuj(self, prompt: str, system: str | None = None, max_tokenow: int = 4000) -> str: ...


class ModelEmbeddingow(Protocol):
    def osadz(self, teksty: list[str]) -> list[list[float]]: ...


# --- Ollama (lokalnie, bez internetu) ---------------------------------------

def _ollama_post(url: str, sciezka: str, dane: dict, timeout: float = 600) -> dict:
    zapytanie = urllib.request.Request(
        url.rstrip("/") + sciezka,
        data=json.dumps(dane).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(zapytanie, timeout=timeout) as odp:
            return json.loads(odp.read())
    except OSError as e:
        raise BladLLM(f"Brak połączenia z Ollama pod {url}: {e}") from e


class Ollama:
    def __init__(self, u: Ustawienia):
        self.url, self.model, self.model_embed = u.ollama_url, u.ollama_model, u.ollama_model_embed

    def generuj(self, prompt: str, system: str | None = None, max_tokenow: int = 4000) -> str:
        wiadomosci = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        odp = _ollama_post(self.url, "/api/chat", {
            "model": self.model, "messages": wiadomosci, "stream": False,
            "options": {"num_predict": max_tokenow},
        })
        return odp["message"]["content"]

    def osadz(self, teksty: list[str]) -> list[list[float]]:
        return _ollama_post(self.url, "/api/embed", {"model": self.model_embed, "input": teksty})["embeddings"]


# --- Groq (chmura, tylko dane testowe) ---------------------------------------

class Groq:
    def __init__(self, u: Ustawienia):
        import groq

        if not u.groq_api_key:
            raise BladLLM("Brak klucza Groq: ustaw AI_API_KEY w pliku .env")
        self._groq = groq
        self.klient = groq.Groq(api_key=u.groq_api_key.get_secret_value())
        self.model = u.groq_model

    def generuj(self, prompt: str, system: str | None = None, max_tokenow: int = 8000) -> str:
        wiadomosci = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        try:
            odp = self.klient.chat.completions.create(
                model=self.model, messages=wiadomosci, max_completion_tokens=max_tokenow,
            )
        except self._groq.APIConnectionError as e:
            raise BladLLM(f"Brak połączenia z API Groq: {e}") from e
        except self._groq.APIStatusError as e:
            raise BladLLM(f"Błąd API Groq ({e.status_code}): {e.message}") from e
        wybor = odp.choices[0]
        if wybor.finish_reason == "length":
            raise BladLLM("Odpowiedź modelu została ucięta (za mały limit tokenów).")
        return wybor.message.content or ""


# --- Atrapa (testy, praca nad UI) --------------------------------------------

class Atrapa:
    def generuj(self, prompt: str, system: str | None = None, max_tokenow: int = 4000) -> str:
        return f"[ATRAPA LLM] Odpowiedź na: {prompt[:200]}"

    def osadz(self, teksty: list[str]) -> list[list[float]]:
        """Wektor z haszowanych słów – wystarcza do testów wyszukiwania po wspólnych słowach."""
        wektory = []
        for tekst in teksty:
            w = [0.0] * WYMIAR_ATRAPY
            for slowo in re.findall(r"\w+", tekst.lower()):
                if len(slowo) > 2:
                    w[int(hashlib.md5(slowo[:6].encode()).hexdigest(), 16) % WYMIAR_ATRAPY] += 1.0
            norma = math.sqrt(sum(x * x for x in w)) or 1.0
            wektory.append([x / norma for x in w])
        return wektory


# --- Wybór backendu ----------------------------------------------------------

@cache
def model_tekstowy() -> ModelTekstowy:
    return {"lokalny": Ollama, "groq": Groq}.get(ustawienia.llm_backend, lambda u: Atrapa())(ustawienia)


@cache
def model_embeddingow() -> ModelEmbeddingow:
    return Ollama(ustawienia) if ustawienia.embed_backend == "lokalny" else Atrapa()


def generuj(prompt: str, system: str | None = None, max_tokenow: int = 4000) -> str:
    return model_tekstowy().generuj(prompt, system=system, max_tokenow=max_tokenow)


def osadz(teksty: list[str]) -> list[list[float]]:
    return model_embeddingow().osadz(teksty)
