"""Klient Groq (API zgodne z OpenAI Chat Completions)."""

from __future__ import annotations

from typing import Protocol

import re

import httpx


class BladLLM(Exception):
    """Błąd po stronie dostawcy modelu – komunikat nadaje się do pokazania urzędnikowi."""

    def __init__(self, komunikat: str, status: int = 502):
        super().__init__(komunikat)
        self.komunikat = komunikat
        self.status = status


class KlientLLM(Protocol):
    async def czat_json(self, wiadomosci: list[dict[str, str]]) -> str: ...


class KlientGroq:
    def __init__(
        self,
        api_key: str,
        model: str,
        url: str,
        timeout_s: float,
        max_tokens: int = 2000,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.url = url
        self.timeout_s = timeout_s
        self.max_tokens = max_tokens
        self._transport = transport

    async def czat_json(self, wiadomosci: list[dict[str, str]]) -> str:
        """Wysyła rozmowę i zwraca treść odpowiedzi modelu (oczekiwany obiekt JSON)."""
        tresc: dict = {
            "model": self.model,
            "messages": wiadomosci,
            "temperature": 0.2,
            "max_completion_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }
        if "gpt-oss" in self.model:
            # modele rozumujące: mało rozumowania = więcej miejsca na odpowiedź w limicie tokenów
            tresc["reasoning_effort"] = "low"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s, transport=self._transport) as klient:
                odp = await klient.post(self.url, json=tresc, headers={"Authorization": f"Bearer {self.api_key}"})
        except httpx.TimeoutException as e:
            raise BladLLM("Model nie odpowiedział w wyznaczonym czasie. Spróbuj ponownie.", 504) from e
        except httpx.HTTPError as e:
            raise BladLLM(f"Brak połączenia z Groq: {e.__class__.__name__}.", 502) from e

        if odp.status_code == 401:
            raise BladLLM("Groq odrzucił klucz API (401). Sprawdź GROQ_API_KEY w pliku .env.", 502)
        if odp.status_code == 413:
            raise BladLLM(
                f"Zapytanie jest większe niż limit tokenów planu Groq ({_komunikat_bledu(odp)}). "
                "Ustaw w .env KONTEKST_PRAWNY=wybrany i GROQ_LIMIT_TPM zgodny z planem.",
                502,
            )
        if odp.status_code == 429:
            komunikat = _komunikat_bledu(odp)
            if "per day" in komunikat.lower() or "TPD" in komunikat or "RPD" in komunikat:
                czas = re.search(r"try again in ([0-9hms.]+)", komunikat)
                raise BladLLM(
                    "Wyczerpano DZIENNY limit modelu w darmowym planie Groq"
                    + (f" – ponowna próba możliwa za ok. {czas.group(1).split('.')[0]}s" if czas else "")
                    + ". Funkcje bez AI (kalendarz, podobne sprawy, wydziały, anonimizacja, eksport) działają dalej. "
                    "Docelowo: lokalny model w urzędzie (LLM_URL) – bez limitów i bez internetu.",
                    429,
                )
            raise BladLLM(
                "Wykorzystano limit tokenów/zapytań Groq na tę minutę (darmowy plan mieści ok. jedno zapytanie na minutę). "
                "Odczekaj minutę i spróbuj ponownie.",
                429,
            )
        if odp.status_code >= 400:
            raise BladLLM(f"Groq zwrócił błąd {odp.status_code}: {_komunikat_bledu(odp)}", 502)

        try:
            wybor = odp.json()["choices"][0]
            tekst = wybor["message"]["content"]
        except (ValueError, KeyError, IndexError) as e:
            raise BladLLM("Nieoczekiwany format odpowiedzi z Groq.", 502) from e
        if wybor.get("finish_reason") == "length":
            raise BladLLM(
                "Odpowiedź modelu została ucięta (za mało tokenów na odpowiedź). Zwiększ GROQ_MAX_TOKENS w .env.", 502
            )
        return tekst or ""


def _komunikat_bledu(odp: httpx.Response) -> str:
    try:
        return str(odp.json()["error"]["message"])[:300]
    except (ValueError, KeyError, TypeError):
        return odp.text[:300]
