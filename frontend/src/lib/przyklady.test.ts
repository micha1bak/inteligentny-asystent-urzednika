// Sprawdza parsowanie i podpowiedzi na prawdziwych (zanonimizowanych) wnioskach z katalogu repo.
import { readdirSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import mammoth from 'mammoth';
import { wyciagnijMetadane } from './parsowanie';
import { proponujWydzialy } from './wydzialy';
import { szukajPodobnych } from './podobienstwo';
import { ARCHIWUM_BAZOWE, JEDNOSTKI } from '../dane/referencje';

const KATALOG = join(__dirname, '../../../Przykładowe wnioski i odpowiedzi');
const pliki = readdirSync(KATALOG).filter((f) => f.startsWith('Wniosek') && f.endsWith('.docx'));

describe('przykładowe wnioski DOCX', () => {
  it.each(pliki)('%s – odczyt, temat, wydział, podobne', async (plik) => {
    const { value } = await mammoth.extractRawText({ path: join(KATALOG, plik) });
    expect(value.trim().length).toBeGreaterThan(50);
    const m = wyciagnijMetadane(value);
    expect(m.temat.length).toBeGreaterThan(5);
    const wydzialy = proponujWydzialy(value, JEDNOSTKI, ARCHIWUM_BAZOWE);
    const sygn = plik.match(/BKS\.IV\.1431\.\d+\.\d{4}/)![0];
    const podobne = szukajPodobnych(value, ARCHIWUM_BAZOWE.map((a) => ({ element: a, tekst: a.wniosek })), 3);
    console.log(`${sygn}\n  temat: ${m.temat}\n  wnioskodawca: ${m.wnioskodawca || '-'}\n  wydziały: ${wydzialy.map((w) => w.jednostka.symbol).join(', ')}\n  podobne: ${podobne.map((p) => p.element.sygnatura).join(', ')}`);
  });
});
