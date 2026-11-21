import { useEffect, useMemo, useRef, useState } from 'react';

interface Props {
  plik: File;
  onZamknij: () => void;
}

type Rodzaj = 'pdf' | 'docx' | 'obraz';

function rodzajPliku(nazwa: string): Rodzaj {
  const n = nazwa.toLowerCase();
  if (n.endsWith('.pdf')) return 'pdf';
  if (n.endsWith('.docx')) return 'docx';
  return 'obraz';
}

const TYPY_MIME: Record<string, string> = {
  pdf: 'application/pdf',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  tif: 'image/tiff',
  tiff: 'image/tiff',
};

function typMime(nazwa: string): string {
  return TYPY_MIME[nazwa.toLowerCase().split('.').pop() ?? ''] ?? 'application/octet-stream';
}

/**
 * Podgląd wgranego pliku w jego oryginalnej postaci, w oknie modalnym.
 * PDF i obrazy wyświetla przeglądarka, DOCX renderuje docx-preview (z zachowaniem formatowania Worda).
 * Plik nie opuszcza przeglądarki – podgląd działa na lokalnej kopii (blob URL).
 */
export default function PodgladPliku({ plik, onZamknij }: Props) {
  const okno = useRef<HTMLDialogElement>(null);
  const rodzaj = rodzajPliku(plik.name);
  // typ ustawiany z rozszerzenia – plik z systemu nie zawsze go ma, a bez niego PDF wyświetla się jako surowe bajty
  const url = useMemo(() => URL.createObjectURL(new Blob([plik], { type: typMime(plik.name) })), [plik]);
  const [blad, setBlad] = useState('');

  useEffect(() => () => URL.revokeObjectURL(url), [url]);

  // aktualny callback bez ponownego podpinania listenera
  const zamknij = useRef(onZamknij);
  zamknij.current = onZamknij;

  useEffect(() => {
    const d = okno.current;
    if (!d) return;
    if (!d.open) d.showModal();
    // Esc: „cancel” przychodzi od razu (zdarzenie „close” Chromium potrafi opóźnić, np. w karcie w tle)
    const poAnulowaniu = (e: Event) => {
      e.preventDefault();
      zamknij.current();
    };
    const poZamknieciu = () => zamknij.current();
    d.addEventListener('cancel', poAnulowaniu);
    d.addEventListener('close', poZamknieciu);
    // blokada przewijania strony pod modalem
    const poprzedni = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      d.removeEventListener('cancel', poAnulowaniu);
      d.removeEventListener('close', poZamknieciu);
      document.body.style.overflow = poprzedni;
    };
  }, []);

  return (
    <dialog
      ref={okno}
      className="podglad"
      aria-label={`Podgląd pliku ${plik.name}`}
      onClick={(e) => e.target === okno.current && onZamknij()} // kliknięcie w tło
    >
      <div className="podglad-naglowek">
        <strong title={plik.name}>{plik.name}</strong>
        <div className="rzad">
          <a className="przycisk maly-p" href={url} target="_blank" rel="noreferrer">Otwórz w nowej karcie</a>
          <a className="przycisk maly-p" href={url} download={plik.name}>Pobierz</a>
          <button className="maly-p" onClick={onZamknij} aria-label="Zamknij podgląd">✕ Zamknij</button>
        </div>
      </div>
      <div className="podglad-tresc">
        {blad ? (
          <div className="uwaga" style={{ margin: 16 }}>
            {blad} Możesz go <a href={url} download={plik.name}>pobrać</a> i otworzyć w innym programie.
          </div>
        ) : rodzaj === 'pdf' ? (
          <iframe src={url} title={plik.name} className="podglad-pdf" />
        ) : rodzaj === 'docx' ? (
          <PodgladDocx plik={plik} onBlad={setBlad} />
        ) : (
          <div className="podglad-obraz">
            <img
              src={url}
              alt={`Skan: ${plik.name}`}
              onError={() => setBlad('Przeglądarka nie potrafi wyświetlić tego obrazu (np. TIFF).')}
            />
          </div>
        )}
      </div>
    </dialog>
  );
}

function PodgladDocx({ plik, onBlad }: { plik: File; onBlad: (b: string) => void }) {
  const kontener = useRef<HTMLDivElement>(null);
  const [trwa, setTrwa] = useState(true);

  useEffect(() => {
    let anulowano = false;
    const cel = kontener.current;
    if (!cel) return;
    (async () => {
      try {
        const { renderAsync } = await import('docx-preview'); // ładowane dopiero przy pierwszym podglądzie DOCX
        if (anulowano) return;
        await renderAsync(plik, cel, undefined, { className: 'docx', inWrapper: true, breakPages: true, ignoreLastRenderedPageBreak: false });
      } catch {
        if (!anulowano) onBlad('Nie udało się wyświetlić pliku DOCX.');
      } finally {
        if (!anulowano) setTrwa(false);
      }
    })();
    return () => {
      anulowano = true;
      cel.replaceChildren();
    };
  }, [plik, onBlad]);

  return (
    <>
      {trwa && <p className="maly" style={{ padding: 16 }}>Przygotowuję podgląd dokumentu…</p>}
      <div ref={kontener} className="podglad-docx" />
    </>
  );
}
