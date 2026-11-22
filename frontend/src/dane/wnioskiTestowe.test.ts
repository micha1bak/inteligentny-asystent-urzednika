import { describe, expect, it } from 'vitest';
import { wnioskiTestowe } from './wnioskiTestowe';
import { najblizszyRoboczy, terminOdpowiedzi } from '../lib/terminy';

describe('wnioski testowe', () => {
  // dzień roboczy, piątek, niedziela, dzień wolny (Wigilia)
  for (const dzis of ['2026-11-23', '2026-11-27', '2026-11-22', '2026-12-24']) {
    it(`najbliższy termin wypada dziś lub w najbliższy dzień roboczy (${dzis})`, () => {
      const wnioski = wnioskiTestowe(dzis);
      const terminy = wnioski.map((w) => terminOdpowiedzi(w)).sort();
      expect(wnioski).toHaveLength(10);
      expect(terminy[0]).toBe(najblizszyRoboczy(dzis));
      expect(wnioski.every((w) => w.status === 'brak_dzialan' && w.dataWplywu <= dzis)).toBe(true);
    });
  }
});
