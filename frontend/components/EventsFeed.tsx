import React, { useState, useMemo } from 'react';
import StaleDataNotice from './StaleDataNotice';
import { ChevronDown, ChevronUp, MapPin, Clock, Calendar } from 'lucide-react';
import { useEvents } from '../src/hooks/useEvents';
import { TimedEvent, endOf, isAllDay, phaseOf } from '../src/utils/eventTime';
import { Event } from '../types';

/* ── Category chip / badge colors ── */
const CATEGORY_CHIP: Record<string, { active: string; dot: string; badge: string }> = {
    kultura:   { active: 'bg-violet-600/20 text-violet-300 border-violet-500/30',  dot: 'bg-violet-400',  badge: 'bg-violet-600/30 text-violet-300 border-violet-500/30' },
    sport:     { active: 'bg-orange-600/20 text-orange-300 border-orange-500/30',  dot: 'bg-orange-400',  badge: 'bg-orange-600/30 text-orange-300 border-orange-500/30' },
    rozrywka:  { active: 'bg-pink-600/20 text-pink-300 border-pink-500/30',         dot: 'bg-pink-400',    badge: 'bg-pink-600/30 text-pink-300 border-pink-500/30' },
    społeczne: { active: 'bg-emerald-600/20 text-emerald-300 border-emerald-500/30', dot: 'bg-emerald-400', badge: 'bg-emerald-600/30 text-emerald-300 border-emerald-500/30' },
    edukacja:  { active: 'bg-cyan-600/20 text-cyan-300 border-cyan-500/30',          dot: 'bg-cyan-400',    badge: 'bg-cyan-600/30 text-cyan-300 border-cyan-500/30' },
    koncert:   { active: 'bg-rose-600/20 text-rose-300 border-rose-500/30',          dot: 'bg-rose-400',    badge: 'bg-rose-600/30 text-rose-300 border-rose-500/30' },
    festiwal:  { active: 'bg-fuchsia-600/20 text-fuchsia-300 border-fuchsia-500/30', dot: 'bg-fuchsia-400', badge: 'bg-fuchsia-600/30 text-fuchsia-300 border-fuchsia-500/30' },
    targi:     { active: 'bg-amber-600/20 text-amber-300 border-amber-500/30',       dot: 'bg-amber-400',   badge: 'bg-amber-600/30 text-amber-300 border-amber-500/30' },
};

const DEFAULT_CHIP = {
    active: 'bg-blue-600/20 text-blue-300 border-blue-500/30',
    dot: 'bg-blue-400',
    badge: 'bg-blue-600/30 text-blue-300 border-blue-500/30',
};

function getCategoryChip(cat: string) {
    const key = cat.toLowerCase();
    for (const [k, v] of Object.entries(CATEGORY_CHIP)) {
        if (key.includes(k) || k.includes(key)) return v;
    }
    return DEFAULT_CHIP;
}

