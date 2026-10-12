import React from 'react';
import {
    AlertTriangle, Briefcase, Bus, CalendarDays, ChevronDown, ChevronRight, GraduationCap, HeartPulse,
    Home, Landmark, Newspaper, Palette, ShieldAlert, Trees, Trophy, Users, type LucideIcon,
} from 'lucide-react';
import type { Article } from '../../types';
import { parseUtc } from '../../src/utils/articleTime';

/**
 * Elementy „Paska informacyjnego” (odświeżenie 10.2026) — wspólne dla pulpitu.
 *
 * Język wzięty z grafiki telewizji informacyjnej: PLAKIETKA tematu (wąskie
 * wersaliki na pełnym kolorze) nad PASEM treści. Kąty proste, bez cieni
 * i poświaty; podziały to szew 1 px. Kolor plakietki niesie znaczenie
 * i nic poza nim: chaber = temat, czerwień = awaria teraz/jutro,
 * żółć = kontekst albo zapowiedź, papier = rzecz neutralna.
 */

export type TagTone = 'blue' | 'red' | 'yellow' | 'paper' | 'seam';

const TAG_TONES: Record<TagTone, string> = {
    blue: 'bg-tv-blue text-white',
    red: 'bg-tv-red text-white',
    yellow: 'bg-tv-yellow text-tv-ink',
    paper: 'bg-tv-paper text-tv-ink',
    seam: 'bg-tv-seam text-tv-paper',
};

interface TagProps {
    tone?: TagTone;
    children: React.ReactNode;
    className?: string;
    as?: 'span' | 'h2' | 'h3';
}

/** Plakietka tematu. Jako `h2`/`h3` jest nagłówkiem sekcji, nie ozdobnikiem nad nim. */
export const Tag: React.FC<TagProps> = ({ tone = 'blue', children, className = '', as: El = 'span' }) => (
    <El
        className={`font-cond inline-block max-w-full self-start px-2.5 py-1 text-[13px] font-extrabold uppercase leading-none tracking-wide ${TAG_TONES[tone]} ${className}`}
    >
        {children}
    </El>
);

interface PlateProps {
    tag: React.ReactNode;
    tagTone?: TagTone;
    value: React.ReactNode;
    sub?: React.ReactNode;
    onClick?: () => void;
    ariaLabel?: string;
    children?: React.ReactNode;
}

/**
 * Plakietka z wartością — kafel „Na dziś”. Wartość to odpowiedź (termin, godzina,
 * temperatura) w wąskim grubym kroju; zdanie pod nią dopowiada szczegół.
 * Cały kafel jest jednym przyciskiem, gdy prowadzi dalej.
 */
export const Plate: React.FC<PlateProps> = ({ tag, tagTone = 'blue', value, sub, onClick, ariaLabel, children }) => {
    const body = (
        <>
            <Tag tone={tagTone}>{tag}</Tag>
            <span className="flex w-full flex-1 flex-col bg-tv-panel px-3.5 pb-3.5 pt-3">
                <span className="font-cond tabular text-[26px] font-extrabold leading-[1.05] text-white lg:text-[30px]">
                    {value}
                </span>
                {sub && <span className="mt-1.5 text-[15px] leading-snug text-tv-muted">{sub}</span>}
                {children}
            </span>
        </>
    );

    if (!onClick) return <div className="flex min-w-0 flex-col items-start">{body}</div>;

    return (
        <button
            onClick={onClick}
            aria-label={ariaLabel}
            className="group flex min-w-0 flex-col items-start text-left transition-colors [&>span:last-child]:w-full [&>span:last-child]:transition-colors hover:[&>span:last-child]:bg-tv-panel2"
        >
            {body}
        </button>
    );
};

interface RowLinkProps {
    onClick: () => void;
    children: React.ReactNode;
    className?: string;
}

/** Link tekstowy „dalej” w kolorze chabru — jeden wygląd w całym pulpicie. */
export const RowLink: React.FC<RowLinkProps> = ({ onClick, children, className = '' }) => (
    <button
        onClick={onClick}
        className={`inline-flex min-h-[44px] items-center gap-1 text-[15px] font-bold text-tv-bluesoft underline-offset-4 transition-colors hover:text-white hover:underline ${className}`}
    >
        {children}
        <ChevronRight size={16} aria-hidden />
    </button>
);

const WEEKDAYS_SHORT = ['nd', 'pn', 'wt', 'śr', 'czw', 'pt', 'sb'];

const hm = (d: Date) => d.toLocaleTimeString('pl-PL', { hour: 'numeric', minute: '2-digit' });

const dayDiff = (d: Date, now: Date) => {
    const a = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    const b = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    return Math.round((a - b) / 86_400_000);
};

/** „dziś”, „jutro”, „wt 14.10” — słowo dnia liczone od lokalnej doby. */
export const dayWord = (d: Date, now = new Date()): string => {
    const diff = dayDiff(d, now);
    if (diff === 0) return 'dziś';
    if (diff === 1) return 'jutro';
    return `${WEEKDAYS_SHORT[d.getDay()]} ${d.getDate()}.${String(d.getMonth() + 1).padStart(2, '0')}`;
};

