import { useState } from 'react';
import StrefaPliku from '../components/StrefaPliku';
import {
  dodajUkrycie,
  podzielNaUkrycia,
  przelaczUkrycie,
  scalSugestie,
  zastosujUkrycia,
  type Ukrycie,
} from '../lib/anonimizacja';
import { sugestieAnonimizacji } from '../lib/api';

/**
 * Anonimizacja dowolnego dokumentu (np. wniosku, odpowiedzi wydziału, załącznika przed publikacją).
 * Program proponuje dane osobowe (szare), urzędnik je akceptuje (czarne) albo zaznacza tekst do ukrycia,
 * a pobrany plik zawiera ukryte fragmenty ZASTĄPIONE znakami █. Wykrywanie działa lokalnie, bez AI.
 */
export default function Anonimizacja() {
  const [tekst, setTekst] = useState('');
  const [nazwa, setNazwa] = useState('dokument');
  const [ukrycia, setUkrycia] = useState<Ukrycie[]>([]);
  const [odrzucone, setOdrzucone] = useState<string[]>([]);
  const [dodatkowe, setDodatkowe] = useState('');
  const [trwa, setTrwa] = useState(false);
  const [blad, setBlad] = useState('');
  const [wklejanie, setWklejanie] = useState(false);

  async function wykryj(t: string, dotychczasowe: Ukrycie[] = ukrycia, odrzuc: string[] = odrzucone) {
    setTrwa(true);
    setBlad('');
    try {
      const frazy = dodatkowe.split('\n').map((l) => l.trim()).filter(Boolean);
      setUkrycia(scalSugestie(dotychczasowe, await sugestieAnonimizacji(t, frazy), odrzuc));
    } catch (e) {
      setBlad(e instanceof Error ? e.message : String(e));
    } finally {
      setTrwa(false);
    }
  }

  function wczytaj(t: string, plik?: string) {
    setTekst(t);
    setNazwa(plik ? plik.replace(/\.[^.]+$/, '') : 'dokument');
    setUkrycia([]);
    setOdrzucone([]);
    void wykryj(t, [], []);
  }

  function ukryjZaznaczenie() {
    const z = window.getSelection()?.toString() ?? '';
    if (z.trim().length < 2) {
      setBlad('Zaznacz myszą fragment tekstu dokumentu, który ma zostać ukryty.');
      return;
    }
    setBlad('');
    setUkrycia((u) => dodajUkrycie(u, z));
  }

  function odrzucPropozycje() {
    setOdrzucone((o) => [...o, ...ukrycia.filter((u) => u.stan === 'proponowane').map((u) => u.tekst)]);
    setUkrycia((u) => u.filter((x) => x.stan === 'ukryte'));
  }

  async function pobierz(format: 'docx' | 'txt') {
    setBlad('');
    try {
      const ukryte = ukrycia.filter((u) => u.stan === 'ukryte').map((u) => u.tekst);
      const odp = await fetch(`/api/dokument/${format}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tekst, ukryte, nazwa: `${nazwa} zanonimizowany` }),
      });
      if (!odp.ok) throw new Error(`Błąd backendu (${odp.status}).`);
      const url = URL.createObjectURL(await odp.blob());
      const a = document.createElement('a');
      a.href = url;
      a.download = `${nazwa}_zanonimizowany.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setBlad(e instanceof Error ? e.message : String(e));
    }
  }

  const propozycji = ukrycia.filter((u) => u.stan === 'proponowane').length;
  const ukrytych = ukrycia.filter((u) => u.stan === 'ukryte').length;

  return (
    <>
      <h1>Anonimizacja dokumentu</h1>
      <p className="podtytul">
        Wgraj dokument (PDF, Word) albo wklej tekst. Program podświetli na szaro dane osobowe – kliknij fragment, aby go
        ukryć (czarny), albo zaznacz myszą dowolny tekst i „Ukryj zaznaczony tekst”. Pobrany plik nie zawiera ukrytych danych.
        Wykrywanie działa lokalnie, bez wysyłania danych do AI.
      </p>

      <div className="siatka-2">
        <div className="stos">
          <div className="karta">
            <h2>Dokument</h2>
            <StrefaPliku napis="Przeciągnij plik PDF lub Word albo kliknij, aby wybrać" onWczytano={(w, plik) => wczytaj(w.tekst, plik.name)} />
            <div className="rzad" style={{ marginTop: 10 }}>
              <button className="maly-p" onClick={() => setWklejanie((w) => !w)}>{wklejanie ? 'Ukryj pole tekstu' : 'Wklej tekst'}</button>
            </div>
            {wklejanie && (
              <label style={{ marginTop: 8 }}>
                Tekst dokumentu
                <textarea rows={8} placeholder="Wklej treść…" onBlur={(e) => e.target.value.trim() && wczytaj(e.target.value)} />
              </label>
            )}
            <label style={{ marginTop: 10 }}>
              Dodatkowe frazy do ukrycia (np. nazwisko wnioskodawcy; jedna w linii)
              <textarea rows={2} value={dodatkowe} onChange={(e) => setDodatkowe(e.target.value)} />
            </label>
          </div>

          {tekst && (
            <div className="karta">
              <h2>Wykryte dane ({ukrycia.length})</h2>
              <div className="rzad" style={{ marginBottom: 8 }}>
                <button className="maly-p" disabled={!propozycji} onClick={() => setUkrycia((u) => u.map((x) => ({ ...x, stan: 'ukryte' as const })))}>
                  Ukryj wszystkie propozycje
                </button>
                <button className="maly-p" onMouseDown={(e) => e.preventDefault()} onClick={ukryjZaznaczenie}>Ukryj zaznaczony tekst</button>
                <button className="maly-p" disabled={!propozycji} onClick={odrzucPropozycje}>Odrzuć pozostałe propozycje</button>
                <button className="maly-p" disabled={trwa} onClick={() => void wykryj(tekst)}>Wykryj ponownie</button>
              </div>
              <ul className="lista-ukryc">
                {ukrycia.map((u) => (
                  <li key={u.tekst}>
                    <button className={`anon anon-${u.stan} przycisk-ukrycia`} onClick={() => setUkrycia((x) => przelaczUkrycie(x, u.tekst))}
                      title={u.stan === 'ukryte' ? 'Kliknij, aby przywrócić jako propozycję' : 'Kliknij, aby ukryć'}>
                      {u.tekst}
                    </button>
                    <span className="maly"> {u.rodzaj}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="stos">
          <div className="karta">
            <div className="rzad rozsun">
              <h2 style={{ margin: 0 }}>Podgląd</h2>
              <span className="maly">{propozycji} propozycji, {ukrytych} ukrytych</span>
            </div>
            {trwa && <div className="postep postep-ciagly"><div /></div>}
            {blad && <div className="blad">{blad}</div>}
            {!tekst && <p className="maly">Wgraj dokument, aby zobaczyć propozycje anonimizacji.</p>}
            {tekst && (
              <div className="dokument-anonimizacja tryb-anonimizacji">
                {podzielNaUkrycia(tekst, ukrycia).map((o, i) =>
                  o.ukrycie ? (
                    <span key={i} className={`anon anon-${o.ukrycie.stan}`} title={o.ukrycie.rodzaj}
                      onClick={() => setUkrycia((x) => przelaczUkrycie(x, o.ukrycie!.tekst))}>
                      {o.tekst}
                    </span>
                  ) : (
                    <span key={i}>{o.tekst}</span>
                  ),
                )}
              </div>
            )}
            {tekst && (
              <div className="rzad" style={{ marginTop: 12 }}>
                <button className="glowny" onClick={() => void pobierz('docx')}>Pobierz DOCX (zanonimizowany)</button>
                <button className="maly-p" onClick={() => void pobierz('txt')}>Pobierz TXT</button>
                <button className="maly-p" onClick={() => void navigator.clipboard.writeText(zastosujUkrycia(tekst, ukrycia))}>Kopiuj tekst</button>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
