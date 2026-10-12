/**
 * Kolory wykresów GUS z palety „Paska informacyjnego” (DESIGN.md, `--tv-*`).
 *
 * Recharts rysuje SVG i dostaje kolory atrybutem, więc trzymamy tu wartości
 * wprost, a nie klasy Tailwinda. Chaber = seria główna (gmina Rybno),
 * przygaszony = porównanie (powiat, inne gminy), szew = siatka osi.
 */
export const GUS_CHART = {
  series: '#1f4fff',
  seriesSoft: '#8fa8ff',
  compare: '#b4bbd0',
  paper: '#f5f6fa',
  muted: '#b4bbd0',
  seam: '#222b45',
  ink: '#0a0e1a',
  panel2: '#182036',
} as const;

/** Wspólny wygląd chmurki: płaski panel, szew 1 px, bez zaokrągleń i cienia */
export const TOOLTIP_CLASS = 'border border-tv-seam bg-tv-ink px-3 py-2.5';
