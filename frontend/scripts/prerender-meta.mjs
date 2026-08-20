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

/**
 * Graf schema.org dla podstrony.
 *
 * `index.html` niesie jeden graf na cały serwis (WebSite + Organization) i do
 * 20.08.2026 był to JEDYNY strukturalny opis — identyczny na każdym adresie,
 * więc Google nie miał z niego jak odczytać, czym różni się `/kino` od `/cennik`.
 *
 * Każda podstrona dostaje teraz własny węzeł strony wpięty w `#website` przez
 * `isPartOf` oraz `BreadcrumbList` — to okruszki pokazują się w wyniku
 * wyszukiwania zamiast surowego adresu. `about` wskazuje gminę, bo to ona jest
 * tematem każdej z tych stron.
 *
 * Świadomie NIE opisujemy tu cen (`Offer`) ani pojedynczych artykułów
 * (`NewsArticle`): dane, które zmieniają się w bazie, a byłyby zamrożone
 * w buildzie, prędzej czy później zaczną kłamać. Te typy mają sens dopiero
 * z prerenderem czytającym API.
 */
const structuredData = (path, { title, description, short, type }) => {
    if (path === '/' || !short) return null;
    const url = `${BASE_URL}${path}`;
    return {
        '@context': 'https://schema.org',
        '@graph': [
            {
                '@type': type || 'WebPage',
                '@id': `${url}#webpage`,
                url,
                name: title,
                description,
                inLanguage: 'pl',
                isPartOf: { '@id': `${BASE_URL}/#website` },
                publisher: { '@id': `${BASE_URL}/#organization` },
                about: {
                    '@type': 'AdministrativeArea',
                    name: 'Gmina Rybno',
                    containedInPlace: { '@type': 'AdministrativeArea', name: 'Powiat Działdowski' },
                },
                breadcrumb: { '@id': `${url}#breadcrumb` },
            },
            {
                '@type': 'BreadcrumbList',
                '@id': `${url}#breadcrumb`,
                itemListElement: [
                    { '@type': 'ListItem', position: 1, name: 'RybnoLive', item: `${BASE_URL}/` },
                    { '@type': 'ListItem', position: 2, name: short, item: url },
                ],
            },
        ],
    };
};

/**
 * Treść dla czytelnika BEZ JavaScriptu.
 *
 * `index.html` ma jeden blok `<noscript>` z danymi usługodawcy — ten sam na
 * każdym adresie. Robot, który nie uruchamia skryptów (podgląd linku, część
 * crawlerów), widział więc na `/harmonogram-odpadow` nagłówek „RybnoLive.pl"
 * i adres firmy kamieniarskiej, a o odpadach ani słowa. Nagłówek dokumentu
 * mówił prawdę, ciało dokumentu nie mówiło nic.
 *
 * Podmieniamy w tym bloku `h1` i pierwszy akapit na tytuł i opis TEJ strony
 * oraz dokładamy spis pozostałych sekcji — bez niego robot bez JS nie ma jak
 * przejść dalej, bo cała nawigacja serwisu powstaje dopiero w React.
 *
 * To nie jest cloaking: `<noscript>` widzi każdy z wyłączonym JS, a treść
 * pokrywa się z tym, co mówi `title` i `description` tej samej strony.
 * Dane usługodawcy zostają — są wymagane i nie zależą od trasy.
 */
const noscriptFor = (path, { title, description }, allMeta) => {
    // Tytuł bez sufiksu marki — w treści strony powtarzanie „| RybnoLive" nic nie wnosi
    const heading = escapeHtml(title.replace(/\s*[|—-]\s*RybnoLive\s*$/, ''));
    const links = Object.entries(allMeta)
        .filter(([p, m]) => p !== path && m.short)
        .map(([p, m]) => `                <li><a href="${p}" style="color:#60a5fa">${escapeHtml(m.short)}</a></li>`)
        .join('\n');
    return { heading, description: escapeHtml(description), links };
};

let written = 0;
let withLd = 0;
for (const [path, entry] of Object.entries(meta)) {
    const { title, description } = entry;
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

    // Graf strony dokładany OBOK grafu serwisu z index.html — dwa bloki ld+json
    // w jednym dokumencie są dozwolone i czytelniejsze niż sklejanie ich w jeden
    const jsonLd = structuredData(path, entry);
    if (jsonLd) {
        html = html.replace(
            '</head>',
            `    <script type="application/ld+json">\n${JSON.stringify(jsonLd, null, 2)}\n    </script>\n</head>`,
        );
    }

    // Ciało dokumentu dla czytelnika bez JS — patrz `noscriptFor`
    {
        const { heading, description: desc, links } = noscriptFor(path, entry, meta);
        html = html.replace(
            '<h1>RybnoLive.pl — Centrum Operacyjne Mieszkańca</h1>',
            `<h1>${heading}</h1>`,
        );
        html = html.replace(
            '<p>Serwis wymaga włączonej obsługi JavaScript. Poniżej podstawowe informacje o usługodawcy.</p>',
            `<p>${desc}</p>\n            <p>Pełny serwis wymaga włączonej obsługi JavaScript. Pozostałe sekcje:</p>\n            <ul>\n${links}\n            </ul>\n            <p>Poniżej dane usługodawcy.</p>`,
        );
    }

    const outPath = path === '/'
        ? join(root, 'dist/index.html')
        : join(root, 'dist', path.replace(/^\//, ''), 'index.html');
    mkdirSync(dirname(outPath), { recursive: true });
    writeFileSync(outPath, html, 'utf-8');
    written += 1;
    if (jsonLd) withLd += 1;
}

console.log(`prerender-meta: ${written} tras z własnym title/description/canonical, ${withLd} z grafem schema.org`);
