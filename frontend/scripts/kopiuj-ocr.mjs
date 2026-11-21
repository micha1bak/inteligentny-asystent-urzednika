// Kopiuje pliki OCR (worker, rdzeń WebAssembly, polski model) z node_modules do public/ocr,
// żeby aplikacja rozpoznawała skany bez dostępu do internetu.
import { copyFileSync, existsSync, mkdirSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const katalog = join(dirname(fileURLToPath(import.meta.url)), '..');
const nm = join(katalog, 'node_modules');
const cel = join(katalog, 'public', 'ocr');

const kopie = [
  [join(nm, 'tesseract.js/dist/worker.min.js'), join(cel, 'worker.min.js')],
  [join(nm, '@tesseract.js-data/pol/4.0.0_best_int/pol.traineddata.gz'), join(cel, 'lang/pol.traineddata.gz')],
  // tylko warianty LSTM – używamy wyłącznie silnika LSTM (OEM 1)
  ...readdirSync(join(nm, 'tesseract.js-core'))
    .filter((f) => f.startsWith('tesseract-core') && f.includes('lstm'))
    .map((f) => [join(nm, 'tesseract.js-core', f), join(cel, 'core', f)]),
];

for (const [z, d] of kopie) {
  if (!existsSync(z)) throw new Error(`Brak pliku ${z} – uruchom npm install`);
  mkdirSync(dirname(d), { recursive: true });
  copyFileSync(z, d);
}
console.log(`OCR: skopiowano ${kopie.length} plików do public/ocr`);
