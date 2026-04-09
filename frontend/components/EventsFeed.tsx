import React, { useState, useMemo } from 'react';
import { ChevronDown, ChevronUp, MapPin, Clock, Calendar } from 'lucide-react';
import { useEvents } from '../src/hooks/useEvents';
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

/* ── Google Calendar & ICS ── */
function generateGoogleCalendarUrl(event: Event): string {
    const startDate = new Date(event.date);
    const endDate = new Date(startDate.getTime() + 2 * 60 * 60 * 1000);
    const fmt = (d: Date) => d.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
    const params = new URLSearchParams({
        action: 'TEMPLATE',
        text: event.title,
        dates: `${fmt(startDate)}/${fmt(endDate)}`,
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
const EventCard: React.FC<{ event: Event }> = ({ event }) => {
    const d = new Date(event.date);
    const chip = getCategoryChip(event.category || '');
    const h = d.getHours();
    const m = d.getMinutes();
    const timeStr = (h === 0 && m === 0) ? 'cały dzień' : `${h}:${m.toString().padStart(2, '0')}`;

    const inner = (
        <>
            {/* Date badge */}
            <div className="shrink-0 flex flex-col items-center justify-center w-14 h-14 rounded-xl bg-white/5 border border-white/10 group-hover:border-blue-500/20 group-hover:bg-blue-500/8 transition-colors">
                <span className="text-[8px] text-neutral-500 font-bold uppercase leading-none">
                    {d.toLocaleDateString('pl-PL', { month: 'short' }).replace('.', '')}
                </span>
                <span className="text-xl font-black text-neutral-200 leading-none group-hover:text-blue-300 transition-colors">
                    {d.getDate()}
                </span>
                <span className="text-[7px] text-neutral-600 font-medium capitalize">
                    {d.toLocaleDateString('pl-PL', { weekday: 'short' })}
                </span>
            </div>

            {/* Image thumbnail */}
            {event.imageUrl && (
                <div className="shrink-0 w-14 h-14 rounded-xl overflow-hidden border border-white/5">
                    <img
                        src={event.imageUrl}
                        alt=""
                        className="w-full h-full object-cover"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                    />
                </div>
            )}

            {/* Content */}
            <div className="flex-1 min-w-0">
                {event.category && (
                    <span className={`inline-block text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border mb-1 ${chip.badge}`}>
                        {event.category}
                    </span>
                )}
                <h4 className="text-sm font-bold text-neutral-200 group-hover:text-blue-300 transition-colors leading-snug mb-1.5 line-clamp-2">
                    {event.title}
                </h4>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-neutral-500">
                    <span className="flex items-center gap-1">
                        <Clock size={10} className="shrink-0" />
                        {timeStr}
                    </span>
                    {event.location && (
                        <span className="flex items-center gap-1 truncate max-w-[160px]">
                            <MapPin size={10} className="shrink-0" />
                            {event.location}
                        </span>
                    )}
                </div>
                {event.description && (
                    <p className="text-xs text-neutral-500 mt-1.5 line-clamp-2">{event.description}</p>
                )}
                {event.sourceName && (
                    <p className="text-[10px] text-neutral-600 mt-1.5">
                        <span>Źródło:</span> <span className="font-medium text-neutral-500">{event.sourceName}</span>
                    </p>
                )}
            </div>

            {/* Google Calendar button */}
            <div className="shrink-0 flex items-start">
                <button
                    onClick={(e) => { e.preventDefault(); e.stopPropagation(); window.open(generateGoogleCalendarUrl(event), '_blank'); }}
                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[10px] font-bold text-blue-400 bg-blue-500/10 border border-blue-500/20 hover:bg-blue-500/20 transition-colors whitespace-nowrap"
                    title="Dodaj do Google Calendar"
                >
                    <Calendar size={10} />
                    Google Cal
                </button>
            </div>
        </>
    );

    const cardClass = "flex gap-4 p-4 rounded-2xl bg-gray-900/40 border border-white/5 hover:bg-gray-900/60 hover:border-white/10 transition-all group";

    if (event.externalUrl) {
        return (
            <a href={event.externalUrl} target="_blank" rel="noopener noreferrer" className={cardClass}>
                {inner}
            </a>
        );
    }
    return <div className={cardClass}>{inner}</div>;
};

/* ── Main Component ── */
const VISIBLE_CHIPS = 5;

const EventsFeed: React.FC<{ initialCategory?: string }> = ({ initialCategory }) => {
    const { events, loading, error } = useEvents(100);
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

    if (error) return <div className="text-center p-8 text-red-500">Błąd: {error}</div>;
    if (!events || events.length === 0) return (
        <div className="text-center p-12 text-neutral-500">
            <div className="text-4xl mb-3">📅</div>
            Brak nadchodzących wydarzeń.
        </div>
    );

    return (
        <div className="space-y-5">
            {/* ── Title ── */}
            <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-400">
                    Nadchodzące Wydarzenia
                </h2>
                <span className="text-xs font-bold text-neutral-600 bg-gray-900/50 px-2 py-0.5 rounded-full">
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
                                <h3 className="text-xs font-bold uppercase tracking-widest text-neutral-500">
                                    {getMonthLabel(monthKey)}
                                </h3>
                                <div className="flex-1 h-px bg-white/5" />
                                <span className="text-[10px] text-neutral-700">
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
