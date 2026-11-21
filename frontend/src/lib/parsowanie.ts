// Odczyt tekstu z pliku PDF w przeglądarce – nic nie opuszcza komputera urzędnika.
import { dzisIso } from './daty';

export async function odczytajPdf(plik: File): Promise<string> {
  if (!plik.name.toLowerCase().endsWith('.pdf')) throw new Error('Wgraj plik w formacie PDF.');
  const pdfjs = await import('pdfjs-dist');
  const worker = await import('pdfjs-dist/build/pdf.worker.min.mjs?url');
  pdfjs.GlobalWorkerOptions.workerSrc = worker.default;
  return tekstZPdf(pdfjs, new Uint8Array(await plik.arrayBuffer()));
}

type PdfJs = typeof import('pdfjs-dist');

export async function tekstZPdf(pdfjs: Pick<PdfJs, 'getDocument'>, dane: Uint8Array): Promise<string> {
  const pdf = await pdfjs.getDocument({ data: dane }).promise;
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
  // Pusty wynik oznacza skan bez warstwy tekstowej – dane wpisuje wtedy urzędnik.
  return normalizuj(strony.join('\n\n'));
}

function normalizuj(t: string): string {
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
