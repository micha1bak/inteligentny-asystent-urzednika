// Odczyt tekstu z pliku PDF w przeglądarce – nic nie opuszcza komputera urzędnika.
// PDF z warstwą tekstową czytamy bezpośrednio (pdf.js); skan rozpoznajemy przez OCR (tesseract.js).
import type { PDFDocumentProxy } from 'pdfjs-dist';
import { dzisIso } from './daty';
import type { Postep } from './ocr';

/** Ile stron skanu rozpoznawać – wnioski mają zwykle 1–2 strony, a OCR trwa kilka sekund na stronę. */
export const MAKS_STRON_OCR = 5;
/** Rozdzielczość renderowania skanu: 1 jednostka PDF = 1/72 cala, skala 3 ≈ 216 DPI. */
const SKALA_OCR = 3;
/** Poniżej tylu znaków uznajemy, że PDF nie ma prawdziwej warstwy tekstowej. */
const MIN_ZNAKOW_TEKSTU = 30;

export interface WynikOdczytu {
  tekst: string;
  zrodlo: 'tekst' | 'ocr';
  /** średnia pewność OCR 0–100 (tylko dla skanów) */
  pewnosc?: number;
  /** ile stron pominięto przy OCR (limit MAKS_STRON_OCR) */
  pominieteStrony?: number;
}

export async function odczytajPdf(plik: File, postep?: Postep): Promise<WynikOdczytu> {
  if (!plik.name.toLowerCase().endsWith('.pdf')) throw new Error('Wgraj plik w formacie PDF.');
  const pdfjs = await import('pdfjs-dist');
  const worker = await import('pdfjs-dist/build/pdf.worker.min.mjs?url');
  pdfjs.GlobalWorkerOptions.workerSrc = worker.default;
  const pdf = await pdfjs.getDocument({ data: new Uint8Array(await plik.arrayBuffer()) }).promise;

  const tekst = await tekstZDokumentu(pdf);
  if (czyMaTekst(tekst)) return { tekst, zrodlo: 'tekst' };

  postep?.('Plik to skan – przygotowuję strony do rozpoznania');
  const liczba = Math.min(pdf.numPages, MAKS_STRON_OCR);
  const strony: HTMLCanvasElement[] = [];
  for (let i = 1; i <= liczba; i++) strony.push(await renderujStrone(pdf, i));
  const { rozpoznaj } = await import('./ocr');
  const ocr = await rozpoznaj(strony, postep);
  return {
    tekst: normalizuj(ocr.tekst),
    zrodlo: 'ocr',
    pewnosc: ocr.pewnosc,
    pominieteStrony: pdf.numPages - liczba,
  };
}

/**
 * Poniżej tej średniej pewności OCR wynik to zwykle szum (pismo odręczne, zły skan) –
 * nie wypełniamy wtedy formularza automatycznie. Przykład z repo: wniosek odręczny ~25%, wydruk ~88%.
 */
export const MIN_PEWNOSC_OCR = 60;

export function czyOdczytWiarygodny(w: WynikOdczytu): boolean {
  return w.zrodlo === 'tekst' || (w.pewnosc ?? 0) >= MIN_PEWNOSC_OCR;
}

export function czyMaTekst(tekst: string): boolean {
  return tekst.replace(/\s/g, '').length >= MIN_ZNAKOW_TEKSTU;
}

async function renderujStrone(pdf: PDFDocumentProxy, nr: number): Promise<HTMLCanvasElement> {
  const strona = await pdf.getPage(nr);
  const viewport = strona.getViewport({ scale: SKALA_OCR });
  const canvas = document.createElement('canvas');
  canvas.width = Math.ceil(viewport.width);
  canvas.height = Math.ceil(viewport.height);
  const ctx = canvas.getContext('2d')!;
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  await strona.render({ canvas, canvasContext: ctx, viewport }).promise;
  return canvas;
}

type PdfJs = typeof import('pdfjs-dist');

export async function tekstZPdf(pdfjs: Pick<PdfJs, 'getDocument'>, dane: Uint8Array): Promise<string> {
  return tekstZDokumentu(await pdfjs.getDocument({ data: dane }).promise);
}

