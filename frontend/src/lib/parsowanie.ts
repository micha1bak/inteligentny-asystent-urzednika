// Odczyt tekstu z plików PDF/DOCX w przeglądarce – nic nie opuszcza komputera urzędnika.
import { dzisIso } from './daty';

export async function odczytajTekst(plik: File): Promise<string> {
  const nazwa = plik.name.toLowerCase();
  if (nazwa.endsWith('.txt')) return plik.text();
  if (nazwa.endsWith('.docx')) {
    const mammoth = await import('mammoth');
    const { value } = await mammoth.extractRawText({ arrayBuffer: await plik.arrayBuffer() });
    return normalizuj(value);
  }
  if (nazwa.endsWith('.pdf')) {
    const pdfjs = await import('pdfjs-dist');
    const worker = await import('pdfjs-dist/build/pdf.worker.min.mjs?url');
    pdfjs.GlobalWorkerOptions.workerSrc = worker.default;
    const pdf = await pdfjs.getDocument({ data: new Uint8Array(await plik.arrayBuffer()) }).promise;
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
    const tekst = normalizuj(strony.join('\n\n'));
    if (!tekst.trim()) {
      throw new Error('PDF nie zawiera warstwy tekstowej (skan). Rozpoznawanie OCR będzie po stronie serwera – na razie wklej treść ręcznie.');
    }
    return tekst;
  }
  throw new Error('Obsługiwane formaty: PDF, DOCX, TXT.');
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

const MIESIACE = ['stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca', 'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia'];

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

function wyciagnijTemat(tekst: string): string {
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

export function rozpoznajDateZTresci(tekst: string): string | undefined {
  const m = tekst.match(/(\d{1,2})\s+(\p{Ll}+)\s+(\d{4})\s*r/u);
  if (!m) return undefined;
  const mies = MIESIACE.indexOf(m[2]);
  if (mies < 0) return undefined;
  return `${m[3]}-${String(mies + 1).padStart(2, '0')}-${m[1].padStart(2, '0')}`;
}
