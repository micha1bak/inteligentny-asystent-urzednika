import { useRef, useState } from 'react';
import { odczytajPdf } from '../lib/parsowanie';

interface Props {
  napis: string;
  onWczytano: (tekst: string, plik: File) => void;
}

export default function StrefaPliku({ napis, onWczytano }: Props) {
  const wejscie = useRef<HTMLInputElement>(null);
  const [aktywna, setAktywna] = useState(false);
  const [blad, setBlad] = useState('');
  const [trwa, setTrwa] = useState(false);

  async function obsluz(plik: File | undefined) {
    if (!plik) return;
    setBlad('');
    setTrwa(true);
    try {
      onWczytano(await odczytajPdf(plik), plik);
    } catch (e) {
      setBlad(`${plik.name}: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setTrwa(false);
    }
  }

  return (
    <>
      <div
        className={`strefa-upuszczania ${aktywna ? 'aktywna' : ''}`}
        onClick={() => wejscie.current?.click()}
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
        <strong>{trwa ? 'Odczytuję plik…' : napis}</strong>
        <div className="maly">Plik PDF · przeciągnij tutaj albo kliknij · plik jest czytany lokalnie</div>
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