/** Zakres godzin zdarzenia: „9:00–13:00”, a bez końca sama godzina startu. */
export const hourSpan = (start: Date, end: Date | null): string =>
    end ? `${hm(start)}–${hm(end)}` : `od ${hm(start)}`;

export { hm };

/* ── Klocki podstron (etap 2 odświeżenia, 11.10.2026) ─────────────────────── */

interface PageHeadProps {
    title: React.ReactNode;
    /** Jedno zdanie: czego dotyczy strona albo stan danych („sprawdzone 20:24”) */
    sub?: React.ReactNode;
    /** Prawa strona główki: wybór, przełącznik, licznik */
    aside?: React.ReactNode;
}

/**
 * Główka podstrony — ten sam układ co główka pulpitu (`Masthead`): tytuł wąskim
 * krojem, pod nim jedno zdanie, szew na dole. Bez kickerów i gradientu tekstu.
 */
export const PageHead: React.FC<PageHeadProps> = ({ title, sub, aside }) => (
    <header className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2 border-b border-tv-seam pb-3">
        <div className="min-w-0">
            <h1 className="font-cond text-[26px] font-extrabold leading-tight text-white lg:text-[34px]">{title}</h1>
            {sub && <p className="mt-0.5 text-[15px] leading-snug text-tv-muted">{sub}</p>}
        </div>
        {aside}
    </header>
);

interface ChipProps {
    active?: boolean;
    onClick: () => void;
    children: React.ReactNode;
    count?: number;
    /** Czerwień tylko dla filtra awarii — kolor = stan */
    alert?: boolean;
}

/** Filtr: kwadratowy przycisk 44 px. Aktywny = papier (jak pozycja nawigacji). */
export const Chip: React.FC<ChipProps> = ({ active = false, onClick, children, count, alert = false }) => (
    <button
        onClick={onClick}
        aria-pressed={active}
        className={`font-cond inline-flex min-h-[44px] items-center gap-2 whitespace-nowrap px-3 text-[15px] font-bold uppercase tracking-wide transition-colors ${
            active
                ? alert ? 'bg-tv-red text-white' : 'bg-tv-paper text-tv-ink'
                : 'bg-tv-panel text-tv-paper hover:bg-tv-panel2 hover:text-white'
        }`}
    >
        {children}
        {count !== undefined && (
            <span className={`tabular text-[13px] font-extrabold ${active ? 'opacity-70' : 'text-tv-muted'}`}>{count}</span>
        )}
    </button>
);

/** Stan pusty / błąd / informacja — zdanie w panelu, nigdy emoji ani ilustracja. */
export const Notice: React.FC<{ tone?: 'plain' | 'warn'; children: React.ReactNode; role?: string }> = ({
    tone = 'plain', children, role,
}) => (
    <p
        role={role}
        className={`px-4 py-3 text-[15px] leading-snug ${
            tone === 'warn' ? 'bg-tv-yellow text-tv-ink' : 'bg-tv-panel text-tv-paper'
        }`}
    >
        {children}
    </p>
);

/** Szkielet ładowania: bloki panelu, bez pulsującej poświaty i zaokrągleń. */
export const Skeleton: React.FC<{ className?: string }> = ({ className = 'h-20' }) => (
    <div aria-hidden className={`animate-pulse bg-tv-panel2 ${className}`} />
);

/**
 * Czerwony kwadrat awarii przy wpisie — tylko gdy to sprawa czytelnika TERAZ:
 * awaria, którą backend przypina (`is_pinned_alert`: najbliższe godziny, gmina),
 * i która dotyczy jego wsi. Zapowiedź za trzy dni albo wyłączenie w cudzej wsi
 * stało do 11.10.2026 na czerwono pod belką mówiącą „bez wyłączeń” (Red Is Rare).
 */
export const isRedAlert = (a: Article): boolean =>
    (a.category || '').toLowerCase().includes('awari') && !!a.isPinnedAlert && a.concernsLocation !== false;

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
    children: React.ReactNode;
}

/**
 * Pole wyboru: 52 px, obrys 2 px szwu, własny chevron (systemowy select na iOS
 * ma zaokrąglone rogi i połysk). Jedna postać dla Odpadów, Pogody, push i profilu.
 */
export const Select: React.FC<SelectProps> = ({ children, className = '', ...rest }) => (
    <span className={`relative block ${className}`}>
        <select
            {...rest}
            className="min-h-[52px] w-full appearance-none border-2 border-tv-seam bg-tv-panel py-2 pl-3 pr-10 text-[16px] font-semibold text-tv-paper transition-colors focus:border-tv-paper disabled:opacity-60"
        >
            {children}
        </select>
        <ChevronDown size={18} aria-hidden className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-tv-muted" />
    </span>
);

