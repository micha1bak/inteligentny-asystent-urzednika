"""Inteligentny asystent urzędnika – obsługa wniosków o dostęp do informacji publicznej (UMB)."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="inteligentny-asystent-urzednika")
    pod = parser.add_subparsers(dest="komenda")
    start = pod.add_parser("start", help="uruchom aplikację (domyślnie)")
    start.add_argument("--host", default="127.0.0.1")
    start.add_argument("--port", type=int, default=8000)
    start.add_argument("--reload", action="store_true")
    dane = pod.add_parser("dane-testowe", help="wczytaj dane testowe do bazy")
    dane.add_argument("--wyczysc", action="store_true", help="usuń istniejące wnioski przed wczytaniem")
    args = parser.parse_args()

    if args.komenda == "dane-testowe":
        from .dane_testowe import wczytaj

        print(wczytaj(wyczysc=args.wyczysc))
        return

    import uvicorn

    uvicorn.run(
        "inteligentny_asystent_urzednika.app:app",
        host=getattr(args, "host", "127.0.0.1"),
        port=getattr(args, "port", 8000),
        reload=getattr(args, "reload", False),
    )
