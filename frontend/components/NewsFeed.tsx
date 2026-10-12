import React, { useState, useMemo, useEffect } from 'react';
import StaleDataNotice from './StaleDataNotice';
import { ChevronDown, ExternalLink } from 'lucide-react';
import { useArticles } from '../src/hooks/useArticles';
import { Chip, EntrySquare, Notice, PageHead, Skeleton, Tag, boardOf } from './simple/tv';
import { useMyVillage } from '../src/hooks/useMyVillage';
import AlertPushPrompt from './AlertPushPrompt';
import { Article } from '../types';
import { fetchActiveAnnouncements, ActiveAnnouncement } from '../src/services/businessApi';
import { useAuth } from '../src/context/AuthContext';

interface NewsFeedProps {
  initialCategory?: string;
}

// Do 3.09.2026 feed grupował po DACIE publikacji („Dzisiaj / Wczoraj / Starsze").
// Wszystko lokalne wchodzi rano z WCZORAJSZĄ datą (Facebook przez Apify raz
// dziennie o 6:00), a RSS-y z powiatu publikują w ciągu dnia — więc sekcję
// „Dzisiaj" otwierały zawsze trzy obce wpisy (Władysławowo, Mławka, Strzegowo),
// choć ranking miał je na 5., 11. i 15. miejscu. Data każdego wpisu została
// na plakietce; sekcje mówią teraz, CZYJA to sprawa. Kolejność wewnątrz sekcji
// to ranking z backendu (`feed_policy.article_score`).
const SCOPE_GROUPS = ['gmina', 'okolice', 'region'] as const;
type ScopeGroup = typeof SCOPE_GROUPS[number];

const SCOPE_GROUP_LABELS: Record<ScopeGroup, string> = {
  gmina: 'Gmina Rybno',
  okolice: 'Powiat i sąsiedzi',
  region: 'Dalej w regionie',
};


/** Wieś z gminy wymieniona we wpisie — plakietka, nie szara meta (najwyżej dwie). */
// „Rybno” odejmujemy, gdy obok pada inna wieś: każdy komunikat Energi niesie
// „Rybno gmina wiejska”, więc plakietka RYBNO stała przy co drugim wpisie
// (ta sama reguła co `alert_policy.same_incident`)
const placesOf = (article: Article): string[] => {
  const all = article.alertPlaces ?? [];
  const rest = all.filter(p => p !== 'Rybno');
  return (rest.length ? rest : all).slice(0, 2);
};

/** Meta jednym ciągiem: kategoria · czas · źródło ↗ (13 px, przygaszona). */
const Meta: React.FC<{ article: Article; withCategory?: boolean }> = ({ article, withCategory = true }) => (
  <p className="text-[13px] leading-snug text-tv-muted">
    {/* „Wiadomości” jako kategoria w zakładce Wiadomości to tautologia */}
    {withCategory && article.category && article.category !== 'Wiadomości' && (
      <><span className="font-bold text-tv-paper">{article.category}</span>{' · '}</>
    )}
    {/* Etykietę składa `useArticles` przez `utils/articleTime` — dla
        zapowiedzi liczy się TERMIN, nie wiek ogłoszenia */}
    <span className="tabular">{article.timestamp}</span>
    {article.sourceLabel && <> · {article.sourceLabel}</>}
  </p>
);

/** Tytuł jest linkiem do źródła — osobny wiersz „Czytaj u źródła” kosztował 44 px na wpis. */
const TitleLink: React.FC<{ article: Article; className: string }> = ({ article, className }) => (
  <a
    href={article.url}
    target="_blank"
    // Przy prywatnych profilach FB nie pokazujemy nazwy (sourceLabel === null),
    // ale link zostaje — to atrybucja, a mieszkaniec i tak chce doczytać oryginał
    rel={article.sourceLabel ? 'noopener noreferrer' : 'noopener noreferrer nofollow'}
    className={`group/t block underline-offset-4 hover:underline ${className}`}
  >
    {article.title}
    <ExternalLink size={14} aria-hidden className="ml-1.5 inline-block align-[-1px] text-tv-muted group-hover/t:text-white" />
    <span className="sr-only"> (otwiera się w nowej karcie u źródła)</span>
  </a>
);

/**
 * Pełny wpis — sekcja „Gmina Rybno”. Kwadrat (zdjęcie → tablica z terminem →
 * piktogram), plakietka wsi, meta, tytuł-link, wypis najwyżej 2 linie.
 * Do 11.10.2026 wiersz miał ~10 linii i ~255 px — na telefonie 360 px
 * mieściły się 2 wpisy, a pierwszy zaczynał się pod zgięciem (krytyka 23/36).
 */
