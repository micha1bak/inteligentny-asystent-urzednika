"""Eksport pisma do DOCX/TXT z anonimizacją."""

import io
import zipfile
from xml.dom import minidom

from fastapi.testclient import TestClient

from inteligentny_asystent_urzednika.app import app
from inteligentny_asystent_urzednika.wzor.eksport import pismo_do_docx, pismo_do_tekstu

PISMO = {
    "naglowek": ["URZĄD MIASTA BYDGOSZCZY", "Biuro Komunikacji Społecznej"],
    "data": "Bydgoszcz, dnia 21 listopada 2026 r.",
    "znak": "BKS.IV.1431.18.2026",
    "adresat": ["Jan Kowalski", "ul. Lipowa 7/3"],
    "tytul": [],
    "tresc": [
        {"typ": "zwrot", "tekst": "Szanowny Panie,"},
        {"typ": "akapit", "tekst": "w odpowiedzi na wniosek Pana Jana Kowalskiego informuję, że liczba wynosi 5697 & <więcej>."},
        {"typ": "ad", "tekst": "Ad 1"},
    ],
    "zakonczenie": "Łączę wyrazy szacunku,",
    "podpis": ["Biuro Komunikacji Społecznej", "Urząd Miasta Bydgoszczy"],
    "stopka": ["85-102 Bydgoszcz, ul. Jezuicka 1"],
    "ukrycia": [
        {"tekst": "Jan Kowalski", "rodzaj": "imię i nazwisko", "stan": "ukryte"},
        {"tekst": "Jana Kowalskiego", "rodzaj": "imię i nazwisko", "stan": "ukryte"},
        {"tekst": "ul. Lipowa 7/3", "rodzaj": "adres", "stan": "proponowane"},
    ],
}


def test_txt_ukrywa_zatwierdzone_i_zostawia_propozycje():
    t = pismo_do_tekstu(PISMO)
    assert "Kowalski" not in t and "████████████" in t
    assert "ul. Lipowa 7/3" in t  # propozycja nieakceptowana – bez zmian
    assert t.startswith("URZĄD MIASTA BYDGOSZCZY") and "ul. Jezuicka 1" in t


def test_docx_poprawny_i_bez_ukrytych_danych():
    dane = pismo_do_docx(PISMO)
    with zipfile.ZipFile(io.BytesIO(dane)) as z:
        assert {"[Content_Types].xml", "word/document.xml", "word/header1.xml", "word/footer1.xml"} <= set(z.namelist())
        for nazwa in z.namelist():
            minidom.parseString(z.read(nazwa))  # każdy XML poprawny składniowo
        dokument = z.read("word/document.xml").decode()
    assert "Kowalski" not in dokument and "5697 &amp; &lt;więcej&gt;" in dokument
    assert "BKS.IV.1431.18.2026" in dokument and "Ad 1" in dokument


def test_endpointy_eksportu():
    k = TestClient(app)
    d = k.post("/api/pismo/docx", json={"pismo": PISMO, "nazwa": "BKS.IV.1431.18.2026 odpowiedź"})
    assert d.status_code == 200 and d.content[:2] == b"PK"
    assert 'filename="BKS.IV.1431.18.2026_odpowiedz.docx"' in d.headers["content-disposition"]
    t = k.post("/api/pismo/txt", json={"pismo": PISMO})
    assert t.status_code == 200 and "Kowalski" not in t.text
