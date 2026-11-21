import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { dodajUkrycie, scalSugestie, zastosujUkrycia } from '../lib/anonimizacja';
import { pobierzPlikPisma, sugestieAnonimizacji } from '../lib/api';
import { pismoNaTekst, type StrukturaPisma } from '../lib/pismo';
import PodgladPisma from './PodgladPisma';

/**
 * Pełnoekranowy podgląd pisma nałożony na środek strony. Urzędnik poprawia tekst bezpośrednio na stronie A4,
 * drukuje lub zapisuje pismo do PDF. Zamknięcie: przycisk „Zamknij” albo klawisz Esc.
 */
export default function PelnyPodgladPisma({
  pismo, onZmiana, onZamknij, tytul, onZatwierdz, trwaZatwierdzanie, dodatkoweAnonimizacji = [], nazwaPliku = 'odpowiedz',
}: {
  pismo: StrukturaPisma;
  onZmiana: (p: StrukturaPisma) => void;
  onZamknij: () => void;
  tytul?: string;
  onZatwierdz?: () => void;
  trwaZatwierdzanie?: boolean;
  /** frazy do zaproponowania do ukrycia oprócz wykrytych regułami (np. wnioskodawca, dane wskazane przez model) */
  dodatkoweAnonimizacji?: string[];
  /** nazwa pobieranego pliku DOCX/TXT (bez rozszerzenia) */
  nazwaPliku?: string;
}) {
  const [skopiowano, setSkopiowano] = useState(false);
  const [trybAnonimizacji, setTrybAnonimizacji] = useState(false);
  const [odrzucone, setOdrzucone] = useState<string[]>([]);
  const [blad, setBlad] = useState('');
  const braki = (pismoNaTekst(pismo).match(/\[\[[^\]]*\]\]/g) ?? []).length;
  const ukrycia = pismo.ukrycia ?? [];
  const propozycji = ukrycia.filter((u) => u.stan === 'proponowane').length;
  const ukrytych = ukrycia.filter((u) => u.stan === 'ukryte').length;
  const aktualne = useRef(pismo);
  aktualne.current = pismo;

  async function wykryj(odrzuc: string[] = odrzucone) {
    setBlad('');
    try {
      const p = aktualne.current;
      const sugestie = await sugestieAnonimizacji(pismoNaTekst(p), dodatkoweAnonimizacji);
      onZmiana({ ...aktualne.current, ukrycia: scalSugestie(aktualne.current.ukrycia ?? [], sugestie, odrzuc) });
    } catch (e) {
      setBlad(e instanceof Error ? e.message : String(e));
    }
  }

  // przy pierwszym otwarciu pisma – propozycje anonimizacji (lokalnie, bez AI)
  useEffect(() => {
    if (pismo.ukrycia === undefined) void wykryj();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function ukryjWszystkie() {
    onZmiana({ ...pismo, ukrycia: ukrycia.map((u) => ({ ...u, stan: 'ukryte' as const })) });
  }

  function odrzucPropozycje() {
    const nowe = ukrycia.filter((u) => u.stan === 'proponowane').map((u) => u.tekst);
    setOdrzucone((o) => [...o, ...nowe]);
    onZmiana({ ...pismo, ukrycia: ukrycia.filter((u) => u.stan === 'ukryte') });
  }

  function ukryjZaznaczenie() {
    const zaznaczenie = window.getSelection()?.toString() ?? '';
    if (zaznaczenie.trim().length < 2) {
      setBlad('Zaznacz myszą fragment tekstu na stronie, który ma zostać ukryty.');
      return;
    }
    setBlad('');
    onZmiana({ ...pismo, ukrycia: dodajUkrycie(ukrycia, zaznaczenie) });
  }

  async function pobierz(format: 'docx' | 'txt') {
    setBlad('');
    try {
      await pobierzPlikPisma(pismo, format, nazwaPliku);
    } catch (e) {
      setBlad(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    const esc = (e: KeyboardEvent) => {
      // Esc w trakcie edycji tylko kończy edycję fragmentu
      if (e.key !== 'Escape') return;
      if (document.activeElement instanceof HTMLElement && document.activeElement.isContentEditable) document.activeElement.blur();
      else onZamknij();
    };
    const przewijanie = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', esc);
    return () => {
      window.removeEventListener('keydown', esc);
      document.body.style.overflow = przewijanie;
    };
  }, [onZamknij]);

  async function kopiuj() {
    try {
      await navigator.clipboard.writeText(zastosujUkrycia(pismoNaTekst(pismo), ukrycia));
      setSkopiowano(true);
      setTimeout(() => setSkopiowano(false), 1500);
    } catch {
      /* brak uprawnień do schowka */
    }
  }

  return createPortal(
    <div className="pelny-podglad" role="dialog" aria-modal="true" aria-label="Podgląd pisma">
      <div className="pelny-podglad-pasek">
        <span className="tytul">{tytul ?? 'Projekt pisma'}</span>
        <span className="maly">
          {braki > 0 ? `Do uzupełnienia: ${braki}` : 'Kompletne'}
        </span>
        <span className="maly" title="Dane osobowe: szare – propozycje, czarne – ukryte">
          Anonimizacja: {propozycji} propozycji, {ukrytych} ukrytych
        </span>
        <button className={trybAnonimizacji ? 'glowny' : 'maly-p'} onClick={() => setTrybAnonimizacji((t) => !t)}
          title="W trybie anonimizacji kliknij szary fragment, aby go ukryć (czarny), albo czarny, aby przywrócić">
          {trybAnonimizacji ? 'Zakończ anonimizację' : 'Anonimizacja'}
        </button>
        {trybAnonimizacji && (
          <>
            <button className="maly-p" disabled={!propozycji} onClick={ukryjWszystkie}>Ukryj wszystkie propozycje</button>
            <button className="maly-p" onMouseDown={(e) => e.preventDefault()} onClick={ukryjZaznaczenie}>Ukryj zaznaczony tekst</button>
            <button className="maly-p" disabled={!propozycji} onClick={odrzucPropozycje}>Odrzuć pozostałe propozycje</button>
            <button className="maly-p" onClick={() => void wykryj()}>Wykryj ponownie</button>
          </>
        )}
        <button className="maly-p" onClick={() => void pobierz('docx')}>Pobierz DOCX</button>
        <button className="maly-p" onClick={() => void pobierz('txt')}>Pobierz TXT</button>
        <button className="maly-p" onClick={() => void kopiuj()}>{skopiowano ? 'Skopiowano' : 'Kopiuj tekst'}</button>
        {onZatwierdz && (
          <button className="glowny" disabled={trwaZatwierdzanie} onClick={onZatwierdz}>
            {trwaZatwierdzanie ? 'Zapisywanie…' : 'Zatwierdź odpowiedź'}
          </button>
        )}
        <button className={onZatwierdz ? 'maly-p' : 'glowny'} onClick={() => window.print()}>Drukuj / zapisz PDF</button>
        <button className="maly-p" onClick={onZamknij} aria-label="Zamknij podgląd">Zamknij</button>
      </div>
      <div className="pelny-podglad-przewijanie" onMouseDown={(e) => e.target === e.currentTarget && onZamknij()}>
        {blad && <div className="blad" style={{ maxWidth: 820, margin: '0 auto 12px' }}>{blad}</div>}
        <PodgladPisma pismo={pismo} onZmiana={onZmiana} trybAnonimizacji={trybAnonimizacji} />
      </div>
    </div>,
    document.body,
  );
}