/* ── Kwadrat wpisu: zdjęcie → tablica z terminem → piktogram kategorii ─────── */
/*
 * Krytyka 11.10.2026 (Wiadomości/Wydarzenia, 23/36): 16 z 16 wpisów miało
 * w kwadracie tę samą szarą gazetę — czytaną jak niezaładowany obrazek. Zdjęć
 * nie pobieramy, a generowana ilustracja udawałaby kadr z miejsca zdarzenia
 * („prawda albo nic”). Kwadrat niesie więc INFORMACJĘ: termin, gdy wpis go ma
 * (kolor = stan), a bez terminu rodzaj sprawy piktogramem.
 */

const CATEGORY_GLYPHS: Record<string, LucideIcon> = {
    awaria: AlertTriangle,
    sport: Trophy,
    kultura: Palette,
    bezpieczenstwo: ShieldAlert,
    spolecznosc: Users,
    urzad: Landmark,
    edukacja: GraduationCap,
    transport: Bus,
    biznes: Briefcase,
    rekreacja: Trees,
    zdrowie: HeartPulse,
    nieruchomosci: Home,
    wydarzenia: CalendarDays,
};

const flatKey = (s?: string | null) =>
    (s || '').toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/ł/g, 'l').trim();

/** Piktogram kategorii — ikona z jednej biblioteki, jedna grubość kreski. */
export const categoryGlyph = (category?: string | null): LucideIcon =>
    CATEGORY_GLYPHS[flatKey(category)] ?? Newspaper;

const MONTHS_SHORT = ['sty', 'lut', 'mar', 'kwi', 'maj', 'cze', 'lip', 'sie', 'wrz', 'paź', 'lis', 'gru'];

export type BoardTone = 'red' | 'yellow' | 'blue' | 'quiet';

const BOARD_TONES: Record<BoardTone, string> = {
    red: 'bg-tv-red text-white',
    yellow: 'bg-tv-yellow text-tv-ink',
    blue: 'bg-tv-blue text-white',
    quiet: 'bg-tv-panel2 text-tv-paper',
};

interface EntrySquareProps {
    imageUrl?: string;
    /** Termin zdarzenia — tablica zamiast piktogramu */
    when?: Date | null;
    /** Wpis całodniowy: bez godziny na tablicy */
    allDay?: boolean;
    tone?: BoardTone;
    category?: string | null;
    className?: string;
}

/**
 * Kwadrat obok wpisu. Kolejność: zdjęcie (prawdziwe) → tablica z terminem
 * („14 / PAŹ / 9:00”) w kolorze stanu → piktogram kategorii na panelu.
 */
export const EntrySquare: React.FC<EntrySquareProps> = ({
    imageUrl, when, allDay = false, tone = 'quiet', category, className = 'h-16 w-16 sm:h-20 sm:w-20',
}) => {
    const [broken, setBroken] = React.useState(false);
    if (imageUrl && !broken) {
        return (
            <span className={`block shrink-0 overflow-hidden bg-tv-panel2 ${className}`}>
                <img src={imageUrl} alt="" loading="lazy" onError={() => setBroken(true)} className="h-full w-full object-cover" />
            </span>
        );
    }
    if (when) {
        return (
            <span aria-hidden className={`font-cond flex shrink-0 flex-col items-center justify-center leading-none ${BOARD_TONES[tone]} ${className}`}>
                <span className="tabular text-[24px] font-extrabold sm:text-[30px]">{when.getDate()}</span>
                <span className="mt-0.5 text-[13px] font-extrabold uppercase tracking-wide">{MONTHS_SHORT[when.getMonth()]}</span>
                {!allDay && <span className="tabular mt-1 text-[13px] font-bold opacity-90">{hm(when)}</span>}
            </span>
        );
    }
    const Glyph = categoryGlyph(category);
    return (
        <span aria-hidden className={`flex shrink-0 items-center justify-center bg-tv-panel2 text-tv-paper ${className}`}>
            <Glyph size={26} strokeWidth={1.75} />
        </span>
    );
};

/** Termin wpisu i kolor tablicy. Kolor = stan: awaria teraz czerwona, zapowiedź
 *  żółta, trwające dziś chabrowe, miniony termin wycofany na panel. */
export function boardOf(article: Article, now = new Date()): { when: Date | null; allDay: boolean; tone: BoardTone } {
  const when = parseUtc(article.eventAt);
  if (!when) return { when: null, allDay: false, tone: 'quiet' };
  const until = parseUtc(article.eventUntil);
  const allDay = !until && when.getHours() === 0 && when.getMinutes() === 0;
  const end = until ?? new Date(when.getTime() + (allDay ? 24 : 3) * 3_600_000);
  if (isRedAlert(article)) return { when, allDay, tone: 'red' };
  if (now < when) return { when, allDay, tone: 'yellow' };
  if (now <= end) return { when, allDay, tone: 'blue' };
  return { when, allDay, tone: 'quiet' };
}

