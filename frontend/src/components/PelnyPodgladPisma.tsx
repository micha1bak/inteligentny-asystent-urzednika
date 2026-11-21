import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { pismoNaTekst, type StrukturaPisma } from '../lib/pismo';
import PodgladPisma from './PodgladPisma';

/**
 * Pełnoekranowy podgląd pisma nałożony na środek strony. Urzędnik poprawia tekst bezpośrednio na stronie A4,
 * drukuje lub zapisuje pismo do PDF. Zamknięcie: przycisk „Zamknij” albo klawisz Esc.
 */
export default function PelnyPodgladPisma({ pismo, onZmiana, onZamknij, tytul, onZatwierdz, trwaZatwierdzanie }: {
  pismo: StrukturaPisma;
  onZmiana: (p: StrukturaPisma) => void;
  onZamknij: () => void;
  tytul?: string;
  onZatwierdz?: () => void;
  trwaZatwierdzanie?: boolean;
}) {
  const [skopiowano, setSkopiowano] = useState(false);
  const braki = (pismoNaTekst(pismo).match(/\[\[[^\]]*\]\]/g) ?? []).length;

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
      await navigator.clipboard.writeText(pismoNaTekst(pismo));
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
        <PodgladPisma pismo={pismo} onZmiana={onZmiana} />
      </div>
    </div>,
    document.body,
  );
}
