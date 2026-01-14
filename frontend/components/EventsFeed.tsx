import React, { useState, useMemo } from 'react';
import { useEvents } from '../src/hooks/useEvents';

const EventsFeed: React.FC = () => {
    const { events, loading, error } = useEvents();
    const [activeCategory, setActiveCategory] = useState<string>('Wszystkie');

    // Group events categories
    const categories = useMemo(() => {
        if (!events) return [];
        const cats = new Set(events.map(e => e.category).filter(Boolean));
        return ['Wszystkie', ...Array.from(cats)];
    }, [events]);

    // Filter and Deduplicate events
    const filteredEvents = useMemo(() => {
        if (!events) return [];

        let filtered = events;
        if (activeCategory !== 'Wszystkie') {
            filtered = events.filter(e => e.category === activeCategory);
        }

        // Deduplicate by title and date
        const uniqueEvents = filtered.filter((event, index, self) =>
            index === self.findIndex((t) => (
                t.title === event.title &&
                new Date(t.date).toDateString() === new Date(event.date).toDateString()
            ))
        );

        return uniqueEvents;
    }, [events, activeCategory]);

    if (loading) return <div className="text-center p-8 text-slate-500 animate-pulse">Ładowanie wydarzeń...</div>;
    if (error) return <div className="text-center p-8 text-red-500">Błąd: {error}</div>;
    if (!events || events.length === 0) return <div className="text-center p-8 text-slate-500">Brak nadchodzących wydarzeń.</div>;

    const categoryIcons: Record<string, string> = {
        'Kultura': '🎭',
        'Sport': '⚽',
        'Urząd': '🏛️',
        'Rozrywka': '🎉',
        'Edukacja': '📚',
        'Inne': '📅'
    };

    return (
        <div className="space-y-6">
            <h2 className="text-2xl font-bold text-slate-900">Nadchodzące Wydarzenia</h2>

            {/* Categories */}
            <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
                {categories.map(cat => (
                    <button
                        key={cat}
                        onClick={() => setActiveCategory(cat)}
                        className={`px-4 py-2 rounded-full text-sm font-bold transition-all whitespace-nowrap ${activeCategory === cat
                            ? 'bg-purple-600 text-white shadow-md shadow-purple-200'
                            : 'bg-white text-slate-500 hover:bg-slate-100'
                            }`}
                    >
                        {cat}
                    </button>
                ))}
            </div>

            {/* Events List */}
            <div className="bg-white rounded-3xl shadow-sm border border-slate-100 overflow-hidden divide-y divide-slate-100">
                {filteredEvents.map((event) => (
                    <div key={event.id} className="p-6 hover:bg-slate-50 transition-colors flex flex-col md:flex-row gap-6 group">
                        {/* Date Badge */}
                        <div className="flex-shrink-0 flex flex-col items-center justify-center w-20 h-20 bg-slate-100 rounded-2xl border border-slate-200 group-hover:border-purple-200 group-hover:bg-purple-50 transition-colors">
                            <span className="text-xs font-bold text-slate-400 uppercase group-hover:text-purple-400">{new Date(event.date).toLocaleDateString('pl-PL', { month: 'short' })}</span>
                            <span className="text-2xl font-black text-slate-700 group-hover:text-purple-600">{new Date(event.date).getDate()}</span>
                        </div>

                        {/* Content */}
                        <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                                <span className="text-[10px] font-bold uppercase tracking-wider text-purple-600 bg-purple-50 px-2 py-0.5 rounded">
                                    {event.category}
                                </span>
                                {event.isPromoted && (
                                    <span className="text-[10px] font-bold uppercase tracking-wider text-amber-600 bg-amber-50 px-2 py-0.5 rounded">
                                        ⭐ Promowane
                                    </span>
                                )}
                            </div>
                            <h3 className="text-lg font-bold text-slate-900 mb-2 group-hover:text-purple-600 transition-colors">
                                {event.title}
                            </h3>
                            <div className="flex items-center gap-4 text-sm text-slate-500">
                                <span className="flex items-center gap-1">📍 {event.location}</span>
                                {/* <span className="flex items-center gap-1">⏰ 18:00</span> */}
                            </div>
                        </div>

                        {/* Action */}
                        <div className="flex items-center">
                            <button className="px-6 py-2 rounded-xl border border-slate-200 text-slate-600 font-bold text-sm hover:bg-purple-600 hover:text-white hover:border-purple-600 transition-all">
                                Szczegóły
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default EventsFeed;