async function tekstZDokumentu(pdf: PDFDocumentProxy): Promise<string> {
  const strony: string[] = [];
  for (let i = 1; i <= pdf.numPages; i++) {
    const tresc = await (await pdf.getPage(i)).getTextContent();
    let linia = '';
    const linie: string[] = [];
    for (const el of tresc.items) {
      if (!('str' in el)) continue;
      linia += el.str;
      if (el.hasEOL) {
        linie.push(linia);
        linia = '';
      }
    }
    if (linia) linie.push(linia);
    strony.push(linie.join('\n'));
  }
  return normalizuj(strony.join('\n\n'));
}

export function normalizuj(t: string): string {
  return t.replace(/\r/g, '').replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
}

export interface Metadane {
  dataWplywu: string;
  wnioskodawca: string;
  kontakt: string;
  temat: string;
}

/** Heurystyczne wyciągnięcie metadanych – wynik zawsze trafia do formularza do zatwierdzenia. */
export function wyciagnijMetadane(tekst: string): Metadane {
  const linie = tekst.split('\n').map((l) => l.trim()).filter(Boolean);

  const email = tekst.match(/[\w.+-]+@[\w-]+(?:\.[\w-]+)+/)?.[0] ?? '';

  let wnioskodawca = '';
  const podpis = tekst.match(/(?:Z poważaniem|Z wyrazami szacunku|Pozdrawiam)[,\s]*\n\s*([^\n]{3,60})/i);
  if (podpis) wnioskodawca = podpis[1].split(/,|\s+tel\.|\s+e-mail/)[0].trim();
  if (!wnioskodawca) {
    const imie = linie.slice(0, 6).find((l) => /^\p{Lu}\p{Ll}+ \p{Lu}\p{Ll}+(?:-\p{Lu}\p{Ll}+)?$/u.test(l));
    if (imie) wnioskodawca = imie;
  }

  return {
    dataWplywu: dzisIso(),
    wnioskodawca,
    kontakt: email,
    temat: wyciagnijTemat(tekst),
  };
}

// Od najbardziej do najmniej charakterystycznych zwrotów, którymi wnioskodawcy zapowiadają przedmiot wniosku.
const ZWROTY_TEMATU = [
  /w zakresie\s*:?\s*([^.?!]{10,})/i,
  /na temat\s+([^.?!]{10,})/i,
  /informacji publicznej\s*:\s*([^.?!]{10,})/i,
  /zapytać\s+(?:o to\s*,?\s*)?([^.?!]{10,})/i,
  /(?:wnosz[eę]|wnosi(?:my)?|prosz[eę]|prosimy|prośbą)\s+o\s+(?!(?:przes|przys)[łl]anie\s+(?:pocztą|na adres|odpowiedzi))(?:udostępnienie\s+|przesłanie\s+)?(?:informacj[ięa]\s+)?(?:o\s+)?([^.?!]{10,})/i,
];
const POWITANIE = /^(dzień dobry|szanowni|szanowny|szanowna|wniosek o|biuro|urząd)/i;

// Skróty z kropką, które nie kończą zdania (np. „inwestycji pn. Budowa…”, „ul. Gdańskiej”).
const SKROTY = /\b(pn|ul|al|os|nr|im|tj|ok|godz|zm|poz|ust|pkt|art|dz|sp|św)\./gi;
const ZASLONA = '․'; // kropka zastępcza, przywracana na końcu

function wyciagnijTemat(tekst: string): string {
  return wyciagnijTematZaslonieta(tekst.replace(SKROTY, `$1${ZASLONA}`)).replaceAll(ZASLONA, '.');
}

function wyciagnijTematZaslonieta(tekst: string): string {
  const plaski = tekst.replace(/\s+/g, ' ');
  let zdanie = '';
  for (const wzorzec of ZWROTY_TEMATU) {
    const m = plaski.match(wzorzec);
    if (m) {
      zdanie = m[1].trim();
      break;
    }
  }
  if (!zdanie) {
    zdanie =
      tekst
        .split(/[\n.?!]+/)
        .map((s) => s.trim())
        .find((s) => s.split(' ').length >= 5 && !POWITANIE.test(s)) ?? plaski.slice(0, 120);
  }
  const krotko = zdanie.length > 90 ? zdanie.slice(0, 90).replace(/\s+\S*$/, '') + '…' : zdanie;
  return krotko.charAt(0).toUpperCase() + krotko.slice(1);
}
