// Odczyt pliku wniosku (PDF, DOCX, skan) – przez moduł `konwersja` backendu (POST /api/konwersja):
// filtr pisma odręcznego, tekst z warstwy tekstowej PDF / DOCX, skany druku przepisywane przez model.
// Tutaj zostaje normalizacja tekstu i heurystyczne wyciągnięcie metadanych do formularza.
import { dzisIso } from './daty';
import { konwertujPlik, ROZSZERZENIA_WNIOSKU, type WynikKonwersji } from './api';

export type WynikOdczytu = WynikKonwersji;

export function czyObslugiwanyPlik(nazwa: string): boolean {
  const n = nazwa.toLowerCase();
  return ROZSZERZENIA_WNIOSKU.some((r) => n.endsWith(r));
}

export async function odczytajWniosek(plik: File, sygnal?: AbortSignal): Promise<WynikOdczytu> {
  if (!czyObslugiwanyPlik(plik.name)) throw new Error(`Nieobsługiwany format. Wgraj plik: ${ROZSZERZENIA_WNIOSKU.join(', ')}.`);
  const wynik = await konwertujPlik(plik, sygnal);
  return { ...wynik, tekst: normalizuj(wynik.tekst) };
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
  /w zakresie\s*:?\s*(?:1[.)]\s*|[-–•]\s*)?([^.?!]{10,})/i,
  /na temat\s+([^.?!]{10,})/i,
  /informacji publicznej\s*:\s*(?:1[.)]\s*|[-–•]\s*)?([^.?!]{10,})/i,
  /zapytać\s+(?:o to\s*,?\s*)?([^.?!]{10,})/i,
  /(?:wnosz[eę]|wnosi(?:my)?|prosz[eę]|prosimy|prośbą)\s+o\s*:?\s*(?!(?:przes|przys)[łl]anie\s+(?:pocztą|na adres|odpowiedzi))(?:udostępnienie\s+|przesłanie\s+|udzielenie\s+|podanie\s+)?(?:w\s+trybie\s+(?:ustawy\s+o\s+dostępie\s+do\s+)?informacji\s+publicznej\s+)?(?:(?:następujących|poniższych)\s+)?(?:informacj[ięa]|danych)?(?:\s+publiczn(?:ej|ych))?(?:\s+dotyczących|\s+o(?:\s+tym)?)?[\s,:–-]*(?:1[.)]\s*|[-–•]\s*)?(?:podanie\s+)?([^.?!]{10,})/i,
];
const POWITANIE = /^(dzień dobry|szanowni|szanowny|szanowna|wniosek o|biuro|urząd)/i;

// Skróty z kropką, które nie kończą zdania (np. „inwestycji pn. Budowa…”, „ul. Gdańskiej”, „2026 r.”).
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
      zdanie = m[1].replace(/^[\s,:;–-]+/, '').replace(/[,;:\s]+$/, '').trim();
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
  const krotko =
    zdanie.length > 90
      ? zdanie.slice(0, 90).replace(/\s+\S*$/, '').replace(/[,;:\s]+$/, '') + '…'
      : zdanie;
  return krotko.charAt(0).toUpperCase() + krotko.slice(1);
}
