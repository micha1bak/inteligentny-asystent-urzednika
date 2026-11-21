import { useEffect, useRef, useState } from 'react';
import { ROZSZERZENIA_WNIOSKU } from '../lib/api';
import { odczytajWniosek, type WynikOdczytu } from '../lib/parsowanie';
import PodgladPliku from './PodgladPliku';

interface Props {
  /** napis, gdy nie wgrano jeszcze pliku */
  napis: string;
  onWczytano: (wynik: WynikOdczytu, plik: File) => void;
}

/**
 * Strefa wgrywania pliku. Po wgraniu kliknięcie pokazuje podgląd pliku w oryginalnym formacie,
 * a plik zmienia się przyciskiem „Zmień plik” albo przeciągnięciem nowego.
 */
export default function StrefaPliku({ napis, onWczytano }: Props) {
  const wejscie = useRef<HTMLInputElement>(null);
  const przerwij = useRef<AbortController | null>(null);
  const [aktywna, setAktywna] = useState(false);
  const [blad, setBlad] = useState('');
  const [trwa, setTrwa] = useState<string | null>(null);
  const [plik, setPlik] = useState<File>();
  const [podglad, setPodglad] = useState(false);

  useEffect(() => () => przerwij.current?.abort(), []);

  async function obsluz(nowy: File | undefined) {
    if (!nowy || trwa) return;
    setBlad('');
    setTrwa(nowy.name);
    const kontroler = (przerwij.current = new AbortController());
    try {
      onWczytano(await odczytajWniosek(nowy, kontroler.signal), nowy);
      setPlik(nowy);
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return;
      setBlad(`${nowy.name}: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      if (przerwij.current === kontroler) przerwij.current = null;
      setTrwa(null);
    }
  }

  const wybierzPlik = () => wejscie.current?.click();
  const kliknieto = () => {
    if (trwa) return;
    if (plik) setPodglad(true);
    else wybierzPlik();
  };

  return (
    <>
      <div
        className={`strefa-upuszczania ${aktywna ? 'aktywna' : ''} ${trwa ? 'zajeta' : ''}`}
        role="button"
        tabIndex={0}
        aria-label={plik ? `Podgląd pliku ${plik.name}` : napis}
        onClick={kliknieto}
        onKeyDown={(e) => {
          if (e.target !== e.currentTarget || (e.key !== 'Enter' && e.key !== ' ')) return;
          e.preventDefault();
          kliknieto();
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setAktywna(true);
        }}
        onDragLeave={() => setAktywna(false)}
        onDrop={(e) => {
          e.preventDefault();
          setAktywna(false);
          void obsluz(e.dataTransfer.files[0]);
        }}
      >
        {trwa ? (
          <>
            <strong>Odczytuję {trwa}…</strong>
            <div className="postep postep-ciagly" role="progressbar" style={{ maxWidth: 360, margin: '10px auto 6px' }}>
              <div />
            </div>
          </>
        ) : plik ? (
          <>
            <strong>{plik.name}</strong>
            <div className="strefa-akcje">
              <button
                className="maly-p"
                onClick={(e) => {
                  e.stopPropagation();
                  setPodglad(true);
                }}
              >
                Podgląd
              </button>
              <button
                className="maly-p"
                onClick={(e) => {
                  e.stopPropagation();
                  wybierzPlik();
                }}
              >
                Zmień plik
              </button>
            </div>
          </>
        ) : (
          <>
            <strong>{napis}</strong>
            <div className="maly" style={{ marginTop: 4 }}>{ROZSZERZENIA_WNIOSKU.join(', ')}</div>
          </>
        )}
      </div>
      <input
        ref={wejscie}
        type="file"
        hidden
        accept={ROZSZERZENIA_WNIOSKU.join(',')}
        onChange={(e) => {
          void obsluz(e.target.files?.[0]);
          e.target.value = '';
        }}
      />
      {blad && <div className="blad" style={{ marginTop: 8 }}>{blad}</div>}
      {podglad && plik && <PodgladPliku plik={plik} onZamknij={() => setPodglad(false)} />}
    </>
  );
}
