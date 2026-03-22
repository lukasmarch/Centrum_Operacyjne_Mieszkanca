import React, { useState, useMemo, useCallback } from 'react';
import { ChevronLeft, ChevronRight, MapPin, Clock, Calendar, Download, ExternalLink } from 'lucide-react';
import { Event } from '../types';

interface EventCalendarProps {
    events: Event[];
    onSelectDay?: (date: Date, dayEvents: Event[]) => void;
}

/* ── Category color dots ─────────────────────────────────────── */

const CATEGORY_DOT_COLORS: Record<string, string> = {
    kultura: 'bg-violet-400',
    sport: 'bg-orange-400',
    rozrywka: 'bg-pink-400',
    społeczne: 'bg-emerald-400',
    edukacja: 'bg-cyan-400',
    koncert: 'bg-rose-400',
    festiwal: 'bg-fuchsia-400',
    targi: 'bg-amber-400',
    urząd: 'bg-blue-400',
    inne: 'bg-neutral-400',
};

const CATEGORY_BADGE_COLORS: Record<string, string> = {
    kultura: 'bg-violet-600/30 text-violet-300 border-violet-500/30',
    sport: 'bg-orange-600/30 text-orange-300 border-orange-500/30',
    rozrywka: 'bg-pink-600/30 text-pink-300 border-pink-500/30',
    społeczne: 'bg-emerald-600/30 text-emerald-300 border-emerald-500/30',
    edukacja: 'bg-cyan-600/30 text-cyan-300 border-cyan-500/30',
    koncert: 'bg-rose-600/30 text-rose-300 border-rose-500/30',
    festiwal: 'bg-fuchsia-600/30 text-fuchsia-300 border-fuchsia-500/30',
    targi: 'bg-amber-600/30 text-amber-300 border-amber-500/30',
    urząd: 'bg-blue-600/30 text-blue-300 border-blue-500/30',
    inne: 'bg-neutral-600/30 text-neutral-300 border-neutral-500/30',
};

const getCategoryDotColor = (category?: string): string => {
    if (!category) return 'bg-blue-400';
    const key = category.toLowerCase();
    for (const [k, v] of Object.entries(CATEGORY_DOT_COLORS)) {
        if (key.includes(k) || k.includes(key)) return v;
    }
    return 'bg-blue-400';
};

const getCategoryBadgeColor = (category?: string): string => {
    if (!category) return 'bg-blue-600/30 text-blue-300 border-blue-500/30';
    const key = category.toLowerCase();
    for (const [k, v] of Object.entries(CATEGORY_BADGE_COLORS)) {
        if (key.includes(k) || k.includes(key)) return v;
    }
    return 'bg-blue-600/30 text-blue-300 border-blue-500/30';
};

/* ── Calendar helpers ────────────────────────────────────────── */

const WEEKDAY_LABELS = ['Pn', 'Wt', 'Śr', 'Cz', 'Pt', 'So', 'Nd'];
const MONTH_NAMES = [
    'Styczeń', 'Luty', 'Marzec', 'Kwiecień', 'Maj', 'Czerwiec',
    'Lipiec', 'Sierpień', 'Wrzesień', 'Październik', 'Listopad', 'Grudzień'
];

