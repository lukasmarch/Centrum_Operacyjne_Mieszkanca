import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronRight, Pause, Play } from 'lucide-react';
import { Article, HealthTodayResponse } from '../../types';
import type { OutageItem, OutageOutlook } from '../../src/hooks/useOutageOutlook';
import { parseUtc } from '../../src/utils/articleTime';
import { Tag, TagTone, dayWord, hourSpan, hm } from './tv';
import { healthChanges } from './HealthTodayCard';

/**
 * Pasek „Na żywo” — pierwsza linia pulpitu i miejsce na NAJŚWIEŻSZĄ sprawę gminy.
 *
 * Do 13.10.2026 cały biały pas należał do prądu i wody. Uwaga Łukasza: to pierwsza
 * linia, którą czytelnik ogląda — albo go zaciekawi, albo wyjdzie — a zapowiedź
 * wyłączenia za tydzień nie zaciekawia nikogo poza jedną wsią. Teraz pas to
 * MIGAWKI, które się podmieniają jak na pasku telewizji informacyjnej:
 *
 *   1. awaria w Twojej wsi TERAZ albo w ciągu doby (czerwień, zawsze pierwsza),
 *   2. zmiana w ośrodku zdrowia dziś („nie przyjmuje”) — dla wszystkich wsi,
 *   3. ogłoszenia sołtysów — dla wszystkich wsi, bo bal w Żabinach zainteresuje
 *      też kogoś z Rumiana; migawka mówi tylko „sołtys z X podał”, treść jest dalej,
 *   4. najświeższe wiadomości z gminy (np. OSiR).
 *
 * Prąd i woda nie znikają: żółty pasek pod spodem trzyma ich stan NA STAŁE,
 * także „bez zapowiedzianych wyłączeń” — to odpowiedź, której ktoś szuka
 * celowo, a nie migawka, która ma przyciągnąć.
 *
 * Ruch: przy wczytaniu pas rozwija się od lewej (klatki z TVN24, 13.10),
 * przy zmianie migawki tekst odsłania krawędź w kolorze plakietki. Bez ruchu
 * przy `prefers-reduced-motion`; rotację zatrzymuje najechanie, fokus,
 * schowana karta i przycisk pauzy (WCAG 2.2.2 — treść ruszająca się > 5 s).
 */

/** Ile godzin naprzód awaria jest „pilna” — ta sama skala co przypięcie feedu (30 h) z zapasem. */
const URGENT_H = 36;
/** Ile trwa jedna migawka */
const SLIDE_MS = 8000;
/** Ogłoszenie sołtysa jest „świeże” przez 5 dni — sołtysi piszą rzadko */
const SOLTYS_FRESH_H = 120;
/** Wiadomość z gminy jest migawką przez 36 h */
const NEWS_FRESH_H = 36;
const SOLECTWA_SOURCE = 'RybnoLive - Sołectwa';

const isUrgent = (item: OutageItem, now: Date) =>
    item.ongoing || (item.start !== null && item.start.getTime() - now.getTime() <= URGENT_H * 3_600_000);

/** „dziś 9:00–13:00”, a dla zgłoszenia bez terminu „zgłoszono 10:12”. */
const when = (item: OutageItem, now: Date): string => {
    if (item.start) return `${dayWord(item.start, now)} ${hourSpan(item.start, item.end)}`;
    if (item.reportedAt) return `zgłoszono ${dayWord(item.reportedAt, now) === 'dziś' ? '' : dayWord(item.reportedAt, now) + ' '}${hm(item.reportedAt)}`;
    return 'trwa';
};

const placesOf = (item: OutageItem) => (item.places.length ? item.places.join(', ') : 'gmina Rybno');

/** „Sołtys sołectwa Żabiny” → „Żabiny”; bez podpisu — pierwsza wieś z treści. */
const villageOfPost = (a: Article): string | null => {
    const m = (a.author ?? '').match(/so[łl]ectwa\s+(.+)$/i);
    return m?.[1]?.trim() || a.alertPlaces?.[0] || null;
};

