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
  klasyczny: {
    id: 'klasyczny',
    name: 'Klasyczny',
    description: 'Standardowy układ z AI briefingiem i ruchem drogowym na górze',
    tiles: [
      { id: 'ai_briefing', colSpan: 2, variant: 'gradient' },
      { id: 'weather',     colSpan: 1, variant: 'dark' },
      { id: 'traffic',     colSpan: 1, rowSpan: 2, variant: 'dark' },
      { id: 'events',      colSpan: 1, variant: 'glass' },
      { id: 'airly',       colSpan: 1, variant: 'dark' },
      { id: 'gmina',       colSpan: 1, variant: 'dark' },
      { id: 'news',        colSpan: 4, variant: 'dark' },
    ],
  },

  wiadomosci: {
    id: 'wiadomosci',
    name: 'Wiadomości',
    description: 'Wiadomości na pierwszym planie, AI briefing poniżej',
    tiles: [
      { id: 'news',        colSpan: 4, variant: 'dark' },
      { id: 'ai_briefing', colSpan: 2, variant: 'gradient' },
      { id: 'weather',     colSpan: 1, variant: 'dark' },
      { id: 'events',      colSpan: 1, variant: 'glass' },
      { id: 'traffic',     colSpan: 1, variant: 'dark' },
      { id: 'airly',       colSpan: 1, variant: 'dark' },
      { id: 'gmina',       colSpan: 2, variant: 'dark' },
    ],
  },

  kompakt: {
    id: 'kompakt',
    name: 'Kompakt',
    description: 'Zwarty układ bez rozciągniętych kafelków',
    tiles: [
      { id: 'weather',     colSpan: 1, variant: 'dark' },
      { id: 'airly',       colSpan: 1, variant: 'dark' },
      { id: 'events',      colSpan: 1, variant: 'glass' },
      { id: 'gmina',       colSpan: 1, variant: 'dark' },
      { id: 'ai_briefing', colSpan: 2, variant: 'gradient' },
      { id: 'news',        colSpan: 2, variant: 'dark' },
    ],
  },

  ai_focus: {
    id: 'ai_focus',
    name: 'AI Focus',
    description: 'AI briefing dominuje, reszta uzupełnia',
    tiles: [
      { id: 'ai_briefing', colSpan: 3, variant: 'gradient' },
      { id: 'weather',     colSpan: 1, variant: 'dark' },
      { id: 'news',        colSpan: 2, variant: 'dark' },
      { id: 'events',      colSpan: 1, variant: 'glass' },
      { id: 'airly',       colSpan: 1, variant: 'dark' },
      { id: 'traffic',     colSpan: 2, variant: 'dark' },
      { id: 'gmina',       colSpan: 2, variant: 'dark' },
    ],
  },
};

export const DEFAULT_LAYOUT_ID: DashboardLayoutId = 'klasyczny';

export function getUserDashboardLayout(prefs: Record<string, unknown> | null): DashboardLayoutId {
  const val = prefs?.dashboard_layout;
  if (typeof val === 'string' && val in DASHBOARD_LAYOUTS) return val as DashboardLayoutId;
  return DEFAULT_LAYOUT_ID;
}
