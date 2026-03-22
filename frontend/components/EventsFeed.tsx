import React, { useState, useMemo } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { useEvents } from '../src/hooks/useEvents';
import EventCalendar from './EventCalendar';

/* ── Category chip colors ───────────────────────────────────── */

const CATEGORY_CHIP: Record<string, { active: string; dot: string }> = {
    kultura: { active: 'bg-violet-600/20 text-violet-300 border-violet-500/30', dot: 'bg-violet-400' },
    sport: { active: 'bg-orange-600/20 text-orange-300 border-orange-500/30', dot: 'bg-orange-400' },
    rozrywka: { active: 'bg-pink-600/20 text-pink-300 border-pink-500/30', dot: 'bg-pink-400' },
    społeczne: { active: 'bg-emerald-600/20 text-emerald-300 border-emerald-500/30', dot: 'bg-emerald-400' },
    edukacja: { active: 'bg-cyan-600/20 text-cyan-300 border-cyan-500/30', dot: 'bg-cyan-400' },
    koncert: { active: 'bg-rose-600/20 text-rose-300 border-rose-500/30', dot: 'bg-rose-400' },
};

const DEFAULT_CHIP = { active: 'bg-blue-600/20 text-blue-300 border-blue-500/30', dot: 'bg-blue-400' };

function getCategoryChip(cat: string) {
    const key = cat.toLowerCase();
    for (const [k, v] of Object.entries(CATEGORY_CHIP)) {
        if (key.includes(k) || k.includes(key)) return v;
    }
    return DEFAULT_CHIP;
}

/* ── Main Component ──────────────────────────────────────────── */

interface NewsFeedProps {
    initialCategory?: string;
}

const VISIBLE_CHIPS = 5;

const EventsFeed: React.FC<NewsFeedProps> = ({ initialCategory }) => {
    const { events, loading, error } = useEvents(100);
    const [activeCategory, setActiveCategory] = useState<string>(initialCategory || 'Wszystkie');
    const [chipsExpanded, setChipsExpanded] = useState(false);

    // Category counts
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
        // Deduplicate by title + date
        return filtered.filter((ev, i, arr) =>
            i === arr.findIndex(t =>
                t.title === ev.title &&
                new Date(t.date).toDateString() === new Date(ev.date).toDateString()
            )
        );
    }, [events, activeCategory]);

    if (loading) return (
        <div className="space-y-6">
            <div className="h-8 w-56 bg-gray-900/50 rounded-xl animate-pulse" />
            <div className="h-10 bg-gray-900/30 rounded-xl animate-pulse" />
            <div className="h-[380px] bg-gray-900/30 rounded-3xl animate-pulse" />
        </div>
    );

    if (error) return <div className="text-center p-8 text-red-500">Błąd: {error}</div>;
    if (!events || events.length === 0) return <div className="text-center p-8 text-neutral-500">Brak nadchodzących wydarzeń.</div>;

    return (
        <div className="space-y-6">
            {/* ── Title ── */}
            <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-400">
                    Nadchodzące Wydarzenia
                </h2>
                <span className="text-xs font-bold text-neutral-600 bg-gray-900/50 px-2 py-0.5 rounded-full">
                    {events.length} events
                </span>
            </div>

            {/* ── Category Chips (above calendar) ── */}
            <div className="flex flex-wrap gap-2 items-center">
                <button
                    onClick={() => setActiveCategory('Wszystkie')}
                    className={`px-3.5 py-1.5 rounded-full text-xs font-medium transition-all whitespace-nowrap flex items-center gap-1.5 border ${activeCategory === 'Wszystkie'
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
                            className={`px-3.5 py-1.5 rounded-full text-xs font-medium transition-all whitespace-nowrap flex items-center gap-1.5 border ${activeCategory === cat
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
                            ? <>Ukryj <ChevronUp size={10} /></>
                            : <>+{overflowCount} więcej <ChevronDown size={10} /></>
                        }
                    </button>
                )}
            </div>

            {/* ── Calendar ── */}
            <EventCalendar events={filteredEvents} />

            {/* Empty state */}
            {filteredEvents.length === 0 && (
                <div className="text-center py-16 text-neutral-500">
                    <div className="text-4xl mb-3">📅</div>
                    Brak wydarzeń w kategorii „{activeCategory}".
                </div>
            )}
        </div>
    );
};

export default EventsFeed;