/** Link do ogłoszenia jako ścieżka TEJ strony — `url` w bazie niesie host z chwili publikacji. */
const announcementPath = (url: string): string => {
    try {
        const u = new URL(url);
        return `${u.pathname}${u.search}`;
    } catch {
        return url;
    }
};

const ts = (iso: string): Date => parseUtc(iso) ?? new Date(0);
const hoursAgo = (iso: string, now: Date) => (now.getTime() - ts(iso).getTime()) / 3_600_000;

type SlideAction =
    | { kind: 'outage' }
    | { kind: 'health' }
    | { kind: 'href'; href: string }
    /** Źródło wpisu — nowa karta, strona zostaje otwarta */
    | { kind: 'external'; href: string }
    | { kind: 'news' };

interface Slide {
    key: string;
    tone: TagTone;
    tag: string;
    text: string;
    /** Co mówi link na końcu pasa — czytelnik ma wiedzieć, dokąd idzie */
    cta: string;
    action: SlideAction;
}

/** Klasa krawędzi odsłaniającej tekst — kolor plakietki migawki. */
const EDGE: Record<TagTone, string> = {
    red: 'bg-tv-red',
    yellow: 'bg-tv-yellow',
    blue: 'bg-tv-blue',
    paper: 'bg-tv-ink',
    seam: 'bg-tv-seam',
};

function buildSlides(
    outlook: OutageOutlook | null | undefined,
    village: string | null,
    health: HealthTodayResponse | null,
    articles: Article[],
    now: Date,
): Slide[] {
    const slides: Slide[] = [];
    const where = village ?? 'Gmina Rybno';

    // 1. Awaria TERAZ albo w ciągu doby — tylko ta, która dotyczy czytelnika
    const mine = outlook ? (village ? outlook.items.filter(i => i.concernsVillage) : outlook.items) : [];
    for (const item of mine.filter(i => isUrgent(i, now)).slice(0, 2)) {
        slides.push({
            key: `awaria-${item.id}`,
            tone: 'red',
            tag: `${where} · ${item.ongoing ? 'trwa teraz' : dayWord(item.start ?? now, now)}`,
            text: village ? `${item.label}: ${when(item, now)}` : `${item.label} — ${placesOf(item)}: ${when(item, now)}`,
            cta: 'sprawdź',
            // Czytelnik, który widzi wypadek, chce sprawdzić TEN wpis, nie ogólną listę
            action: item.url ? { kind: 'external', href: item.url } : { kind: 'outage' },
        });
    }

    // 2. Ośrodek zdrowia — tylko ZMIANA, nigdy stały grafik
    for (const change of healthChanges(health)) {
        slides.push({
            key: `zdrowie-${change.clinic}-${change.name}`,
            tone: 'yellow',
            tag: 'Ośrodek zdrowia · dziś',
            text: change.absent
                ? `Dziś nie przyjmuje: ${change.name || change.clinic}${change.name ? ` (${change.clinic})` : ''}`
                : `${change.clinic}${change.name ? ` · ${change.name}` : ''}: ${change.note}`,
            cta: 'sprawdź',
            action: { kind: 'health' },
        });
    }

    // 3. Sołtysi — dla wszystkich wsi, najświeższe pierwsze
    const posts = articles
        .filter(a => a.source === SOLECTWA_SOURCE && hoursAgo(a.rawTimestamp, now) <= SOLTYS_FRESH_H)
        .sort((a, b) => ts(b.rawTimestamp).getTime() - ts(a.rawTimestamp).getTime())
        .slice(0, 3);
    for (const a of posts) {
        const v = villageOfPost(a);
        slides.push({
            key: `soltys-${a.id}`,
            tone: 'blue',
            tag: v ? `Sołtys · ${v}` : 'Ogłoszenie sołectwa',
            text: a.title,
            cta: 'sprawdź',
            action: { kind: 'href', href: announcementPath(a.url) },
        });
    }

    // 4. Świeże wiadomości z gminy — bez awarii (mają pas niżej) i bez sołtysów (wyżej)
    const news = articles
        .filter(a =>
            a.scope === 'gmina'
            && a.source !== SOLECTWA_SOURCE
            && !a.isPinnedAlert
            && a.category !== 'Awaria'
            && hoursAgo(a.rawTimestamp, now) <= NEWS_FRESH_H,
        )
        .slice(0, 2);
    for (const a of news) {
        slides.push({
            key: `news-${a.id}`,
            tone: 'blue',
            tag: `${a.sourceLabel ?? 'Gmina Rybno'} · ${dayWord(ts(a.rawTimestamp), now)}`,
            text: a.title,
            cta: 'sprawdź',
            action: a.url ? { kind: 'external', href: a.url } : { kind: 'news' },
        });
    }

    return slides;
}

