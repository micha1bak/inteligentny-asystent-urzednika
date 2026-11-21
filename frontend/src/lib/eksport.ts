function pobierz(blob: Blob, nazwa: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = nazwa;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function nazwaPliku(numer: string, rozszerzenie: string): string {
  return `Odpowiedz - ${numer}.${rozszerzenie}`;
}

export function eksportujTxt(tekst: string, numer: string) {
  pobierz(new Blob([tekst.replace(/\n/g, '\r\n')], { type: 'text/plain;charset=utf-8' }), nazwaPliku(numer, 'txt'));
}

export async function eksportujDocx(tekst: string, numer: string) {
  const { Document, Packer, Paragraph, TextRun } = await import('docx');
  const doc = new Document({
    styles: { default: { document: { run: { font: 'Times New Roman', size: 24 } } } },
    sections: [
      {
        children: tekst.split('\n').map(
          (linia, i) =>
            new Paragraph({
              alignment: i === 0 ? 'right' : undefined,
              spacing: { after: 120 },
              children: [new TextRun(linia)],
            }),
        ),
      },
    ],
  });
  pobierz(await Packer.toBlob(doc), nazwaPliku(numer, 'docx'));
}
