import { useRef, useState } from 'react';
import { odczytajTekst } from '../lib/parsowanie';

interface Props {
  napis: string;
  wielokrotny?: boolean;
  onWczytano: (tekst: string, plik: File) => void;
}

export default function StrefaPliku({ napis, wielokrotny, onWczytano }: Props) {
  const wejscie = useRef<HTMLInputElement>(null);
  const [aktywna, setAktywna] = useState(false);
  const [blad, setBlad] = useState('');
  const [trwa, setTrwa] = useState(false);

  async function obsluz(pliki: FileList | null) {
    if (!pliki?.length) return;
    setBlad('');
    setTrwa(true);
    for (const plik of Array.from(pliki)) {
      try {
        onWczytano(await odczytajTekst(plik), plik);
      } catch (e) {
        setBlad(`${plik.name}: ${e instanceof Error ? e.message : String(e)}`);
      }
    }
    setTrwa(false);
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
          void obsluz(e.dataTransfer.files);
        }}
      >
        <strong>{trwa ? 'Odczytuję plik…' : napis}</strong>
        <div className="maly">PDF, DOCX lub TXT · przeciągnij tutaj albo kliknij · plik jest czytany lokalnie</div>
        <input
          ref={wejscie}
          type="file"
          hidden
          multiple={wielokrotny}
          accept=".pdf,.docx,.txt"
          onChange={(e) => {
            void obsluz(e.target.files);
            e.target.value = '';
          }}
        />
      </div>
      {blad && <div className="blad" style={{ marginTop: 8 }}>{blad}</div>}
    </>
  );
}
