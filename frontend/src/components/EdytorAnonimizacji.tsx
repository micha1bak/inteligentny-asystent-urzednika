import { useRef, useState } from 'react';
import type { Fragment } from '../types';
import { dodajReczny, przesunPoEdycji, scal, wykryj, zastosuj } from '../lib/anonimizacja';

interface Props {
  tekst: string;
  fragmenty: Fragment[];
  onZmien: (tekst: string, fragmenty: Fragment[]) => void;
}

/**
 * Dwuetapowa anonimizacja: program zaznacza propozycje na szaro, urzędnik klika, żeby
 * zaczernić (akceptacja) albo odrzucić. Można też zaznaczyć myszą dowolny fragment.
 */
export default function EdytorAnonimizacji({ tekst, fragmenty, onZmien }: Props) {
  const [tryb, setTryb] = useState<'anonimizacja' | 'edycja' | 'podglad'>('anonimizacja');
  const [zaznaczenie, setZaznaczenie] = useState<{ start: number; koniec: number } | null>(null);
  const pole = useRef<HTMLDivElement>(null);

  const propozycje = fragmenty.filter((f) => f.stan === 'propozycja').length;
  const zaakceptowane = fragmenty.filter((f) => f.stan === 'zaakceptowany').length;

  const zmienStan = (id: string) =>
    onZmien(
      tekst,
      fragmenty.map((f) =>
        f.id !== id ? f : { ...f, stan: f.stan === 'zaakceptowany' ? 'odrzucony' : 'zaakceptowany' },
      ),
    );

  function wykryjPonownie() {
    const reczne = fragmenty.filter((f) => f.zrodlo === 'reczny' || f.stan !== 'propozycja');
    const nowe = wykryj(tekst).filter((n) => !reczne.some((r) => n.start < r.koniec && n.koniec > r.start));
    onZmien(tekst, scal([...reczne, ...nowe]));
  }

  function poZaznaczeniu() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !pole.current || !pole.current.contains(sel.anchorNode)) {
      setZaznaczenie(null);
      return;
    }
    const r = sel.getRangeAt(0);
    const przed = document.createRange();
    przed.selectNodeContents(pole.current);
    przed.setEnd(r.startContainer, r.startOffset);
    const start = przed.toString().length;
    const koniec = start + r.toString().length;
    if (koniec > start) setZaznaczenie({ start, koniec });
  }

  function anonimizujZaznaczenie() {
    if (!zaznaczenie) return;
    onZmien(tekst, dodajReczny(fragmenty, zaznaczenie.start, zaznaczenie.koniec));
    setZaznaczenie(null);
    window.getSelection()?.removeAllRanges();
  }

  const segmenty: { tekst: string; f?: Fragment }[] = [];
  let poz = 0;
  for (const f of [...fragmenty].sort((a, b) => a.start - b.start)) {
    if (f.start < poz) continue;
    if (f.start > poz) segmenty.push({ tekst: tekst.slice(poz, f.start) });
    segmenty.push({ tekst: tekst.slice(f.start, f.koniec), f });
    poz = f.koniec;
  }
  if (poz < tekst.length) segmenty.push({ tekst: tekst.slice(poz) });

  return (
    <div>
      <div className="rzad rozsun" style={{ marginBottom: 10 }}>
        <div className="zakladki">
          <button className={tryb === 'anonimizacja' ? 'aktywna' : ''} onClick={() => setTryb('anonimizacja')}>Anonimizacja</button>
          <button className={tryb === 'edycja' ? 'aktywna' : ''} onClick={() => setTryb('edycja')}>Edycja treści</button>
          <button className={tryb === 'podglad' ? 'aktywna' : ''} onClick={() => setTryb('podglad')}>Wersja do wysyłki</button>
        </div>
        {tryb === 'anonimizacja' && (
          <div className="rzad">
            <button className="maly-p" onClick={wykryjPonownie}>Wykryj dane osobowe</button>
            <button
              className="maly-p"
              disabled={!propozycje}
              onClick={() => onZmien(tekst, fragmenty.map((f) => (f.stan === 'propozycja' ? { ...f, stan: 'zaakceptowany' } : f)))}
            >
              Akceptuj wszystkie ({propozycje})
            </button>
            <button className="maly-p glowny" disabled={!zaznaczenie} onClick={anonimizujZaznaczenie} title="Zaznacz myszą fragment tekstu">
              Anonimizuj zaznaczenie
            </button>
          </div>
        )}
      </div>

      {tryb === 'anonimizacja' && (
        <>
          <p className="maly" style={{ margin: '0 0 8px' }}>
            <span className="anon propozycja">szare</span> – propozycje do decyzji (kliknij, aby zaczernić) ·{' '}
            <span className="anon zaakceptowany" style={{ color: '#fff' }}>czarne</span> – zostaną ukryte (kliknij, aby odrzucić) ·
            zaznacz myszą dowolny tekst, aby go ukryć. Do decyzji: <strong>{propozycje}</strong>, ukrytych: <strong>{zaakceptowane}</strong>.
          </p>
          <div ref={pole} className="anon-tekst" onMouseUp={poZaznaczeniu}>
            {segmenty.map((s, i) =>
              s.f ? (
                <span
                  key={s.f.id}
                  className={`anon ${s.f.stan}`}
                  title={`${s.f.kategoria} – ${s.f.stan === 'zaakceptowany' ? 'kliknij, aby odrzucić' : 'kliknij, aby zaczernić'}`}
                  onClick={() => zmienStan(s.f!.id)}
                >
                  {s.tekst}
                </span>
              ) : (
                <span key={i}>{s.tekst}</span>
              ),
            )}
          </div>
        </>
      )}

      {tryb === 'edycja' && (
        <textarea
          rows={22}
          value={tekst}
          onChange={(e) => onZmien(e.target.value, przesunPoEdycji(tekst, e.target.value, fragmenty))}
          style={{ fontFamily: "'Times New Roman', serif", fontSize: '1rem' }}
        />
      )}

      {tryb === 'podglad' && (
        <>
          {propozycje > 0 && <div className="uwaga" style={{ marginBottom: 8 }}>Masz {propozycje} nierozpatrzonych propozycji anonimizacji – w tej wersji nie są ukryte.</div>}
          <div className="anon-tekst">{zastosuj(tekst, fragmenty)}</div>
        </>
      )}
    </div>
  );
}
