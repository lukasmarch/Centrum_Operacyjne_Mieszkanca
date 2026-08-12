/**
 * Meta per trasa — title, description i canonical.
 *
 * Treść meta żyje w `src/data/seoMeta.json`, bo czytają ją DWA miejsca: ten moduł
 * (przy nawigacji w aplikacji) i `scripts/prerender-meta.mjs` (po budowaniu wpisuje
 * je na stałe do HTML-a każdej trasy). Rozjazd tych dwóch źródeł oznaczałby, że
 * robot widzi inny tytuł niż człowiek — dlatego jest jeden plik, kluczowany ścieżką.
 *
 * Bez tego SPA pokazuje wszędzie jeden title, a canonical z index.html wskazywał "/"
 * nawet na /cennik (audyt 2026-08-06) — Google traktował podstrony jak duplikaty.
 */
import { AppSection } from '../types';
import seoMeta from './data/seoMeta.json';

const BASE_URL = 'https://rybnolive.pl';

type Meta = { title: string; description: string };
const META: Record<string, Meta> = seoMeta;

const setMeta = (name: string, content: string) => {
    const el = document.querySelector<HTMLMetaElement>(`meta[name="${name}"]`);
    if (el) el.content = content;
};

const setOg = (property: string, content: string) => {
    const el = document.querySelector<HTMLMetaElement>(`meta[property="${property}"]`);
    if (el) el.content = content;
};

/** Ustaw meta dla sekcji. `path` z SECTION_TO_PATH (App.tsx); brak ścieżki = strona główna. */
export const applySeo = (_section: AppSection, path: string | undefined) => {
    const key = path ?? '/';
    const meta = META[key] ?? META['/'];
    const canonical = `${BASE_URL}${key === '/' ? '/' : key}`;

    document.title = meta.title;
    setMeta('description', meta.description);
    setOg('og:title', meta.title);
    setOg('og:description', meta.description);
    setOg('og:url', canonical);

    let link = document.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!link) {
        link = document.createElement('link');
        link.rel = 'canonical';
        document.head.appendChild(link);
    }
    link.href = canonical;
};
