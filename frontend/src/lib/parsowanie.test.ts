// Odczyt prawdziwych (zanonimizowanych) wniosków PDF z katalogu repozytorium.
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import * as pdfjs from 'pdfjs-dist/legacy/build/pdf.mjs';
import { tekstZPdf, wyciagnijMetadane } from './parsowanie';

const KATALOG = join(__dirname, '../../../Przykładowe wnioski i odpowiedzi');
const pliki = readdirSync(KATALOG).filter((f) => f.startsWith('Wniosek') && f.endsWith('.pdf'));

describe('wnioski PDF', () => {
  it('są przykładowe pliki', () => expect(pliki.length).toBeGreaterThan(0));

  it.each(pliki)('%s – odczyt tekstu i tematu', async (plik: string) => {
    const tekst = await tekstZPdf(pdfjs, new Uint8Array(readFileSync(join(KATALOG, plik))));
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
