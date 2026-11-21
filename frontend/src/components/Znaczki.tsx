import type { Status } from '../types';
import { etykietaStatusu } from '../types';
import { OPIS_PILNOSCI, opisPozostalo, type Pilnosc } from '../lib/terminy';

export function ZnaczekStatusu({ status, dniKwerendy }: { status: Status; dniKwerendy?: number }) {
  return (
    <span className={`znaczek s-${status}`}>
      {etykietaStatusu(status)}
      {status === 'kwerenda' && dniKwerendy ? ` +${dniKwerendy} dni` : ''}
    </span>
  );
}

export function Pozostalo({ pilnosc, pozostalo }: { pilnosc: Pilnosc; pozostalo: number }) {
  if (pilnosc === 'zakonczony') return <span className="maly">—</span>;
  return (
    <span className={`pil-${pilnosc}`} title={OPIS_PILNOSCI[pilnosc]}>
      {opisPozostalo(pozostalo)}
    </span>
  );
}
