import { useEffect, useRef, useState } from 'react';
import {
  dodajUkrycie,
  podzielNaUkrycia,
  przelaczUkrycie,
  scalSugestie,
  zastosujUkrycia,
  type Ukrycie,
} from '../lib/anonimizacja';
import { pobierzPlikDokumentu, sugestieAnonimizacji } from '../lib/api';

/**
 * Ręczna i półautomatyczna anonimizacja tekstu dostępna bezpośrednio w widoku wniosku
 * (bez konieczności przechodzenia do osobnego panelu /anonimizacja).
 */
export default function AnonimizacjaTekstu({
  tekst,
  nazwa = 'dokument',
  dodatkowe = [],
  ukrycia: kontrolowaneUkrycia,
  onZmianaUkryc,
  onZastosujTekst,
}: {
  tekst: string;
  nazwa?: string;
  dodatkowe?: string[];
  /** opcjonalny stan kontrolowany przez rodzica (np. żeby kopiowanie wiadomości uwzględniało ukrycia) */
  ukrycia?: Ukrycie[];
  onZmianaUkryc?: (u: Ukrycie[]) => void;
  /** opcjonalny przycisk podmiany tekstu źródłowego wersją zanonimizowaną (np. w treści wniosku) */
  onZastosujTekst?: (zanonimizowany: string) => void;
}) {
  const [lokalneUkrycia, setLokalneUkrycia] = useState<Ukrycie[]>([]);
  const ukrycia = kontrolowaneUkrycia ?? lokalneUkrycia;
  const ukryciaRef = useRef(ukrycia);
  ukryciaRef.current = ukrycia;

  const ustawUkrycia = (zmiana: Ukrycie[] | ((prev: Ukrycie[]) => Ukrycie[])) => {
    const nastepne = typeof zmiana === 'function' ? zmiana(ukryciaRef.current) : zmiana;
    if (onZmianaUkryc) onZmianaUkryc(nastepne);
    else setLokalneUkrycia(nastepne);
  };

  const [odrzucone, setOdrzucone] = useState<string[]>([]);
  const [nowaFraza, setNowaFraza] = useState('');
  const [trwa, setTrwa] = useState(false);
  const [blad, setBlad] = useState('');
  const [skopiowano, setSkopiowano] = useState(false);
  const kluczDodatkowych = dodatkowe.join('\n');

  async function wykryj(odrzuc: string[] = odrzucone, sygnal?: AbortSignal) {
    if (!tekst.trim()) return;
    setTrwa(true);
    setBlad('');
    try {
      const frazy = kluczDodatkowych.split('\n').map((s) => s.trim()).filter(Boolean);
      const sugestie = await sugestieAnonimizacji(tekst, frazy, sygnal);
      ustawUkrycia((u) => scalSugestie(u, sugestie, odrzuc));
    } catch (e) {
      if (!(e instanceof DOMException && e.name === 'AbortError')) {
        setBlad(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setTrwa(false);
    }
  }

  useEffect(() => {
    const ac = new AbortController();
    void wykryj(odrzucone, ac.signal);
    return () => ac.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tekst, kluczDodatkowych]);

  function ukryjZaznaczenie() {
    const z = window.getSelection()?.toString() ?? '';
    if (z.trim().length < 2) {
      setBlad('Zaznacz myszą fragment tekstu w podglądzie poniżej, który ma zostać ukryty.');
      return;
    }
    setBlad('');
    ustawUkrycia((u) => dodajUkrycie(u, z));
  }

  function dodajRecznaFraze() {
    const t = nowaFraza.trim();
    if (t.length < 2) {
      setBlad('Wpisz co najmniej 2 znaki frazy do ukrycia.');
      return;
    }
    setBlad('');
    ustawUkrycia((u) => dodajUkrycie(u, t, 'ręczne'));
    setNowaFraza('');
  }

  function odrzucPropozycje() {
    setOdrzucone((o) => [...o, ...ukrycia.filter((u) => u.stan === 'proponowane').map((u) => u.tekst)]);
    ustawUkrycia((u) => u.filter((x) => x.stan === 'ukryte'));
  }

  async function pobierz(format: 'docx' | 'txt') {
    setBlad('');
    try {
      const ukryte = ukrycia.filter((u) => u.stan === 'ukryte').map((u) => u.tekst);
      await pobierzPlikDokumentu(tekst, ukryte, format, nazwa);
    } catch (e) {
      setBlad(e instanceof Error ? e.message : String(e));
    }
  }

  async function kopiuj() {
    try {
      await navigator.clipboard.writeText(zastosujUkrycia(tekst, ukrycia));
      setSkopiowano(true);
      setTimeout(() => setSkopiowano(false), 1500);
    } catch {
      /* brak uprawnień do schowka */
    }
  }

  const propozycji = ukrycia.filter((u) => u.stan === 'proponowane').length;
  const ukrytych = ukrycia.filter((u) => u.stan === 'ukryte').length;

  return (
    <div className="stos" style={{ gap: 8 }}>
      <div className="rzad rozsun">
        <span className="maly">
          Kliknij szary fragment, aby go ukryć (czarny), albo zaznacz myszą dowolny tekst i użyj „Ukryj zaznaczony tekst”.
        </span>
        <span className="maly">
          {propozycji} propozycji, {ukrytych} ukrytych
        </span>
      </div>

      <div className="rzad">
        <button
          type="button"
          className="maly-p"
          disabled={!propozycji}
          onClick={() => ustawUkrycia((u) => u.map((x) => ({ ...x, stan: 'ukryte' as const })))}
        >
          Ukryj wszystkie propozycje
        </button>
        <button type="button" className="maly-p" onMouseDown={(e) => e.preventDefault()} onClick={ukryjZaznaczenie}>
          Ukryj zaznaczony tekst
        </button>
        <button type="button" className="maly-p" disabled={!propozycji} onClick={odrzucPropozycje}>
          Odrzuć pozostałe propozycje
        </button>
        <button type="button" className="maly-p" disabled={trwa} onClick={() => void wykryj()}>
          Wykryj ponownie
        </button>
      </div>

      <div className="rzad" style={{ flexWrap: 'nowrap' }}>
        <input
          value={nowaFraza}
          placeholder="Wpisz ręcznie frazę do ukrycia (np. nazwisko, adres)…"
          onChange={(e) => setNowaFraza(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              dodajRecznaFraze();
            }
          }}
        />
        <button type="button" className="maly-p nowrap" disabled={nowaFraza.trim().length < 2} onClick={dodajRecznaFraze}>
          Ukryj frazę
        </button>
      </div>

      {trwa && <div className="postep postep-ciagly"><div /></div>}
      {blad && <div className="blad">{blad}</div>}

      <div className="dokument-anonimizacja tryb-anonimizacji" style={{ maxHeight: 340 }}>
        {podzielNaUkrycia(tekst, ukrycia).map((o, i) =>
          o.ukrycie ? (
            <span
              key={i}
              className={`anon anon-${o.ukrycie.stan}`}
              title={`${o.ukrycie.rodzaj} – kliknij, aby ${o.ukrycie.stan === 'ukryte' ? 'przywrócić' : 'ukryć'}`}
              onClick={() => ustawUkrycia((x) => przelaczUkrycie(x, o.ukrycie!.tekst))}
            >
              {o.tekst}
            </span>
          ) : (
            <span key={i}>{o.tekst}</span>
          ),
        )}
      </div>

      {ukrycia.length > 0 && (
        <div className="rzad" style={{ gap: 6 }}>
          {ukrycia.map((u) => (
            <button
              key={u.tekst}
              type="button"
              className={`anon anon-${u.stan} przycisk-ukrycia`}
              onClick={() => ustawUkrycia((x) => przelaczUkrycie(x, u.tekst))}
              title={`${u.rodzaj} – kliknij, aby ${u.stan === 'ukryte' ? 'przywrócić' : 'ukryć'}`}
            >
              {u.tekst}
            </button>
          ))}
        </div>
      )}

      <div className="rzad">
        <button type="button" className="glowny maly-p" onClick={() => void pobierz('docx')}>
          Pobierz DOCX (zanonimizowany)
        </button>
        <button type="button" className="maly-p" onClick={() => void pobierz('txt')}>
          Pobierz TXT (zanonimizowany)
        </button>
        <button type="button" className="maly-p" onClick={() => void kopiuj()}>
          {skopiowano ? 'Skopiowano' : 'Kopiuj zanonimizowany'}
        </button>
        {onZastosujTekst && (
          <button
            type="button"
            className="maly-p"
            disabled={!ukrytych}
            title="Zastąpi ukryte fragmenty znakami █ w polu tekstowym powyżej (do zapisu przyciskiem Zapisz zmiany)"
            onClick={() => onZastosujTekst(zastosujUkrycia(tekst, ukrycia))}
          >
            Zastosuj w treści wniosku
          </button>
        )}
      </div>
    </div>
  );
}
