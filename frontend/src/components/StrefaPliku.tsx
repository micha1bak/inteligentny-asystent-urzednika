import { useEffect, useRef, useState } from 'react';
import { ROZSZERZENIA_WNIOSKU } from '../lib/api';
import { odczytajWniosek, type WynikOdczytu } from '../lib/parsowanie';

interface Props {
  napis: string;
  onWczytano: (wynik: WynikOdczytu, plik: File) => void;
}

export default function StrefaPliku({ napis, onWczytano }: Props) {
  const wejscie = useRef<HTMLInputElement>(null);
  const przerwij = useRef<AbortController | null>(null);
  const [aktywna, setAktywna] = useState(false);
  const [blad, setBlad] = useState('');
  const [trwa, setTrwa] = useState<string | null>(null);

  useEffect(() => () => przerwij.current?.abort(), []);

  async function obsluz(plik: File | undefined) {
    if (!plik || trwa) return;
    setBlad('');
    setTrwa(plik.name);
    const kontroler = (przerwij.current = new AbortController());
    try {
      onWczytano(await odczytajWniosek(plik, kontroler.signal), plik);
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return;
      setBlad(`${plik.name}: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      if (przerwij.current === kontroler) przerwij.current = null;
      setTrwa(null);
    }
  }

  return (
    <>
      <div
        className={`strefa-upuszczania ${aktywna ? 'aktywna' : ''} ${trwa ? 'zajeta' : ''}`}
        onClick={() => !trwa && wejscie.current?.click()}
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
            <div className="maly">
              Backend sprawdza, czy pismo nie jest odręczne, i odczytuje tekst. Skan może potrwać do minuty na stronę.
            </div>
          </>
        ) : (
          <>
            <strong>{napis}</strong>
            <div className="maly">
              PDF (także skan), DOCX lub zdjęcie · przeciągnij tutaj albo kliknij · strony PDF i skany są analizowane przez model (Groq)
            </div>
          </>
        )}
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
      </div>
      {blad && <div className="blad" style={{ marginTop: 8 }}>{blad}</div>}
    </>
  );
}
