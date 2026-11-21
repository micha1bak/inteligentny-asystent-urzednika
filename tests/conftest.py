import os

# testy nigdy nie wołają prawdziwych modeli, niezależnie od ustawień w .env
os.environ["ASYSTENT_LLM_BACKEND"] = "atrapa"
os.environ["ASYSTENT_EMBED_BACKEND"] = "atrapa"

import pytest  # noqa: E402
from sqlmodel import create_engine  # noqa: E402
from sqlmodel.pool import StaticPool  # noqa: E402

from inteligentny_asystent_urzednika import db  # noqa: E402


@pytest.fixture(autouse=True)
def baza_w_pamieci():
    silnik = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    db.ustaw_silnik(silnik)
    db.utworz_tabele()
    yield silnik
    db.ustaw_silnik(None)