const ArticleRow: React.FC<{ article: Article; span?: boolean }> = ({ article, span = false }) => {
  const board = boardOf(article);
  const places = placesOf(article);
  const hasSummary = article.summary && article.summary !== 'Brak opisu';
  return (
    <article className={`flex gap-3 bg-tv-panel p-3 sm:gap-4 sm:p-4 ${span ? 'lg:col-span-2' : ''}`}>
      <EntrySquare
        imageUrl={article.imageUrl}
        when={board.when}
        allDay={board.allDay}
        tone={board.tone}
        category={article.category}
      />
      <div className="min-w-0 flex-1">
        {places.length > 0 && (
          <div className="mb-1 flex flex-wrap gap-1">
            {places.map(p => <Tag key={p} tone="paper">{p}</Tag>)}
          </div>
        )}
        <Meta article={article} />
        <TitleLink article={article} className="mt-0.5 line-clamp-3 text-[17px] font-semibold leading-snug text-white" />
        {hasSummary && (
          <p className="mt-1 line-clamp-2 max-w-[68ch] text-[15px] leading-snug text-[#d7dbe8]">{article.summary}</p>
        )}
      </div>
    </article>
  );
};

/** Zwarty wpis — powiat i region: sama meta i tytuł. Sprawa sąsiadów nie
 *  waży tyle co sprawa gminy (PRODUCT.md, zasada 1). */
const CompactRow: React.FC<{ article: Article }> = ({ article }) => (
  <li className="bg-tv-panel px-3 py-2.5 sm:px-4">
    <Meta article={article} />
    <TitleLink article={article} className="mt-0.5 line-clamp-2 text-[16px] font-semibold leading-snug text-white" />
  </li>
);