/* ── Google Calendar ── */
// Wpis całodniowy idzie jako DZIEŃ (YYYYMMDD/następny dzień), nie jako
// 00:00–02:00 — tak wpadał do kalendarza mieszkańca do 11.10.2026 (audyt F-038).
// Koniec z `endOf`: ta sama reguła co kafle (podany koniec albo 2 h).
function generateGoogleCalendarUrl(event: TimedEvent): string {
    const start = new Date(event.date);
    let dates: string;
    if (isAllDay(event)) {
        const day = (d: Date) =>
            `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
        const next = new Date(start);
        next.setDate(next.getDate() + 1);
        dates = `${day(start)}/${day(next)}`;
    } else {
        const fmt = (d: Date) => d.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
        dates = `${fmt(start)}/${fmt(endOf(event))}`;
    }
    const params = new URLSearchParams({
        action: 'TEMPLATE',
        text: event.title,
        dates,
        details: event.description || '',
        location: event.location || '',
    });
    return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

/* ── Month group helpers ── */
const MONTH_NAMES = [
    'Styczeń', 'Luty', 'Marzec', 'Kwiecień', 'Maj', 'Czerwiec',
    'Lipiec', 'Sierpień', 'Wrzesień', 'Październik', 'Listopad', 'Grudzień',
];

function getMonthKey(dateStr: string): string {
    const d = new Date(dateStr);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function getMonthLabel(key: string): string {
    const [year, month] = key.split('-');
    const now = new Date();
    const label = `${MONTH_NAMES[parseInt(month) - 1]} ${year}`;
    if (parseInt(year) === now.getFullYear() && parseInt(month) === now.getMonth() + 1) {
        return `${label} — ten miesiąc`;
    }
    return label;
}

/* ── Single event card ── */
/**
 * Karta wydarzenia — układ pod telefon 375 px (audyt V13, F-043).
 *
 * Do 11.10.2026 w jednym wierszu stały: data, miniatura, treść i przycisk
 * „Google Cal”, więc na tytuł zostawało 54 px, a terminy i źródło miały
 * 7–11 px przy kontraście 1,9–2,5:1 — „kiedy” i „skąd” były nieczytelne
 * dla starszych mieszkańców. Do tego cała karta była linkiem z przyciskiem
 * w środku (zagnieżdżone elementy interaktywne).
 * Dziś: górny wiersz to data + treść (miniatura dopiero od `sm`), dolny —
 * źródło i „Dodaj do kalendarza”; linkiem jest tytuł. Metadane ≥ 13 px.
 */
const EventCard: React.FC<{ event: TimedEvent }> = ({ event }) => {
    const d = new Date(event.date);
    const chip = getCategoryChip(event.category || '');
    const timeStr = isAllDay(event)
        ? 'cały dzień'
        : d.toLocaleTimeString('pl-PL', { hour: 'numeric', minute: '2-digit' });

    return (
        <div className="group rounded-2xl border border-white/5 bg-gray-900/40 p-4 transition-all hover:border-white/10 hover:bg-gray-900/60">
            <div className="flex gap-3 sm:gap-4">
                {/* Data — pierwsze, czego szuka się w kalendarzu */}
                <div className="flex h-16 w-14 shrink-0 flex-col items-center justify-center rounded-xl border border-white/10 bg-white/5">
                    <span className="text-xs font-bold uppercase leading-none text-neutral-300">
                        {d.toLocaleDateString('pl-PL', { month: 'short' }).replace('.', '')}
                    </span>
                    <span className="my-0.5 text-2xl font-black leading-none text-neutral-100">
                        {d.getDate()}
                    </span>
                    <span className="text-xs font-medium leading-none text-neutral-400">
                        {d.toLocaleDateString('pl-PL', { weekday: 'short' }).replace('.', '')}
                    </span>
                </div>

                <div className="min-w-0 flex-1">
                    {event.category && (
                        <span className={`mb-1 inline-block rounded border px-1.5 py-0.5 text-xs font-bold uppercase tracking-wide ${chip.badge}`}>
                            {event.category}
                        </span>
                    )}
                    <h4 className="mb-1.5 text-base font-bold leading-snug text-neutral-100">
                        {event.externalUrl ? (
                            <a
                                href={event.externalUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="transition-colors hover:text-blue-300"
                            >
                                {event.title}
                            </a>
                        ) : event.title}
                    </h4>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-neutral-300">
                        <span className="flex items-center gap-1">
                            <Clock size={13} className="shrink-0 text-neutral-400" aria-hidden />
                            {timeStr}
                        </span>
                        {event.location && (
                            <span className="flex min-w-0 items-center gap-1">
                                <MapPin size={13} className="shrink-0 text-neutral-400" aria-hidden />
                                <span className="truncate">{event.location}</span>
                            </span>
                        )}
                    </div>
                    {event.description && (
                        <p className="mt-1.5 line-clamp-2 text-sm text-neutral-400">{event.description}</p>
                    )}
                </div>

                {/* Miniatura poza kolumną tekstu: na telefonie jej nie ma —
                    zabierała tytułowi 56 px z i tak wąskiego wiersza */}
                {event.imageUrl && (
                    <div className="hidden h-16 w-16 shrink-0 overflow-hidden rounded-xl border border-white/5 sm:block">
                        <img
                            src={event.imageUrl}
                            alt=""
                            className="h-full w-full object-cover"
                            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                        />
                    </div>
                )}
            </div>

            <div className="mt-3 flex items-center justify-between gap-3 border-t border-white/5 pt-2">
                <p className="min-w-0 truncate text-[13px] text-neutral-400">
                    {event.sourceName && (
                        <>Źródło: <span className="font-medium text-neutral-300">{event.sourceName}</span></>
                    )}
                </p>
                <a
                    href={generateGoogleCalendarUrl(event)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex min-h-[40px] shrink-0 items-center gap-1.5 rounded-lg px-2 text-[13px] font-semibold text-blue-300 transition-colors hover:bg-blue-500/10 hover:text-blue-200"
                >
                    <Calendar size={14} aria-hidden />
                    Dodaj do kalendarza
                </a>
            </div>
        </div>
    );
};

/* ── Main Component ── */
const VISIBLE_CHIPS = 5;

const EventsFeed: React.FC<{ initialCategory?: string }> = ({ initialCategory }) => {
    const { events: allEvents, loading, error, fetchedAt } = useEvents(100);
    // „Nadchodzące” bez tego, co już się skończyło (audyt F-038). API oddaje
    // wydarzenia od początku dzisiejszej doby — kafle strony głównej potrzebują
    // porannych, żeby powiedzieć „dziś już po wszystkim”. Koniec liczy `endOf`,
    // ta sama reguła co backend (`time_span.event_end`). `fetchedAt` w zależnościach:
    // lista przelicza się z każdym odświeżeniem, więc 10:00 nie wisi do wieczora
    const events = useMemo(
        () => (allEvents ? allEvents.filter(e => phaseOf(e) !== 'past') : null),
        [allEvents, fetchedAt],
    );
    const [activeCategory, setActiveCategory] = useState<string>(initialCategory || 'Wszystkie');
    const [chipsExpanded, setChipsExpanded] = useState(false);

    const categoryCounts = useMemo(() => {
        if (!events) return {} as Record<string, number>;
        const counts: Record<string, number> = {};
        events.forEach(e => {
            const cat = e.category || 'Inne';
            counts[cat] = (counts[cat] || 0) + 1;
        });
        return counts;
    }, [events]);

    const sortedCategories = useMemo(() => {
        return Object.entries(categoryCounts)
            .sort((a, b) => (b[1] as number) - (a[1] as number))
            .map(([cat]) => cat);
    }, [categoryCounts]);

    const visibleCategories = chipsExpanded ? sortedCategories : sortedCategories.slice(0, VISIBLE_CHIPS);
    const overflowCount = Math.max(0, sortedCategories.length - VISIBLE_CHIPS);

    // Filter & dedupe
    const filteredEvents = useMemo(() => {
        if (!events) return [];
        let filtered = events;
        if (activeCategory !== 'Wszystkie') {
            filtered = events.filter(e => e.category === activeCategory);
        }
        return filtered.filter((ev, i, arr) =>
            i === arr.findIndex(t =>
                t.title === ev.title &&
                new Date(t.date).toDateString() === new Date(ev.date).toDateString()
            )
        );
    }, [events, activeCategory]);

    // Group events by month
    const groupedEvents = useMemo(() => {
        const groups: Record<string, Event[]> = {};
        filteredEvents.forEach(ev => {
            const key = getMonthKey(ev.date);
            if (!groups[key]) groups[key] = [];
            groups[key].push(ev);
        });
        return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
    }, [filteredEvents]);

    if (loading) return (
        <div className="space-y-4">
            <div className="h-8 w-56 bg-gray-900/50 rounded-xl animate-pulse" />
            <div className="h-10 bg-gray-900/30 rounded-xl animate-pulse" />
            {[1, 2, 3].map(i => (
                <div key={i} className="h-24 bg-gray-900/30 rounded-2xl animate-pulse" />
            ))}
        </div>
    );

    // Błąd bez żadnych danych — przy danych lista zostaje, a nad nią `StaleDataNotice`
    if (error && !events) return <div className="text-center p-8 text-neutral-400">Nie udało się pobrać wydarzeń. Sprawdź połączenie i spróbuj za chwilę.</div>;
    if (!events || events.length === 0) return (
        <div className="text-center p-12 text-neutral-500">
            <div className="text-4xl mb-3">📅</div>
            Brak nadchodzących wydarzeń.
        </div>
    );

    return (
        <div className="space-y-5">
            {error && <StaleDataNotice fetchedAt={fetchedAt} />}
            {/* ── Title ── */}
            <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-400">
                    Nadchodzące Wydarzenia
                </h2>
                <span className="text-xs font-bold text-neutral-400 bg-gray-900/50 px-2 py-0.5 rounded-full">
                    {filteredEvents.length} {activeCategory !== 'Wszystkie' ? `/ ${events.length}` : ''}
                </span>
            </div>

            {/* ── Category Chips ── */}
            <div className="flex flex-wrap gap-2 items-center">
                <button
                    onClick={() => setActiveCategory('Wszystkie')}
                    className={`px-3.5 py-1.5 rounded-full text-xs font-medium transition-all whitespace-nowrap flex items-center gap-1.5 border ${
                        activeCategory === 'Wszystkie'
                            ? 'bg-purple-600/20 text-purple-300 border-purple-500/30 shadow-lg shadow-purple-500/10'
                            : 'bg-white/5 text-neutral-400 border-white/5 hover:bg-white/10'
                    }`}
                >
                    Wszystkie
                    <span className="text-[10px] font-black bg-white/10 px-1.5 rounded">{events.length}</span>
                </button>

                {visibleCategories.map(cat => {
                    const chip = getCategoryChip(cat);
                    const count = categoryCounts[cat] || 0;
                    return (
                        <button
                            key={cat}
                            onClick={() => setActiveCategory(cat)}
                            className={`px-3.5 py-1.5 rounded-full text-xs font-medium transition-all whitespace-nowrap flex items-center gap-1.5 border ${
                                activeCategory === cat
                                    ? `${chip.active} shadow-lg`
                                    : 'bg-white/5 text-neutral-400 border-white/5 hover:bg-white/10'
                            }`}
                        >
                            <div className={`w-1.5 h-1.5 rounded-full ${chip.dot}`} />
                            {cat}
                            <span className="text-[10px] font-black bg-white/10 px-1.5 rounded">{count}</span>
                        </button>
                    );
                })}

                {overflowCount > 0 && (
                    <button
                        onClick={() => setChipsExpanded(p => !p)}
                        className="px-3 py-1.5 rounded-full text-xs font-medium bg-white/5 text-neutral-400 border border-white/5 hover:bg-white/10 transition-all flex items-center gap-1"
                    >
                        {chipsExpanded
                            ? <><span>Ukryj</span> <ChevronUp size={10} /></>
                            : <><span>+{overflowCount} więcej</span> <ChevronDown size={10} /></>
                        }
                    </button>
                )}
            </div>

            {/* ── Events list grouped by month ── */}
            {filteredEvents.length === 0 ? (
                <div className="text-center py-16 text-neutral-500">
                    <div className="text-4xl mb-3">📅</div>
                    Brak wydarzeń w kategorii „{activeCategory}".
                </div>
            ) : (
                <div className="space-y-6">
                    {groupedEvents.map(([monthKey, monthEvents]) => (
                        <div key={monthKey}>
                            {/* Month header */}
                            <div className="flex items-center gap-3 mb-3">
                                <div className="w-1 h-4 rounded-full bg-gradient-to-b from-purple-400 to-pink-400" />
                                <h3 className="text-xs font-bold uppercase tracking-widest text-neutral-300">
                                    {getMonthLabel(monthKey)}
                                </h3>
                                <div className="flex-1 h-px bg-white/5" />
                                <span className="text-xs text-neutral-400">
                                    {monthEvents.length} {monthEvents.length === 1 ? 'wydarzenie' : monthEvents.length < 5 ? 'wydarzenia' : 'wydarzeń'}
                                </span>
                            </div>

                            {/* Event cards */}
                            <div className="space-y-2">
                                {monthEvents.map(event => (
                                    <EventCard key={event.id} event={event} />
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default EventsFeed;
