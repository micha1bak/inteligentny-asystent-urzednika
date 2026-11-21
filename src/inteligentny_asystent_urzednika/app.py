"""Aplikacja FastAPI: API pod /api, dokumentacja pod /docs, interfejs (static) pod /."""

from contextlib import asynccontextmanager
from importlib.resources import files

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import wnioski, zaslepki
from .db import utworz_tabele
from .wydzialy import wczytaj_wydzialy


@asynccontextmanager
async def _cykl_zycia(app: FastAPI):
    utworz_tabele()
    yield


app = FastAPI(title="Inteligentny asystent urzędnika", version="0.1.0", lifespan=_cykl_zycia)
app.include_router(wnioski.router)
app.include_router(zaslepki.router)


@app.get("/api/wydzialy", tags=["słowniki"])
def lista_wydzialow():
    return wczytaj_wydzialy()


@app.get("/api/zdrowie", tags=["słowniki"])
def zdrowie():
    from .config import ustawienia

    return {"status": "ok", "llm": ustawienia.llm_backend, "embeddingi": ustawienia.embed_backend}


app.mount("/", StaticFiles(directory=str(files(__package__).joinpath("static")), html=True), name="static")