const NewsFeed: React.FC<NewsFeedProps> = ({ initialCategory }) => {
  // Wieś czytelnika — tylko po to, by backend powiedział, czy awaria go dotyczy
  // (`concerns_location`); bez niej każda awaria świeciłaby na czerwono
  const { village } = useMyVillage();
  const { articles, loading, error, fetchedAt } = useArticles({ limit: 50, perSource: 5, location: village });
  const [activeCategory, setActiveCategory] = useState<string>(initialCategory || 'Wszystkie');
  const [regionOpen, setRegionOpen] = useState(false);
  const [announcements, setAnnouncements] = useState<ActiveAnnouncement[]>([]);

  // Reklamy widzi wyłącznie plan darmowy — cennik sprzedaje ich brak w planach
  // płatnych. Do 21.08.2026 bramkę miał tylko `AdBoard` na stronie głównej (i tylko
  // dla `premium`), więc płacący widział ogłoszenia w feedzie mimo obietnicy,
  // a firma za 49 zł/mc — mimo pozycji „Wszystko z planu Premium".
  const { user } = useAuth();
  const hidesAds = user?.tier === 'premium' || user?.tier === 'business';

  useEffect(() => {
    if (hidesAds) return;
    fetchActiveAnnouncements(4).then(setAnnouncements).catch(() => {});
  }, [hidesAds]);

  // Category counts
  const categoryCounts = useMemo(() => {
    if (!articles) return {} as Record<string, number>;
    const counts: Record<string, number> = {};
    articles.forEach(a => {
      const cat = a.category || 'Inne';
      counts[cat] = (counts[cat] || 0) + 1;
    });
    return counts;
  }, [articles]);

  // Czy w feedzie stoi awaria — od tego zależy, czy w ogóle pytamy o zgodę na push
  const hasAwaria = useMemo(
    () => (articles || []).some(a => (a.category || '').toLowerCase().includes('awari')),
    [articles]
  );

  // Sorted categories: Awaria first, then by count desc
  const sortedCategories = useMemo(() => {
    if (!articles) return [];
    return Object.entries(categoryCounts)
      .sort((a, b) => {
        const aIsAwaria = a[0].toLowerCase().includes('awari');
        const bIsAwaria = b[0].toLowerCase().includes('awari');
        if (aIsAwaria && !bIsAwaria) return -1;
        if (!aIsAwaria && bIsAwaria) return 1;
        return b[1] - a[1];
      })
      .map(([cat]) => cat);
  }, [categoryCounts, articles]);


  // Filtered articles
  const filteredArticles = useMemo(() => {
    if (!articles) return [];

    if (activeCategory !== 'Wszystkie') {
      return articles.filter(a => a.category === activeCategory);
    }

    // Widok "Wszystkie" = kolejność z backendu. Do 11.10.2026 front przeplatał
    // tu kategorie (po jednym wpisie z każdej na rundę) i niszczył ranking:
    // na szczyt sekcji „Powiat i sąsiedzi" trafiał wpis bez kategorii, a lokalny
    // z czołówki spadał o kilka miejsc (audyt F-011). Różnorodność robi już
    // `diversify` w backendzie — druga polityka we froncie tylko ją psuła.
    return articles;
  }, [articles, activeCategory]);

  // Schema.org ItemList — inject JSON-LD into <head> for Google rich results
  useEffect(() => {
    if (!filteredArticles || filteredArticles.length === 0) return;
    const schemaId = 'schema-news-list';
    let el = document.getElementById(schemaId) as HTMLScriptElement | null;
    if (!el) {
      el = document.createElement('script');
      el.id = schemaId;
      el.type = 'application/ld+json';
      document.head.appendChild(el);
    }
    const items = filteredArticles.slice(0, 20).map((a, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      item: {
        '@type': 'NewsArticle',
        headline: a.title,
        url: a.url,
        datePublished: a.rawTimestamp || a.timestamp,
        image: a.imageUrl || 'https://rybnolive.pl/og-image.jpg',
        publisher: {
          '@type': 'Organization',
          name: 'RybnoLive',
          logo: { '@type': 'ImageObject', url: 'https://rybnolive.pl/og-image.jpg' },
        },
      },
    }));
    el.textContent = JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'ItemList',
      name: 'Aktualności Gminy Rybno',
      itemListElement: items,
    });
    return () => { el?.remove(); };
  }, [filteredArticles]);

  // Sekcje po zasięgu, kolejność wewnątrz = ranking z backendu
  const groupedArticles = useMemo(() => {
    const groups: Record<ScopeGroup, Article[]> = { gmina: [], okolice: [], region: [] };
    filteredArticles.forEach(a => {
      groups[a.scope ?? 'region'].push(a);
    });
    return groups;
  }, [filteredArticles]);

  if (loading) return (
    <div className="space-y-6" aria-busy="true">
      <PageHead title="Wiadomości" sub="Wczytuję…" />
      <div className="flex gap-1.5">
        {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-11 w-24" />)}
      </div>
      <div className="grid grid-cols-1 gap-px bg-tv-seam lg:grid-cols-2">
        {[1, 2, 3, 4, 5, 6].map(i => <Skeleton key={i} className="h-36" />)}
      </div>
    </div>
  );

  // Błąd bez żadnych danych — przy danych lista zostaje, a nad nią `StaleDataNotice`
  if (error && !articles) return (
    <div className="space-y-6">
      <PageHead title="Wiadomości" />
      <Notice tone="warn" role="alert">Nie udało się pobrać wiadomości. Sprawdź połączenie i spróbuj za chwilę.</Notice>
    </div>
  );
  if (!articles || articles.length === 0) return (
    <div className="space-y-6">
      <PageHead title="Wiadomości" />
      <Notice>W ostatnich dniach nie pojawiła się żadna wiadomość z gminy ani okolicy.</Notice>
    </div>
  );

  return (
    <div className="space-y-5 lg:space-y-8">
      <PageHead
        title="Wiadomości"
        sub={<>Najpierw gmina Rybno, potem powiat i region. <span className="tabular">{filteredArticles.length}</span> {filteredArticles.length === 1 ? 'wpis' : 'wpisów'}{activeCategory !== 'Wszystkie' && <> w kategorii „{activeCategory}”</>}.</>}
      />
      {error && <StaleDataNotice fetchedAt={fetchedAt} />}

      {/* Filtry w JEDNYM rzędzie przewijanym w poziomie (telefon), od `lg` zawijane.
          Trzy rzędy chipów (~150 px) spychały pierwszą wiadomość pod zgięcie */}
      <div
        role="group"
        aria-label="Kategorie"
        className="no-scrollbar -mx-4 flex gap-1.5 overflow-x-auto px-4 md:-mx-8 md:px-8 lg:mx-0 lg:flex-wrap lg:overflow-visible lg:px-0"
      >
        <Chip active={activeCategory === 'Wszystkie'} onClick={() => setActiveCategory('Wszystkie')} count={articles.length}>
          Wszystkie
        </Chip>
        {sortedCategories.map(cat => {
          const isAwaria = cat.toLowerCase().includes('awari');
          return (
            <Chip
              key={cat}
              active={activeCategory === cat}
              alert={isAwaria}
              onClick={() => setActiveCategory(cat)}
              count={categoryCounts[cat] || 0}
            >
              {cat}
            </Chip>
          );
        })}
      </div>

      {/* Sekcje po zasięgu. Gmina — pełne wpisy; powiat — zwarta lista;
          region — zwarty i domyślnie zwinięty (kto z Rybna przewija do Mławy?) */}
      {SCOPE_GROUPS.map(group => {
        const groupArticles = groupedArticles[group];
        if (groupArticles.length === 0) return null;
        const isGmina = group === 'gmina';
        const collapsed = group === 'region' && !regionOpen;
        return (
          <React.Fragment key={group}>
            <section aria-label={SCOPE_GROUP_LABELS[group]}>
              <div className="flex items-baseline gap-3">
                <Tag as="h2" tone={isGmina ? 'blue' : 'seam'}>{SCOPE_GROUP_LABELS[group]}</Tag>
                <span className="tabular text-[14px] text-tv-muted">{groupArticles.length}</span>
              </div>
              {isGmina ? (
                <div className="grid grid-cols-1 gap-px border-t-2 border-tv-blue bg-tv-seam lg:grid-cols-2">
                  {/* Nieparzysta liczba: ostatni wpis na całą szerokość — inaczej od `lg` zostaje pusta komórka w kolorze szwu */}
                  {groupArticles.map((article, i) => (
                    <ArticleRow key={article.id} article={article} span={groupArticles.length % 2 === 1 && i === groupArticles.length - 1} />
                  ))}
                </div>
              ) : collapsed ? (
                <button
                  onClick={() => setRegionOpen(true)}
                  aria-expanded={false}
                  className="flex min-h-[48px] w-full items-center justify-between border-t border-tv-seam bg-tv-panel px-4 text-left text-[15px] font-bold text-tv-bluesoft transition-colors hover:bg-tv-panel2 hover:text-white"
                >
                  Pokaż {groupArticles.length} {groupArticles.length === 1 ? 'wpis' : groupArticles.length < 5 ? 'wpisy' : 'wpisów'} z dalszych okolic
                  <ChevronDown size={18} aria-hidden />
                </button>
              ) : (
                <ul className="grid grid-cols-1 gap-px border-t border-tv-seam bg-tv-seam lg:grid-cols-2 [&>li:last-child:nth-child(odd)]:lg:col-span-2">
                  {groupArticles.map(article => <CompactRow key={article.id} article={article} />)}
                </ul>
              )}
            </section>

            {/* Zgoda na powiadomienia — pod sprawami gminy, nie nad nimi: najpierw
                czytelnik widzi awarię, potem pytamy, czy chce o następnej wiedzieć */}
            {isGmina && hasAwaria && <AlertPushPrompt />}
          </React.Fragment>
        );
      })}

      {/* Ogłoszenia firm (plan Firma lokalna) — pod treścią gminną, pod plakietką
          „Reklama” jak na pulpicie (`AdBoard`): reklama jest gościem, nie nagłówkiem */}
      {announcements.length > 0 && (
        <section aria-label="Reklama">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <Tag as="h2" tone="seam">Reklama</Tag>
            <span className="text-[15px] text-tv-muted">ogłoszenia firm z gminy</span>
          </div>
          <div className="grid grid-cols-1 gap-px border-t border-tv-seam bg-tv-seam md:grid-cols-2">
            {announcements.map(a => (
              <div key={a.id} className="bg-tv-panel p-4">
                <div className="mb-1 flex items-start justify-between gap-3">
                  <p className="text-[16px] font-bold leading-snug text-white">{a.title}</p>
                  {a.type === 'okazja' && a.valid_until && (
                    <span className="font-cond tabular whitespace-nowrap bg-tv-yellow px-2 py-1 text-[13px] font-extrabold uppercase leading-none text-tv-ink">
                      do {new Date(a.valid_until).toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' })}
                    </span>
                  )}
                </div>
                <p className="text-[15px] leading-snug text-[#d7dbe8]">{a.body}</p>
                <p className="mt-2 text-[13px] text-tv-muted">
                  {a.nazwa} · {a.miasto}
                  {a.telefon && <> · <a href={`tel:${a.telefon.replace(/\s/g, '')}`} className="tabular font-semibold text-tv-bluesoft underline underline-offset-2 hover:text-white">{a.telefon}</a></>}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      {filteredArticles.length === 0 && (
        <Notice>Brak wpisów w kategorii „{activeCategory}”.</Notice>
      )}
    </div>
  );
};

export default NewsFeed;
