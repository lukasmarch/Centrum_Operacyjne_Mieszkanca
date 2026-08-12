/**
 * Prerender meta: dla każdej znanej trasy zapisuje w `dist/` osobny index.html
 * z wpisanym na stałe tytułem, opisem i canonicalem.
 *
 * Po co, skoro aplikacja i tak ustawia meta w JS: robot, który NIE uruchamia
 * JavaScriptu — podgląd linku na Facebooku, część indeksów, crawlery modeli —
 * widział na każdej podstronie tytuł strony głównej i żadnego canonicala.
 * Kryterium z briefu („curl na /cennik zwraca własny canonical i title")
 * było przez to niespełnione. To NIE jest SSR: treść nadal renderuje aplikacja,
 * statyczny zostaje wyłącznie nagłówek dokumentu.
 *
 * Caddy musi umieć podać te pliki: `try_files {path} {path}/index.html /index.html`.
 *
 * Uruchamiane automatycznie po `npm run build` (skrypt `postbuild`).
 */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const BASE_URL = 'https://rybnolive.pl';

const meta = JSON.parse(readFileSync(join(root, 'src/data/seoMeta.json'), 'utf-8'));
const template = readFileSync(join(root, 'dist/index.html'), 'utf-8');

/** Podmiana wartości atrybutu w konkretnym znaczniku — bez ruszania reszty dokumentu. */
const replaceAttr = (html, selectorRe, value) =>
    html.replace(selectorRe, (match, before, _old, after) => `${before}${value}${after}`);

const escapeHtml = (text) =>
    text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

let written = 0;
for (const [path, { title, description }] of Object.entries(meta)) {
    const canonical = `${BASE_URL}${path === '/' ? '/' : path}`;
    const t = escapeHtml(title);
    const d = escapeHtml(description);

    let html = template
        .replace(/<title>[^<]*<\/title>/, `<title>${t}</title>`);

    html = replaceAttr(html, /(<meta name="description"\s+content=")([^"]*)(">)/, d);
    html = replaceAttr(html, /(<meta property="og:url"\s+content=")([^"]*)(">)/, canonical);

    // Strona główna zachowuje własne og:title („Twoja gmina. Na żywo.") — hasło marki
    // niesie się w feedzie lepiej niż długi tytuł pod wyszukiwarkę. Podstrony nie mają
    // swojego hasła, więc tam tytuł SEO jest lepszy niż powtórzony tytuł strony głównej.
    if (path !== '/') {
        html = replaceAttr(html, /(<meta property="og:title"\s+content=")([^"]*)(">)/, t);
        html = replaceAttr(html, /(<meta property="og:description"\s+content=")([^"]*)(">)/, d);
        html = replaceAttr(html, /(<meta name="twitter:title"\s+content=")([^"]*)(">)/, t);
        html = replaceAttr(html, /(<meta name="twitter:description"\s+content=")([^"]*)(">)/, d);
    }

    // Canonical nie istnieje w szablonie (usunięty, bo sztywny wskazywał "/")
    html = html.replace('</head>', `    <link rel="canonical" href="${canonical}">\n</head>`);

    const outPath = path === '/'
        ? join(root, 'dist/index.html')
        : join(root, 'dist', path.replace(/^\//, ''), 'index.html');
    mkdirSync(dirname(outPath), { recursive: true });
    writeFileSync(outPath, html, 'utf-8');
    written += 1;
}

console.log(`prerender-meta: ${written} tras z własnym title/description/canonical`);
