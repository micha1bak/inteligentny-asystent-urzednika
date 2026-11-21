import { useRef, useState } from 'react';
import { odczytajPdf, type WynikOdczytu } from '../lib/parsowanie';

interface Props {
  napis: string;
  onWczytano: (wynik: WynikOdczytu, plik: File) => void;
}

export default function StrefaPliku({ napis, onWczytano }: Props) {
  const wejscie = useRef<HTMLInputElement>(null);
  const [aktywna, setAktywna] = useState(false);
  const [blad, setBlad] = useState('');
  const [postep, setPostep] = useState<{ opis: string; ulamek?: number } | null>(null);

  async function obsluz(plik: File | undefined) {
    if (!plik || postep) return;
    setBlad('');
    setPostep({ opis: 'Odczytuję plik' });
    try {
      onWczytano(await odczytajPdf(plik, (opis, ulamek) => setPostep({ opis, ulamek })), plik);
    } catch (e) {
      setBlad(`${plik.name}: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setPostep(null);
    }
  }

  return (
    <>
      <div
        className={`strefa-upuszczania ${aktywna ? 'aktywna' : ''} ${postep ? 'zajeta' : ''}`}
        onClick={() => !postep && wejscie.current?.click()}
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
        {postep ? (
          <>
            <strong>{postep.opis}…</strong>
            <div className="postep" role="progressbar" aria-valuenow={Math.round((postep.ulamek ?? 0) * 100)}>
              <div style={{ width: `${Math.round((postep.ulamek ?? 0) * 100)}%` }} />
            </div>
            <div className="maly">Rozpoznawanie odbywa się na tym komputerze – skan nie jest nigdzie wysyłany.</div>
          </>
        ) : (
          <>
            <strong>{napis}</strong>
            <div className="maly">Plik PDF (także skan) · przeciągnij tutaj albo kliknij · plik jest czytany lokalnie</div>
          </>
        )}
        <input
          ref={wejscie}
          type="file"
          hidden
          accept=".pdf,application/pdf"
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
