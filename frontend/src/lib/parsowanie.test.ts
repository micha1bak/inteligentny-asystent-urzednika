// Metadane z prawdziwych (zanonimizowanych) wniosków PDF z katalogu repozytorium.
// W aplikacji tekst odczytuje backend (moduł `konwersja`); tutaj warstwę tekstową czyta pdf.js tylko na potrzeby testu.
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import * as pdfjs from 'pdfjs-dist/legacy/build/pdf.mjs';
import { czyObslugiwanyPlik, normalizuj, wyciagnijMetadane } from './parsowanie';

async function tekstZPdf(dane: Uint8Array): Promise<string> {
  const pdf = await pdfjs.getDocument({ data: dane }).promise;
  const strony: string[] = [];
  for (let i = 1; i <= pdf.numPages; i++) {
    const tresc = await (await pdf.getPage(i)).getTextContent();
    strony.push(tresc.items.map((el) => ('str' in el ? el.str + (el.hasEOL ? '\n' : '') : '')).join(''));
  }
  return normalizuj(strony.join('\n\n'));
}

const KATALOG = join(__dirname, '../../../Przykładowe wnioski i odpowiedzi');
const pliki = readdirSync(KATALOG).filter((f) => f.startsWith('Wniosek') && f.endsWith('.pdf'));

describe('wnioski PDF', () => {
  it('są przykładowe pliki', () => expect(pliki.length).toBeGreaterThan(0));

  it.each(pliki)('%s – odczyt tekstu i tematu', async (plik: string) => {
    const tekst = await tekstZPdf(new Uint8Array(readFileSync(join(KATALOG, plik))));
    if (tekst === '') {
      // skan bez warstwy tekstowej – formularz zostaje do ręcznego uzupełnienia
      console.log(`${plik}: skan bez tekstu`);
      return;
    }
    expect(tekst.length).toBeGreaterThan(50);
    const m = wyciagnijMetadane(tekst);
    expect(m.temat.length).toBeGreaterThan(5);
    console.log(`${plik}\n  temat: ${m.temat}\n  wnioskodawca: ${m.wnioskodawca || '-'}  kontakt: ${m.kontakt || '-'}`);
  });
});

describe('metadane z treści', () => {
  it('wyciąga temat, podpis i e-mail', () => {
    const m = wyciagnijMetadane(
      'Dzień dobry, proszę o informację o liczbie drzew wyciętych w parkach miejskich w 2026 r. Z poważaniem\nMonika Testowa, tel. 600 100 200\nmonika@example.com',
    );
    expect(m.temat).toBe('Liczbie drzew wyciętych w parkach miejskich w 2026 r');
    expect(m.wnioskodawca).toBe('Monika Testowa');
    expect(m.kontakt).toBe('monika@example.com');
  });
});

describe('formaty plików', () => {
  it('przyjmuje formaty modułu konwersja', () => {
    expect(czyObslugiwanyPlik('Wniosek.PDF')).toBe(true);
    expect(czyObslugiwanyPlik('wniosek.docx')).toBe(true);
    expect(czyObslugiwanyPlik('skan.jpg')).toBe(true);
    expect(czyObslugiwanyPlik('wniosek.doc')).toBe(false);
  });
});
