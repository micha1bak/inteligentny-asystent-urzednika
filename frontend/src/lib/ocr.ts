// Rozpoznawanie tekstu ze skanów (OCR) w przeglądarce – tesseract.js, model polski.
// Wszystkie pliki (worker, rdzeń WebAssembly, model) są serwowane lokalnie z public/ocr,
// więc skan nie opuszcza komputera i nie jest potrzebny internet.
import { createWorker, OEM, type Worker } from 'tesseract.js';

export type Postep = (opis: string, ulamek?: number) => void;

let worker: Promise<Worker> | null = null;
let biezacyPostep: Postep | undefined;

function sciezki() {
  const baza = new URL(`${import.meta.env.BASE_URL}ocr/`, window.location.href).href;
  return { workerPath: `${baza}worker.min.js`, corePath: `${baza}core`, langPath: `${baza}lang` };
}

const STATUSY: Record<string, string> = {
  'loading tesseract core': 'Ładuję silnik OCR',
  'initializing tesseract': 'Uruchamiam silnik OCR',
  'loading language traineddata': 'Ładuję model języka polskiego',
  'initializing api': 'Przygotowuję rozpoznawanie',
  'recognizing text': 'Rozpoznaję tekst',
};

function pobierzWorker(): Promise<Worker> {
  worker ??= createWorker('pol', OEM.LSTM_ONLY, {
    ...sciezki(),
    logger: (m) => biezacyPostep?.(STATUSY[m.status] ?? m.status, m.progress),
  }).catch((e) => {
    worker = null;
    throw e;
  });
  return worker;
}

export interface WynikOcr {
  tekst: string;
  /** średnia pewność rozpoznania 0–100 */
  pewnosc: number;
}

/** Rozpoznaje tekst z obrazów stron (kolejno), raportując postęp. */
export async function rozpoznaj(strony: HTMLCanvasElement[], postep?: Postep): Promise<WynikOcr> {
  const w = await (biezacyPostep = postep, pobierzWorker());
  const teksty: string[] = [];
  let suma = 0;
  try {
    for (let i = 0; i < strony.length; i++) {
      biezacyPostep = (opis, ulamek) => postep?.(`${opis} – strona ${i + 1} z ${strony.length}`, ulamek);
      const { data } = await w.recognize(strony[i]);
      teksty.push(data.text);
      suma += data.confidence;
    }
  } finally {
    biezacyPostep = undefined;
  }
  return { tekst: teksty.join('\n\n'), pewnosc: strony.length ? Math.round(suma / strony.length) : 0 };
}
