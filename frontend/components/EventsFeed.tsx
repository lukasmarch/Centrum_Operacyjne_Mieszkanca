import React, { useState, useMemo } from 'react';
import { useEvents } from '../src/hooks/useEvents';

const EventsFeed: React.FC = () => {
    const { events, loading, error } = useEvents();
    const [activeCategory, setActiveCategory] = useState<string>('Wszystkie');
    const [expandedEventId, setExpandedEventId] = useState<string | null>(null);

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

    // Generate Google Calendar URL
    const generateGoogleCalendarUrl = (event: typeof events[0]) => {
        const startDate = new Date(event.date);
        const endDate = new Date(startDate.getTime() + 2 * 60 * 60 * 1000); // +2 hours

        const formatDate = (date: Date) => {
            return date.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
        };

        const params = new URLSearchParams({
            action: 'TEMPLATE',
            text: event.title,
            dates: `${formatDate(startDate)}/${formatDate(endDate)}`,
            details: event.description || '',
            location: event.location || ''
        });

        return `https://calendar.google.com/calendar/render?${params.toString()}`;
    };

    // Generate iCalendar file
    const generateICalendar = (event: typeof events[0]) => {
        const startDate = new Date(event.date);
        const endDate = new Date(startDate.getTime() + 2 * 60 * 60 * 1000);

        const formatDate = (date: Date) => {
            return date.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
        };

        const icsContent = [
            'BEGIN:VCALENDAR',
            'VERSION:2.0',
            'PRODID:-//Centrum Operacyjne Mieszkańca//PL',
            'BEGIN:VEVENT',
            `UID:${event.id}@centrumoperacyjne.pl`,
            `DTSTAMP:${formatDate(new Date())}`,
            `DTSTART:${formatDate(startDate)}`,
            `DTEND:${formatDate(endDate)}`,
            `SUMMARY:${event.title}`,
            `DESCRIPTION:${event.description || ''}`,
            `LOCATION:${event.location || ''}`,
            'END:VEVENT',
            'END:VCALENDAR'
        ].join('\r\n');

        const blob = new Blob([icsContent], { type: 'text/calendar;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${event.title.replace(/[^a-z0-9]/gi, '_')}.ics`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    };

    if (loading) return <div className="text-center p-8 text-slate-500 animate-pulse">Ładowanie wydarzeń...</div>;
    if (error) return <div className="text-center p-8 text-red-500">Błąd: {error}</div>;
    if (!events || events.length === 0) return <div className="text-center p-8 text-slate-500">Brak nadchodzących wydarzeń.</div>;

    return (
        <div className="space-y-6">
            <h2 className="text-2xl font-bold text-slate-100">Nadchodzące Wydarzenia</h2>

            {/* Categories */}
            <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
                {categories.map(cat => (
                    <button
                        key={cat}
                        onClick={() => setActiveCategory(cat)}
                        className={`px-4 py-2 rounded-full text-sm font-bold transition-all whitespace-nowrap ${activeCategory === cat
                            ? 'bg-purple-600 text-white shadow-md shadow-purple-500/20'
                            : 'bg-white/5 text-slate-400 hover:bg-white/10 border border-white/5'
                            }`}
                    >
                        {cat}
                    </button>
                ))}
            </div>

            {/* Events List */}
            <div className="glass-panel rounded-3xl shadow-sm border border-white/10 overflow-hidden divide-y divide-white/5">
                {filteredEvents.map((event) => (
                    <div key={event.id} className="p-6 hover:bg-white/5 transition-colors group">
                        <div className="flex flex-col md:flex-row gap-6">
                            {/* Image Thumbnail */}
                            {event.imageUrl && (
                                <div className="flex-shrink-0 w-full md:w-32 h-32 rounded-2xl overflow-hidden bg-slate-800">
                                    <img
                                        src={event.imageUrl}
                                        alt={event.title}
                                        className="w-full h-full object-cover"
                                        onError={(e) => {
                                            (e.target as HTMLImageElement).style.display = 'none';
                                        }}
                                    />
                                </div>
                            )}

                            {/* Date Badge (if no image) */}
                            {!event.imageUrl && (
                                <div className="flex-shrink-0 flex flex-col items-center justify-center w-20 h-20 bg-white/5 rounded-2xl border border-white/10 group-hover:border-purple-500/30 group-hover:bg-purple-500/10 transition-colors">
                                    <span className="text-xs font-bold text-slate-500 uppercase group-hover:text-purple-400">{new Date(event.date).toLocaleDateString('pl-PL', { month: 'short' })}</span>
                                    <span className="text-2xl font-black text-slate-300 group-hover:text-purple-400">{new Date(event.date).getDate()}</span>
                                </div>
                            )}

                            {/* Content */}
                            <div className="flex-1">
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="text-[10px] font-bold uppercase tracking-wider text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
                                        {event.category}
                                    </span>
                                    {event.isPromoted && (
                                        <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                                            ⭐ Promowane
                                        </span>
                                    )}
                                </div>
                                <h3 className="text-lg font-bold text-slate-200 mb-2 group-hover:text-purple-400 transition-colors">
                                    {event.title}
                                </h3>
                                <div className="flex flex-col gap-1 text-sm text-slate-500 mb-3">
                                    <span className="flex items-center gap-1">
                                        📅 {new Date(event.date).toLocaleDateString('pl-PL', {
                                            day: 'numeric',
                                            month: 'long',
                                            year: 'numeric'
                                        })}
                                    </span>
                                    <span className="flex items-center gap-1">📍 {event.location}</span>
                                </div>
                                {event.description && (
                                    <p className="text-sm text-slate-400 line-clamp-2 mb-3">{event.description}</p>
                                )}
                            </div>

                            {/* Actions */}
                            <div className="flex flex-col gap-2 items-start md:items-end">
                                {/* External Link Button */}
                                {event.externalUrl && (
                                    <a
                                        href={event.externalUrl}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="px-4 py-2 rounded-xl border border-white/10 text-slate-400 font-bold text-sm hover:bg-blue-600 hover:text-white hover:border-blue-500 transition-all"
                                    >
                                        Szczegóły
                                    </a>
                                )}

                                {/* Calendar Export Dropdown */}
                                <div className="relative">
                                    <button
                                        onClick={() => setExpandedEventId(expandedEventId === event.id ? null : event.id)}
                                        className="px-4 py-2 rounded-xl border border-purple-500/30 text-purple-400 font-bold text-sm hover:bg-purple-600 hover:text-white hover:border-purple-500 transition-all flex items-center gap-2 bg-purple-500/5"
                                    >
                                        📅 Zaplanuj
                                        <span className="text-xs">{expandedEventId === event.id ? '▲' : '▼'}</span>
                                    </button>

                                    {expandedEventId === event.id && (
                                        <div className="absolute right-0 mt-2 w-56 glass-panel-solid rounded-xl shadow-lg border border-white/10 overflow-hidden z-10 bg-slate-900">
                                            <button
                                                onClick={() => {
                                                    window.open(generateGoogleCalendarUrl(event), '_blank');
                                                    setExpandedEventId(null);
                                                }}
                                                className="w-full px-4 py-3 text-left text-sm font-semibold text-slate-300 hover:bg-white/10 transition-colors flex items-center gap-3"
                                            >
                                                <span className="text-lg">📆</span>
                                                <span>Google Calendar</span>
                                            </button>
                                            <button
                                                onClick={() => {
                                                    generateICalendar(event);
                                                    setExpandedEventId(null);
                                                }}
                                                className="w-full px-4 py-3 text-left text-sm font-semibold text-slate-300 hover:bg-white/10 transition-colors flex items-center gap-3 border-t border-white/5"
                                            >
                                                <span className="text-lg">📥</span>
                                                <span>Pobierz .ics (iCalendar)</span>
                                            </button>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default EventsFeed;
