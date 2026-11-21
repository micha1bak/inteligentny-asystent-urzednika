"""Sugestie anonimizacji (lokalnie, bez modelu) – test „wprowadzi plik z danymi osobowymi i sprawdzi, czy je ukrywa”."""

from fastapi.testclient import TestClient

from inteligentny_asystent_urzednika.anonimizacja import sugestie, zastosuj
from inteligentny_asystent_urzednika.app import app

TEKST = (
    "Katarzyna Zielińska, ul. Lipowa 7/3, 85-001 Bydgoszcz, tel. 600 123 456, e-mail: k.zielinska@example.com, "
    "PESEL 85010112345, dowód ABC123456, NIP 123-456-78-90, konto PL61 1090 1014 0000 0712 1981 2874. "
    "W odpowiedzi na wniosek Pana Jana Kowalskiego informuję, że Pan Nowak pełnił funkcję kierownika robót. "
    "Biuro Komunikacji Społecznej, 85-102 Bydgoszcz, ul. Jezuicka 1, tel. (52) 58 58 365, bks@um.bydgoszcz.pl"
)


def test_wykrywa_dane_osobowe_kazdego_rodzaju():
    znalezione = {f.tekst: f.rodzaj for f in sugestie(TEKST)}
    for fraza in ("Katarzyna Zielińska", "ul. Lipowa 7/3", "85-001 Bydgoszcz", "600 123 456", "k.zielinska@example.com",
                  "85010112345", "ABC123456", "Jana Kowalskiego", "Nowak"):
        assert fraza in znalezione, fraza
    assert any("NIP" in f for f in znalezione) and any(f.startswith("PL61") for f in znalezione)


def test_nie_ukrywa_danych_urzedu():
    teksty = [f.tekst for f in sugestie(TEKST)]
    assert not any(t in ("ul. Jezuicka 1", "85-102 Bydgoszcz", "bks@um.bydgoszcz.pl", "(52) 58 58 365") for t in teksty)


def test_pozycje_i_brak_nakladania():
    frs = sugestie(TEKST, ["Zielińska"])
    assert all(TEKST[f.start:f.koniec] == f.tekst for f in frs)
    assert all(a.koniec <= b.start for a, b in zip(frs, frs[1:]))
    assert "Katarzyna Zielińska" in [f.tekst for f in frs]  # dłuższy fragment wygrywa z „Zielińska”


def test_zastosuj_ukrywa_wszystkie_wystapienia():
    wynik = zastosuj("Jan Kowalski pisze. Odpowiedź dla: Jan Kowalski.", ["Jan Kowalski"])
    assert "Kowalski" not in wynik and wynik.count("█" * len("Jan Kowalski")) == 2


def test_endpoint_sugestii():
    odp = TestClient(app).post("/api/anonimizacja/sugestie", json={"tekst": TEKST, "dodatkowe": []})
    assert odp.status_code == 200
    assert {"rodzaj", "tekst", "start", "koniec"} <= set(odp.json()[0])


def test_dane_zbedne_nie_trafiaja_do_modelu_ai():
    from inteligentny_asystent_urzednika.anonimizacja import maskuj_dla_ai
    from inteligentny_asystent_urzednika.config import wczytaj_ustawienia
    from inteligentny_asystent_urzednika.propozycja import OdpowiedzWydzialuDoPisma, Wniosek, zbuduj_wiadomosci
    from inteligentny_asystent_urzednika.wiedza import wczytaj_wiedze

    m = maskuj_dla_ai("Jan Kowalski, PESEL 85010112345, tel. 600 123 456, k.zielinska@example.com, BKS tel. (52) 58 58 365")
    assert m == "Jan Kowalski, PESEL [PESEL], tel. [numer telefonu], k.zielinska@example.com, BKS tel. (52) 58 58 365"
    u = wczytaj_ustawienia()
    w = Wniosek(tresc="Proszę o informację o koszcie remontu. Jan Kowalski, PESEL 85010112345, tel. 600 123 456",
                odpowiedzi_wydzialow=[OdpowiedzWydzialuDoPisma(wydzial="WIM", tresc="Koszt 1 mln zł. Kontakt: 601 222 333.")])
    wiadomosci, _ = zbuduj_wiadomosci(w, wczytaj_wiedze(u.plik_oceny, u.plik_werdyktow, u.plik_wzorow), "wybrany", 5700)
    tresc = wiadomosci[1]["content"]
    assert "85010112345" not in tresc and "600 123 456" not in tresc and "601 222 333" not in tresc
    assert "Jan Kowalski" in tresc and "[PESEL]" in tresc
