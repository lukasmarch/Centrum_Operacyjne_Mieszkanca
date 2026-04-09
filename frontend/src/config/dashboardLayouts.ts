/**
 * Dashboard Layout Presets
 * Defines available tile configurations for the BentoGrid dashboard.
 */

export type TileId = 'ai_briefing' | 'weather' | 'traffic' | 'events' | 'airly' | 'gmina' | 'news';
export type DashboardLayoutId = 'klasyczny' | 'wiadomosci' | 'kompakt' | 'ai_focus';

export interface TileConfig {
  id: TileId;
  colSpan: 1 | 2 | 3 | 4;
  rowSpan?: 1 | 2;
  variant: 'glass' | 'gradient' | 'highlight' | 'dark';
}

export interface DashboardLayout {
  id: DashboardLayoutId;
  name: string;
  description: string;
  tiles: TileConfig[];
}

export const DASHBOARD_LAYOUTS: Record<DashboardLayoutId, DashboardLayout> = {
  /*
   * KLASYCZNY — zrównoważony: AI briefing + bogata pogoda + wiadomości lokalne
   *
   * Rząd 1: [ai_briefing c2   ] [weather c2 r2       ]
   * Rząd 2: [traffic c1][events c1][weather ciągnie r2]
   * Rząd 3: [airly c1][gmina c1][news c2              ]
   */
  klasyczny: {
    id: 'klasyczny',
    name: 'Klasyczny',
    description: 'AI briefing i rozbudowana pogoda u góry, wiadomości i dane lokalne poniżej',
    tiles: [
      { id: 'ai_briefing', colSpan: 2, variant: 'gradient' },
      { id: 'weather',     colSpan: 2, rowSpan: 2, variant: 'dark' },
      { id: 'traffic',     colSpan: 1, variant: 'glass' },
      { id: 'events',      colSpan: 1, variant: 'glass' },
      { id: 'airly',       colSpan: 1, variant: 'dark' },
      { id: 'gmina',       colSpan: 1, variant: 'dark' },
      { id: 'news',        colSpan: 2, variant: 'dark' },
    ],
  },

  /*
   * WIADOMOŚCI — informacje na pierwszym planie
   *
   * Rząd 1: [news                c4 (hero)              ]
   * Rząd 2: [ai_briefing c2  ] [events c1] [traffic c1  ]
   * Rząd 3: [weather c2      ] [airly c1 ] [gmina c1    ]
   */
  wiadomosci: {
    id: 'wiadomosci',
    name: 'Wiadomości',
    description: 'Newsy pełnej szerokości jako hero, AI i pogoda uzupełniają',
    tiles: [
      { id: 'news',        colSpan: 4, variant: 'highlight' },
      { id: 'ai_briefing', colSpan: 2, variant: 'gradient' },
      { id: 'events',      colSpan: 1, variant: 'glass' },
      { id: 'traffic',     colSpan: 1, variant: 'glass' },
      { id: 'weather',     colSpan: 2, variant: 'dark' },
      { id: 'airly',       colSpan: 1, variant: 'dark' },
      { id: 'gmina',       colSpan: 1, variant: 'dark' },
    ],
  },

  /*
   * KOMPAKT — gęsty, wszystko naraz, bez rozciągania
   *
   * Rząd 1: [ai_briefing c2  ] [weather c2          ]
   * Rząd 2: [traffic c1][events c1][airly c1][gmina c1]
   * Rząd 3: [news               c4                   ]
   */
  kompakt: {
    id: 'kompakt',
    name: 'Kompakt',
    description: 'Gęsty układ — wszystkie kafelki w równej wysokości, bez rozciągania',
    tiles: [
      { id: 'ai_briefing', colSpan: 2, variant: 'gradient' },
      { id: 'weather',     colSpan: 2, variant: 'dark' },
      { id: 'traffic',     colSpan: 1, variant: 'glass' },
      { id: 'events',      colSpan: 1, variant: 'glass' },
      { id: 'airly',       colSpan: 1, variant: 'dark' },
      { id: 'gmina',       colSpan: 1, variant: 'dark' },
      { id: 'news',        colSpan: 4, variant: 'dark' },
    ],
  },

  /*
   * AI FOCUS — briefing dominuje jako blok 2×2, dane na prawej i dole
   *
   * Rząd 1: [ai_briefing c2 r2    ] [weather c2         ]
   * Rząd 2: [ai_briefing ciągnie  ] [events c1][airly c1]
   * Rząd 3: [news c2              ] [traffic c1][gmina c1]
   */
  ai_focus: {
    id: 'ai_focus',
    name: 'AI Focus',
    description: 'AI briefing jako dominujący blok 2×2, dane poboczne na prawej i dole',
    tiles: [
      { id: 'ai_briefing', colSpan: 2, rowSpan: 2, variant: 'gradient' },
      { id: 'weather',     colSpan: 2, variant: 'dark' },
      { id: 'events',      colSpan: 1, variant: 'glass' },
      { id: 'airly',       colSpan: 1, variant: 'dark' },
      { id: 'news',        colSpan: 2, variant: 'dark' },
      { id: 'traffic',     colSpan: 1, variant: 'glass' },
      { id: 'gmina',       colSpan: 1, variant: 'dark' },
    ],
  },
};

export const DEFAULT_LAYOUT_ID: DashboardLayoutId = 'klasyczny';

export function getUserDashboardLayout(prefs: Record<string, unknown> | null): DashboardLayoutId {
  const val = prefs?.dashboard_layout;
  if (typeof val === 'string' && val in DASHBOARD_LAYOUTS) return val as DashboardLayoutId;
  return DEFAULT_LAYOUT_ID;
}