/** Żółty pasek: stan prądu i wody — zawsze, niezależnie od migawki. */
function outageLine(outlook: OutageOutlook | null, village: string | null, now: Date): React.ReactNode {
    if (outlook === null) {
        return <>Prąd i woda: <strong className="font-extrabold">nie udało się sprawdzić komunikatów</strong> — odśwież stronę za chwilę</>;
    }
    const where = village ?? 'gminie';
    const mine = village ? outlook.items.filter(i => i.concernsVillage) : outlook.items;
    const lead = mine.find(i => !isUrgent(i, now)) ?? null;
    const urgentShown = mine.some(i => isUrgent(i, now));

    if (lead) {
        return (
            <>
                Prąd i woda{village ? <> · {village}</> : ''}: <strong className="font-extrabold">{when(lead, now)}</strong>
                {' — '}{lead.label.toLowerCase()}{!village || lead.places.length > 1 ? <>, {placesOf(lead)}</> : null}
            </>
        );
    }
    const other = outlook.items.find(i => !(village && i.concernsVillage));
    if (urgentShown) {
        return other
            ? <>Prąd i woda, reszta gminy: <strong className="font-extrabold">{when(other, now)}</strong> — {other.label.toLowerCase()}, {placesOf(other)}</>
            : <>Prąd i woda: poza tym w gminie nic nie zapowiedziano na {outlook.windowDays} dni</>;
    }
    // Okno czasu W SAMYM zdaniu: „bez wyłączeń” bez zakresu brzmi jak gwarancja
    return (
        <>
            Prąd i woda {village ? <>w {where}</> : 'w gminie'}: <strong className="font-extrabold">najbliższe {outlook.windowDays} dni bez zapowiedzianych wyłączeń</strong>
            {other && <> · w gminie: {when(other, now)} — {other.label.toLowerCase()}, {placesOf(other)}</>}
        </>
    );
}

/** Żółty pasek, gdy biały pas sam mówi o prądzie i wodzie — nie powtarzamy zdania. */
function calmContext(outlook: OutageOutlook | null, village: string | null, now: Date): React.ReactNode {
    if (outlook === null) return 'Odśwież stronę za chwilę. Do tego czasu nie wiemy, czy coś zapowiedziano.';
    const other = outlook.items.find(i => !(village && i.concernsVillage));
    if (other) {
        return <>W gminie: <strong className="font-extrabold">{when(other, now)}</strong> — {other.label.toLowerCase()}, {placesOf(other)}</>;
    }
    return `${village ? 'W całej gminie' : 'W gminie'} nic więcej nie zapowiedziano na ${outlook.windowDays} dni`;
}

interface StatusBeltProps {
    outlook: OutageOutlook | null | undefined;
    village: string | null;
    health: HealthTodayResponse | null;
    articles: Article[];
    /** Obowiązujące ostrzeżenie meteo z feedu (przypięte, nie-awaria) */
    weatherWarning: Article | null;
    onOpenDetails: () => void;
    onOpenHealth: () => void;
    onOpenNews: () => void;
}

