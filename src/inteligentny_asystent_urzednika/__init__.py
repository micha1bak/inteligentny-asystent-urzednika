def main() -> None:
    """Uruchamia backend na http://127.0.0.1:8000 (tylko lokalnie).

    Domyślnie z automatycznym przeładowaniem po zmianie kodu (wygodne przy pracy zespołu);
    BACKEND_RELOAD=0 wyłącza je (np. na pokazie).
    """
    import os
    from pathlib import Path

    import uvicorn

    przeladowanie = os.getenv("BACKEND_RELOAD", "1") != "0"
    uvicorn.run(
        "inteligentny_asystent_urzednika.app:app",
        host="127.0.0.1",
        port=int(os.getenv("BACKEND_PORT", "8000")),
        reload=przeladowanie,
        reload_dirs=[str(Path(__file__).parent)] if przeladowanie else None,
    )
