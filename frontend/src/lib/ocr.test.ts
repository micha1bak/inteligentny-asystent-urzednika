// OCR na prawdziwych skanach wniosków z repo – te same ustawienia co w przeglądarce
// (model polski best_int, silnik LSTM, render strony w skali 3).
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterAll, describe, expect, it } from 'vitest';
import * as pdfjs from 'pdfjs-dist/legacy/build/pdf.mjs';
import { createCanvas } from '@napi-rs/canvas';
import { createWorker, OEM, type Worker } from 'tesseract.js';
import { czyMaTekst, czyOdczytWiarygodny, normalizuj, tekstZPdf, wyciagnijMetadane } from './parsowanie';

const KATALOG = join(__dirname, '../../../Przykładowe wnioski i odpowiedzi');
const MODEL = join(__dirname, '../../node_modules/@tesseract.js-data/pol/4.0.0_best_int');
const skany = readdirSync(KATALOG).filter((f) => f.startsWith('Wniosek') && f.endsWith('.pdf'));

let worker: Worker | undefined;
afterAll(async () => worker?.terminate());

async function ocr(plik: string) {
  const dane = new Uint8Array(readFileSync(join(KATALOG, plik)));
  if (czyMaTekst(await tekstZPdf(pdfjs, dane.slice()))) return null; // nie skan
  const pdf = await pdfjs.getDocument({ data: dane }).promise;
  worker ??= await createWorker('pol', OEM.LSTM_ONLY, { langPath: MODEL, cacheMethod: 'none' });
  const teksty: string[] = [];
  let pewnosc = 0;
  for (let i = 1; i <= Math.min(pdf.numPages, 5); i++) {
    const strona = await pdf.getPage(i);
    const viewport = strona.getViewport({ scale: 3 });
    const canvas = createCanvas(Math.ceil(viewport.width), Math.ceil(viewport.height));
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    // @ts-expect-error – canvas z @napi-rs/canvas jest zgodny z API, ale nie z typami DOM
    await strona.render({ canvas, canvasContext: ctx, viewport }).promise;
    const { data } = await worker.recognize(canvas.toBuffer('image/png'));
    teksty.push(data.text);
    pewnosc += data.confidence;
  }
  return { tekst: normalizuj(teksty.join('\n\n')), pewnosc: pewnosc / Math.min(pdf.numPages, 5) };
}

// Oczekiwania dla znanych skanów: wydruk ma być odczytany, pismo odręczne – odrzucone jako niewiarygodne.
const OCZEKIWANE: Record<string, { wiarygodny: boolean; temat?: RegExp }> = {
  'Wniosek - BKS.IV.1431.543.2026.pdf': { wiarygodny: true, temat: /bezdomnymi zwierzętami/ },
  'Wniosek - BKS.IV.1431.16.2026.pdf': { wiarygodny: false }, // odręczny, drukowane litery na papierze w kratkę
};

describe('OCR skanów PDF', () => {
  it.each(skany)('%s', async (plik: string) => {
    const wynik = await ocr(plik);
    if (!wynik) return; // PDF z warstwą tekstową – obsłużony bez OCR
    const odczyt = { tekst: wynik.tekst, zrodlo: 'ocr' as const, pewnosc: Math.round(wynik.pewnosc) };
    const m = wyciagnijMetadane(wynik.tekst);
    console.log(`${plik} – OCR, pewność ${odczyt.pewnosc}%, wiarygodny: ${czyOdczytWiarygodny(odczyt)}\n  temat: ${m.temat}`);
    const ocz = OCZEKIWANE[plik];
    if (!ocz) return;
    expect(czyOdczytWiarygodny(odczyt)).toBe(ocz.wiarygodny);
    if (ocz.temat) {
      expect(czyMaTekst(wynik.tekst)).toBe(true);
      expect(m.temat).toMatch(ocz.temat);
    }
  }, 120_000);
});