function getDaysInMonth(year: number, month: number): number {
    return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(year: number, month: number): number {
    const d = new Date(year, month, 1).getDay();
    return d === 0 ? 6 : d - 1;
}

function isSameDay(d1: Date, d2: Date): boolean {
    return d1.getFullYear() === d2.getFullYear() &&
        d1.getMonth() === d2.getMonth() &&
        d1.getDate() === d2.getDate();
}

function toDateKey(d: Date): string {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/* ── Google Calendar & ICS export ────────────────────────────── */

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

function downloadICalendar(event: Event): void {
    const startDate = new Date(event.date);
    const endDate = new Date(startDate.getTime() + 2 * 60 * 60 * 1000);
    const fmt = (d: Date) => d.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
    const ics = [
        'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Centrum Operacyjne Mieszkańca//PL',
        'BEGIN:VEVENT',
        `UID:${event.id}@centrumoperacyjne.pl`,
        `DTSTAMP:${fmt(new Date())}`,
        `DTSTART:${fmt(startDate)}`,
        `DTEND:${fmt(endDate)}`,
        `SUMMARY:${event.title}`,
        `DESCRIPTION:${event.description || ''}`,
        `LOCATION:${event.location || ''}`,
        'END:VEVENT', 'END:VCALENDAR'
    ].join('\r\n');
    const blob = new Blob([ics], { type: 'text/calendar;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${event.title.replace(/[^a-z0-9]/gi, '_')}.ics`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

/* ── Component ───────────────────────────────────────────────── */

const EventCalendar: React.FC<EventCalendarProps> = ({ events }) => {
    const today = new Date();
    const [viewYear, setViewYear] = useState(today.getFullYear());
    const [viewMonth, setViewMonth] = useState(today.getMonth());
    const [selectedDate, setSelectedDate] = useState<Date | null>(null);

    // Build a map: dateKey → Event[]
    const eventsByDate = useMemo(() => {
        const map = new Map<string, Event[]>();
        events.forEach(ev => {
            const d = new Date(ev.date);
            if (isNaN(d.getTime())) return;
            const key = toDateKey(d);
            if (!map.has(key)) map.set(key, []);
            map.get(key)!.push(ev);
        });
        return map;
    }, [events]);

    // Events for selected day
    const selectedDayEvents = useMemo(() => {
        if (!selectedDate) return [];
        return eventsByDate.get(toDateKey(selectedDate)) || [];
    }, [selectedDate, eventsByDate]);

    // Navigation
    const goPrev = useCallback(() => {
        if (viewMonth === 0) { setViewYear(y => y - 1); setViewMonth(11); }
        else setViewMonth(m => m - 1);
        setSelectedDate(null);
    }, [viewMonth]);

    const goNext = useCallback(() => {
        if (viewMonth === 11) { setViewYear(y => y + 1); setViewMonth(0); }
        else setViewMonth(m => m + 1);
        setSelectedDate(null);
    }, [viewMonth]);

    const goToday = useCallback(() => {
        setViewYear(today.getFullYear());
        setViewMonth(today.getMonth());
        setSelectedDate(today);
    }, [today]);

    // Grid cells
    const daysInMonth = getDaysInMonth(viewYear, viewMonth);
    const firstDay = getFirstDayOfMonth(viewYear, viewMonth);
    const prevMonthDays = getDaysInMonth(viewYear, viewMonth === 0 ? 11 : viewMonth - 1);
    const leadingBlanks = firstDay;

    const cells: Array<{ day: number; inMonth: boolean; date: Date }> = [];

    for (let i = leadingBlanks - 1; i >= 0; i--) {
        const d = prevMonthDays - i;
        const prevM = viewMonth === 0 ? 11 : viewMonth - 1;
        const prevY = viewMonth === 0 ? viewYear - 1 : viewYear;
        cells.push({ day: d, inMonth: false, date: new Date(prevY, prevM, d) });
    }

    for (let d = 1; d <= daysInMonth; d++) {
        cells.push({ day: d, inMonth: true, date: new Date(viewYear, viewMonth, d) });
    }

    const trailing = 7 - (cells.length % 7);
    if (trailing < 7) {
        const nextM = viewMonth === 11 ? 0 : viewMonth + 1;
        const nextY = viewMonth === 11 ? viewYear + 1 : viewYear;
        for (let d = 1; d <= trailing; d++) {
            cells.push({ day: d, inMonth: false, date: new Date(nextY, nextM, d) });
        }
    }

    const formatTime = (dateStr: string) => {
        const d = new Date(dateStr);
        const h = d.getHours();
        const m = d.getMinutes();
        if (h === 0 && m === 0) return 'cały dzień';
        return `${h}:${m.toString().padStart(2, '0')}`;
    };

    return (
        <div className="glass-panel rounded-3xl border border-white/10 overflow-hidden">
            {/* ── Header: Month navigation ── */}
            <div className="flex items-center justify-between px-6 pt-6 pb-4">
                <div className="flex items-center gap-3">
                    <h3 className="text-2xl font-black text-neutral-100 tracking-tight">
                        {MONTH_NAMES[viewMonth]}
                    </h3>
                    <span className="text-lg font-bold text-neutral-500">{viewYear}</span>
                </div>
                <div className="flex items-center gap-1">
                    <button
                        onClick={goToday}
                        className="px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider text-blue-400 bg-blue-500/10 border border-blue-500/20 hover:bg-blue-500/20 transition-colors mr-2"
                    >
                        Dziś
                    </button>
                    <button
                        onClick={goPrev}
                        className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/10 text-neutral-400 hover:text-white transition-colors"
                    >
                        <ChevronLeft size={18} />
                    </button>
                    <button
                        onClick={goNext}
                        className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/10 text-neutral-400 hover:text-white transition-colors"
                    >
                        <ChevronRight size={18} />
                    </button>
                </div>
            </div>

            {/* ── Weekday headers ── */}
            <div className="grid grid-cols-7 px-4">
                {WEEKDAY_LABELS.map(label => (
                    <div key={label} className="text-center py-2">
                        <span className={`text-[11px] font-bold uppercase tracking-wider ${label === 'So' || label === 'Nd' ? 'text-neutral-600' : 'text-neutral-500'
                            }`}>
                            {label}
                        </span>
                    </div>
                ))}
            </div>

            {/* ── Day grid ── */}
            <div className="grid grid-cols-7 px-4 pb-4">
                {cells.map((cell, idx) => {
                    const key = toDateKey(cell.date);
                    const dayEvents = eventsByDate.get(key) || [];
                    const hasEvents = dayEvents.length > 0;
                    const isToday = isSameDay(cell.date, today);
                    const isSelected = selectedDate && isSameDay(cell.date, selectedDate);
                    const isWeekend = idx % 7 >= 5;

                    const dotColors = hasEvents
                        ? [...new Set(dayEvents.map(e => getCategoryDotColor(e.category)))].slice(0, 3)
                        : [];

                    return (
                        <button
                            key={idx}
                            onClick={() => {
                                if (hasEvents) {
                                    setSelectedDate(isSelected ? null : cell.date);
                                }
                            }}
                            className={`
                relative flex flex-col items-center justify-center py-3 rounded-xl transition-all duration-200
                ${!cell.inMonth ? 'opacity-30' : ''}
                ${hasEvents ? 'cursor-pointer hover:bg-white/5' : 'cursor-default'}
                ${isSelected && !isToday ? 'bg-blue-500/15 ring-1 ring-blue-500/30' : ''}
              `}
                        >
                            <span className={`
                text-sm font-bold relative z-10 w-8 h-8 flex items-center justify-center rounded-full transition-all
                ${isToday
                                    ? 'bg-red-500 text-white shadow-lg shadow-red-500/30'
                                    : isSelected
                                        ? 'text-blue-300'
                                        : isWeekend && cell.inMonth
                                            ? 'text-neutral-500'
                                            : cell.inMonth
                                                ? 'text-neutral-300'
                                                : 'text-gray-700'
                                }`}>
                                {cell.day}
                            </span>

                            {hasEvents && (
                                <div className="flex items-center gap-0.5 mt-1 h-2">
                                    {dotColors.map((color, di) => (
                                        <div
                                            key={di}
                                            className={`w-1.5 h-1.5 rounded-full ${color} ${isToday ? 'opacity-80' : ''}`}
                                        />
                                    ))}
                                </div>
                            )}

                            {!hasEvents && <div className="h-2 mt-1" />}
                        </button>
                    );
                })}
            </div>

            {/* ── Selected day events panel (below calendar) ── */}
            {selectedDate && selectedDayEvents.length > 0 && (
                <>
                    <div className="border-t border-white/5" />
                    <div className="px-6 py-5 space-y-3 animate-in fade-in slide-in-from-top-2 duration-300">
                        {/* Day header */}
                        <div className="flex items-center gap-2 mb-1">
                            <Calendar size={14} className="text-blue-400" />
                            <span className="text-xs font-bold text-neutral-400 uppercase tracking-wider">
                                {selectedDate.toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'long' })}
                            </span>
                            <span className="text-[10px] text-neutral-600 ml-auto">
                                {selectedDayEvents.length} {selectedDayEvents.length === 1 ? 'wydarzenie' : selectedDayEvents.length < 5 ? 'wydarzenia' : 'wydarzeń'}
                            </span>
                        </div>

                        {/* Event cards */}
                        {selectedDayEvents.map(event => {
                            const time = formatTime(event.date);
                            const badgeColor = getCategoryBadgeColor(event.category);
                            const dotColor = getCategoryDotColor(event.category);
                            const eventDate = new Date(event.date);

                            return (
                                <div
                                    key={event.id}
                                    className="flex gap-4 p-4 rounded-2xl bg-gray-900/40 border border-white/5 hover:bg-gray-900/60 transition-colors group"
                                >
                                    {/* Date badge */}
                                    <div className="shrink-0 flex flex-col items-center justify-center w-14 h-14 rounded-xl bg-white/5 border border-white/10 group-hover:border-blue-500/30 group-hover:bg-blue-500/10 transition-colors">
                                        <span className="text-[8px] text-neutral-500 font-bold uppercase leading-none">
                                            {eventDate.toLocaleDateString('pl-PL', { month: 'short' }).replace('.', '')}
                                        </span>
                                        <span className="text-lg font-black text-neutral-200 leading-none group-hover:text-blue-300">
                                            {eventDate.getDate()}
                                        </span>
                                        <span className="text-[7px] text-neutral-600 font-medium">
                                            {eventDate.toLocaleDateString('pl-PL', { weekday: 'short' })}
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
                                        <div className="flex items-center gap-2 mb-0.5">
                                            <span className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border ${badgeColor}`}>
                                                {event.category}
                                            </span>
                                        </div>
                                        <h4 className="text-sm font-bold text-neutral-200 group-hover:text-blue-300 transition-colors leading-snug mb-1">
                                            {event.title}
                                        </h4>
                                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-neutral-500">
                                            <span className="flex items-center gap-1">
                                                <Clock size={10} className="shrink-0" />
                                                {time}
                                            </span>
                                            {event.location && (
                                                <span className="flex items-center gap-1">
                                                    <MapPin size={10} className="shrink-0" />
                                                    {event.location}
                                                </span>
                                            )}
                                        </div>
                                        {event.description && (
                                            <p className="text-xs text-neutral-500 mt-1.5 line-clamp-2">{event.description}</p>
                                        )}
                                    </div>

                                    {/* Actions – inline, top-right */}
                                    <div className="shrink-0 flex items-start gap-1.5">
                                        <button
                                            onClick={(e) => { e.stopPropagation(); window.open(generateGoogleCalendarUrl(event), '_blank'); }}
                                            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[10px] font-bold text-blue-400 bg-blue-500/10 border border-blue-500/20 hover:bg-blue-500/20 transition-colors whitespace-nowrap"
                                            title="Dodaj do Google Calendar"
                                        >
                                            <Calendar size={10} />
                                            Google
                                        </button>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); downloadICalendar(event); }}
                                            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[10px] font-bold text-neutral-400 bg-white/5 border border-white/5 hover:bg-white/10 transition-colors whitespace-nowrap"
                                            title="Pobierz plik .ics"
                                        >
                                            <Download size={10} />
                                            .ics
                                        </button>
                                        {event.externalUrl && (
                                            <a
                                                href={event.externalUrl}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[10px] font-bold text-purple-400 bg-purple-500/10 border border-purple-500/20 hover:bg-purple-500/20 transition-colors whitespace-nowrap"
                                            >
                                                <ExternalLink size={10} />
                                                Więcej
                                            </a>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </>
            )}
        </div>
    );
};

export default EventCalendar;
