import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMagazyn } from '../magazyn';
import StrefaPliku from '../components/StrefaPliku';
import PropozycjaOdpowiedzi from '../components/PropozycjaOdpowiedzi';
import { dzisIso, formatuj } from '../lib/daty';
import { terminOdpowiedzi } from '../lib/terminy';
import { wyciagnijMetadane, type WynikOdczytu } from '../lib/parsowanie';
import { zapamietaneInicjaly, zapamietajInicjaly } from '../lib/inicjaly';

export default function NowyWniosek() {
  const { dodajWniosek, nastepnyNumer, wnioski } = useMagazyn();
  const nav = useNavigate();
  const dzis = dzisIso();
  const [nazwaPliku, setNazwaPliku] = useState<string>();
  const [tresc, setTresc] = useState('');
  const [odczyt, setOdczyt] = useState<WynikOdczytu>();
  const [dane, setDane] = useState({
    numer: nastepnyNumer(dzis.slice(0, 4)),
    dataWplywu: dzis,
    inicjaly: zapamietaneInicjaly(),
    wnioskodawca: '',
    kontakt: '',
    temat: '',
  });
  const ustaw = (k: keyof typeof dane, v: string) =>
    setDane((d) => {
      const nowe = { ...d, [k]: v };
      if (k === 'dataWplywu' && v.length === 10 && d.numer === nastepnyNumer(d.dataWplywu.slice(0, 4))) nowe.numer = nastepnyNumer(v.slice(0, 4));
      return nowe;
    });

  function wczytano(wynik: WynikOdczytu, plik: File) {
    const { tekst } = wynik;
    setNazwaPliku(plik.name);
    setOdczyt(wynik);
    setTresc(tekst);
    if (!tekst || wynik.odreczny) {
      setDane((d) => ({ ...d, wnioskodawca: '', kontakt: '', temat: '' }));
      return;
    }
    const m = wyciagnijMetadane(tekst);
    setDane((d) => ({ ...d, wnioskodawca: m.wnioskodawca, kontakt: m.kontakt, temat: m.temat }));
  }

  const duplikat = wnioski.some((w) => w.numer === dane.numer);
  const gotowe = nazwaPliku && dane.numer && dane.dataWplywu && dane.temat && !duplikat;

  function zatwierdz() {
    zapamietajInicjaly(dane.inicjaly);
    dodajWniosek({
      ...dane,
      inicjaly: dane.inicjaly.toUpperCase(),
      kontakt: dane.kontakt || undefined,
      tresc,
      nazwaPliku,
      status: 'brak_dzialan',
    });
    nav('/');
  }

  return (
    <>
      <h1>Dodaj wniosek</h1>
      <p className="podtytul">Wgraj plik z wnioskiem (PDF, DOCX lub skan), sprawdź dane wyciągnięte automatycznie i zatwierdź – wniosek trafi do kalendarza.</p>
      <div className="siatka-2">
        <div className="stos">
          <div className="karta">
            <StrefaPliku napis={nazwaPliku ? `Wczytano: ${nazwaPliku} – kliknij, aby zmienić` : 'Wgraj wniosek (PDF / DOCX)'} onWczytano={wczytano} />
            {odczyt?.odreczny && (
              <div className="uwaga" style={{ marginTop: 10 }}>
                Dokument zawiera pismo odręczne (strony: {odczyt.strony_odreczne.join(', ')}) – tekst nie został odczytany
                automatycznie. Oceń dokument samodzielnie i wpisz dane wniosku ręcznie.
              </div>
            )}
            {nazwaPliku && !tresc && !odczyt?.odreczny && (
              <div className="uwaga" style={{ marginTop: 10 }}>
                Nie udało się odczytać tekstu z pliku. Wpisz dane wniosku ręcznie.
              </div>
            )}
          </div>
          <div className="karta">
            <h2>Dane wniosku do zatwierdzenia</h2>
            {odczyt && !odczyt.odreczny && odczyt.zrodlo === 'tekst' && tresc && (
              <div className="info" style={{ marginBottom: 12 }}>Pola uzupełnione automatycznie – sprawdź je przed zatwierdzeniem.</div>
            )}
            {odczyt && !odczyt.odreczny && odczyt.zrodlo === 'model' && tresc && (
              <div className="uwaga" style={{ marginBottom: 12 }}>
                Plik zawiera skan – tekst {odczyt.stron > 1 ? `stron ${odczyt.strony_z_modelu.join(', ')} ` : ''}przepisał model.
                Pola uzupełnione na tej podstawie; sprawdź je dokładnie, zwłaszcza nazwiska i numery.
              </div>
            )}
            <div className="formularz">
              <label>
                Nr wniosku
                <input value={dane.numer} onChange={(e) => ustaw('numer', e.target.value)} />
                {duplikat && <span style={{ color: 'var(--czerwony)' }}>Taki numer już istnieje</span>}
              </label>
              <label>
                Data wpływu
                <input type="date" value={dane.dataWplywu} onChange={(e) => ustaw('dataWplywu', e.target.value)} />
                {dane.dataWplywu && <span>Termin odpowiedzi: <strong>{formatuj(terminOdpowiedzi({ dataWplywu: dane.dataWplywu }))}</strong></span>}
              </label>
              <label>
                Wnioskodawca
                <input value={dane.wnioskodawca} onChange={(e) => ustaw('wnioskodawca', e.target.value)} />
              </label>
              <label>
                Adres do odpowiedzi (e-mail / adres)
                <input value={dane.kontakt} onChange={(e) => ustaw('kontakt', e.target.value)} />
              </label>
              <label className="pelny">
                Skrócony opis tematu
                <input value={dane.temat} onChange={(e) => ustaw('temat', e.target.value)} placeholder="np. Koszt remontu ul. Gdańskiej w 2026 r." />
              </label>
              <label>
                Inicjały osoby prowadzącej
                <input value={dane.inicjaly} maxLength={4} onChange={(e) => ustaw('inicjaly', e.target.value)} />
              </label>
            </div>
            <div className="rzad" style={{ marginTop: 14 }}>
              <button className="glowny" disabled={!gotowe} onClick={zatwierdz}>Zatwierdź i dodaj do kalendarza</button>
              {!gotowe && <span className="maly">Wymagane: plik wniosku, numer, data wpływu i temat.</span>}
            </div>
          </div>
        </div>
        <div className="stos">
          <PropozycjaOdpowiedzi
            key={nazwaPliku}
            wniosek={{ tresc, temat: dane.temat, numer: dane.numer, data_wplywu: dane.dataWplywu, wnioskodawca: dane.wnioskodawca }}
          />
        </div>
      </div>
    </>
  );
}
