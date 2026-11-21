import type { Wniosek } from '../types';
import { formatujSlownie } from './daty';
import { jednostka } from '../dane/referencje';

/**
 * Szablon projektu pisma. Złożony regułowo z odpowiedzi wydziałów – bez modelu językowego,
 * więc nie ma ryzyka halucynacji. Miejsca do uzupełnienia są oznaczone [[…]].
 * Backend może później podmienić to na redakcję przez lokalny LLM (te same dane wejściowe).
 */
export function generujProjekt(w: Wniosek, dzis: string): string {
  const odpowiedzi = w.odpowiedzi.length
    ? w.odpowiedzi
        .map((o, i) => {
          const nazwa = jednostka(o.wydzial)?.nazwa ?? o.wydzial;
          const tresc = oczyscOdpowiedz(o.tresc);
          return w.odpowiedzi.length > 1 ? `${i + 1}. Według informacji przekazanych przez ${nazwa}: ${tresc}` : tresc;
        })
        .join('\n\n')
    : '[[Brak odpowiedzi wydziałów – wgraj odpowiedzi albo uzupełnij treść ręcznie]]';

  return `Bydgoszcz, ${formatujSlownie(dzis)}

${w.numer}

${w.wnioskodawca || '[[Wnioskodawca]]'}
${w.kontakt ?? '[[adres do doręczeń / e-mail]]'}

Dotyczy: wniosku o udostępnienie informacji publicznej z dnia ${formatujSlownie(w.dataWplywu)}

W odpowiedzi na wniosek z dnia ${formatujSlownie(w.dataWplywu)} o udostępnienie informacji publicznej w zakresie: ${w.temat.charAt(0).toLowerCase() + w.temat.slice(1)}, działając na podstawie art. 10 ust. 1 i art. 13 ust. 1 ustawy z dnia 6 września 2001 r. o dostępie do informacji publicznej (t.j. Dz. U. z 2022 r. poz. 902 ze zm.), uprzejmie informuję, co następuje.

${odpowiedzi}

Jednocześnie informuję, że zasady udostępniania informacji publicznej w Urzędzie Miasta Bydgoszczy oraz klauzula informacyjna dotycząca przetwarzania danych osobowych są dostępne w Biuletynie Informacji Publicznej Urzędu Miasta Bydgoszczy.

Z poważaniem

[[imię i nazwisko, stanowisko osoby upoważnionej]]
`;
}

/** Usuwa z odpowiedzi wydziału zwroty wewnętrzne („W odpowiedzi na zapytanie BKS…”). */
function oczyscOdpowiedz(t: string): string {
  return t
    .trim()
    .replace(/^W odpowiedzi na zapytanie BKS\s*,?\s*(informujemy|informuję),?\s*(że)?\s*/i, '')
    .replace(/^(\p{Ll})/u, (c) => c.toUpperCase());
}

export function brakujacePola(tekst: string): string[] {
  return [...tekst.matchAll(/\[\[([^\]]+)\]\]/g)].map((m) => m[1]);
}