const StatusBelt: React.FC<StatusBeltProps> = ({
    outlook, village, health, articles, weatherWarning, onOpenDetails, onOpenHealth, onOpenNews,
}) => {
    const now = new Date();
    const slides = useMemo(
        () => buildSlides(outlook, village, health, articles, new Date()),
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [outlook, village, health, articles],
    );

    const [index, setIndex] = useState(0);
    const [paused, setPaused] = useState(false);
    // Najechanie i fokus zatrzymują rotację tylko na chwilę — pauza z przycisku na stałe
    const [hold, setHold] = useState(false);
    const [hidden, setHidden] = useState(typeof document !== 'undefined' && document.hidden);
    const rootRef = useRef<HTMLElement>(null);

    useEffect(() => {
        const onVis = () => setHidden(document.hidden);
        document.addEventListener('visibilitychange', onVis);
        return () => document.removeEventListener('visibilitychange', onVis);
    }, []);

    // Zbiór migawek zmienia się przy odświeżeniu danych — indeks nie może wyjść poza listę
    useEffect(() => {
        if (index >= slides.length) setIndex(0);
    }, [slides.length, index]);

    const running = slides.length > 1 && !paused && !hold && !hidden;

    useEffect(() => {
        if (!running) return;
        const timer = setTimeout(() => setIndex(i => (i + 1) % slides.length), SLIDE_MS);
        return () => clearTimeout(timer);
    }, [running, index, slides.length]);

    // Pierwsza klatka gra wjazd całego pasa; kolejne — tylko odsłonięcie tekstu
    const [entered, setEntered] = useState(false);
    useEffect(() => {
        const t = setTimeout(() => setEntered(true), 900);
        return () => clearTimeout(t);
    }, []);

    // Zanim przyjdzie odpowiedź o awariach — miejsce zarezerwowane, żeby
    // plakietki pod spodem nie skakały, gdy pas się pojawi
    if (outlook === undefined) {
        return (
            <section aria-label="Na żywo w gminie" aria-busy className="min-h-[148px]">
                <span className="block h-[29px] w-48 bg-tv-panel2" />
                <span className="block h-[84px] w-full bg-tv-panel" />
            </section>
        );
    }

    // Spokojny dzień bez żadnej migawki: pas mówi o prądzie i wodzie, jak dawniej
    const calm: Slide = {
        key: 'spokoj',
        tone: outlook === null ? 'seam' : 'blue',
        tag: `${village ?? 'Gmina Rybno'} · teraz`,
        text: outlook === null
            ? 'Nie udało się sprawdzić komunikatów o awariach'
            : `Najbliższe ${outlook.windowDays} dni: bez zapowiedzianych wyłączeń prądu i wody`,
        cta: '',
        action: { kind: 'outage' },
    };
    const list = slides.length ? slides : [calm];
    const slide = list[Math.min(index, list.length - 1)];
    const multi = list.length > 1;

    const act = () => {
        switch (slide.action.kind) {
            case 'outage': return onOpenDetails();
            case 'health': return onOpenHealth();
            case 'news': return onOpenNews();
            case 'href': window.location.href = slide.action.href; return;
            case 'external': window.open(slide.action.href, '_blank', 'noopener,noreferrer'); return;
        }
    };

    const checked = outlook?.checkedAt ? hm(outlook.checkedAt) : null;

    return (
        <section
            ref={rootRef}
            aria-label="Na żywo w gminie"
            aria-roledescription={multi ? 'karuzela' : undefined}
            className={entered ? '' : 'tv-belt-in'}
            onMouseEnter={() => setHold(true)}
            onMouseLeave={() => setHold(false)}
            onFocus={() => setHold(true)}
            onBlur={e => { if (!rootRef.current?.contains(e.relatedTarget as Node)) setHold(false); }}
        >
            <div className="flex items-end justify-between gap-2">
                <Tag tone={slide.tone} as="h2" className="tv-tag-in !py-1.5 !text-[14px]" key={`t-${slide.key}`}>
                    {slide.tag}
                </Tag>
                {multi && (
                    <div className="flex items-center gap-px">
                        <span className="tabular px-2 text-[14px] font-semibold text-tv-muted" aria-hidden>
                            {list.indexOf(slide) + 1}/{list.length}
                        </span>
                        <button
                            onClick={() => setPaused(p => !p)}
                            aria-label={paused ? 'Wznów przewijanie' : 'Zatrzymaj przewijanie'}
                            className="flex h-9 w-9 items-center justify-center bg-tv-panel text-tv-paper transition-colors hover:bg-tv-seam"
                        >
                            {paused ? <Play size={16} aria-hidden /> : <Pause size={16} aria-hidden />}
                        </button>
                        <button
                            onClick={() => setIndex(i => (i + 1) % list.length)}
                            aria-label="Następna wiadomość"
                            className="flex h-9 w-9 items-center justify-center bg-tv-panel text-tv-paper transition-colors hover:bg-tv-seam"
                        >
                            <ChevronRight size={18} aria-hidden />
                        </button>
                    </div>
                )}
            </div>

            <div className="relative overflow-hidden bg-tv-paper">
                <button
                    key={`b-${slide.key}`}
                    onClick={act}
                    aria-live={running ? 'off' : 'polite'}
                    className="tv-swap group relative block min-h-[84px] w-full px-4 py-3 text-left lg:min-h-[96px] lg:px-6 lg:py-5"
                >
                    <span className={`tv-swap-edge ${EDGE[slide.tone]}`} aria-hidden />
                    <span className="tv-swap-text font-cond line-clamp-2 block text-[24px] font-extrabold leading-[1.08] text-tv-ink sm:text-[30px] lg:line-clamp-1 lg:text-[42px]">
                        {slide.text}
                        {slide.cta && (
                            <span className="ml-2 inline-flex translate-y-[-0.15em] items-center whitespace-nowrap align-middle font-sans text-[15px] font-bold text-tv-blue underline-offset-4 group-hover:underline lg:text-[17px]">
                                {slide.cta}
                                <ChevronRight size={16} aria-hidden />
                            </span>
                        )}
                    </span>
                </button>
                {/* Ile zostało do następnej migawki — cienka linia, jak w telewizji */}
                {multi && (
                    <span
                        key={`p-${slide.key}-${running}`}
                        aria-hidden
                        className={`absolute bottom-0 left-0 h-[3px] ${slide.tone === "yellow" ? "bg-tv-ink" : EDGE[slide.tone]} ${running ? 'tv-progress' : 'w-0'}`}
                        style={running ? { animationDuration: `${SLIDE_MS}ms` } : undefined}
                    />
                )}
            </div>

            {outlook !== undefined && (
                <p className="bg-tv-yellow px-4 py-2 text-[15px] font-semibold leading-snug text-tv-ink lg:px-5">
                    {slides.length ? outageLine(outlook, village, now) : calmContext(outlook, village, now)}
                    {outlook && (
                        <span className="font-normal">
                            {' · '}wg Energi i ZGK{checked && <>, sprawdzone <span className="tabular">{checked}</span></>}
                        </span>
                    )}
                    {outlook && outlook.items.length > 0 && (
                        <>
                            {' · '}
                            <button
                                onClick={onOpenDetails}
                                className="font-extrabold underline underline-offset-2 hover:no-underline"
                            >
                                komunikaty
                            </button>
                        </>
                    )}
                </p>
            )}

            {weatherWarning && (
                <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1 bg-tv-panel px-4 py-2.5">
                    <Tag tone="yellow">Ostrzeżenie</Tag>
                    <p className="min-w-0 flex-1 text-[15px] font-semibold leading-snug text-white">
                        {weatherWarning.title}
                    </p>
                </div>
            )}
        </section>
    );
};

export default StatusBelt;
