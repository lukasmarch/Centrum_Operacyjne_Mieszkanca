import React, { useState, useMemo } from 'react';
import { CalendarDays, ArrowRight, MapPin, Clock } from 'lucide-react';
import { useEvents } from '../src/hooks/useEvents';
import { Calendar } from './ui/calendar-rac';
import { AppSection } from '../types';

/* ── Category legend ── */
const CATEGORY_LEGEND = [
  { label: 'Kultura', color: 'bg-violet-400' },
  { label: 'Sport', color: 'bg-orange-400' },
  { label: 'Rozrywka', color: 'bg-pink-400' },
  { label: 'Społeczne', color: 'bg-emerald-400' },
];

const CATEGORY_DOT_COLORS: Record<string, string> = {
  kultura: 'bg-violet-400',
  sport: 'bg-orange-400',
  rozrywka: 'bg-pink-400',
  społeczne: 'bg-emerald-400',
  edukacja: 'bg-cyan-400',
  koncert: 'bg-rose-400',
};

function getCategoryDot(cat?: string) {
  if (!cat) return 'bg-blue-400';
  const key = cat.toLowerCase();
  for (const [k, v] of Object.entries(CATEGORY_DOT_COLORS)) {
    if (key.includes(k) || k.includes(key)) return v;
  }
  return 'bg-blue-400';
}

interface EventsTileProps {
  onNavigate?: (section: AppSection) => void;
}

const EventsTile: React.FC<EventsTileProps> = ({ onNavigate }) => {
  const { events, loading } = useEvents(100);
  // Store selected date as "YYYY-MM-DD" string key (avoids DateValue type complexity)
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  /* Events for the selected day */
  const selectedDayEvents = useMemo(() => {
    if (!selectedKey || !events) return [];
    return events.filter(ev => {
      const d = new Date(ev.date);
      const k = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      return k === selectedKey;
    });
  }, [selectedKey, events]);

  const formatTime = (dateStr: string) => {
    const d = new Date(dateStr);
    const h = d.getHours();
    const m = d.getMinutes();
    return h === 0 && m === 0 ? 'cały dzień' : `${h}:${m.toString().padStart(2, '0')}`;
  };

  return (
    <div className="h-full flex flex-col p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <CalendarDays size={13} className="text-blue-400" />
          <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider">Kalendarz Wydarzeń</p>
        </div>
        {events && events.length > 0 && (
          <span className="text-[9px] text-neutral-600 font-medium">
            {events.length} nadchodzących
          </span>
        )}
      </div>

      {/* Calendar */}
      {loading ? (
        <div className="space-y-2 animate-pulse">
          <div className="h-6 bg-gray-900/50 rounded-lg" />
          <div className="grid grid-cols-7 gap-1">
            {Array.from({ length: 35 }).map((_, i) => (
              <div key={i} className="h-8 bg-gray-900/30 rounded-lg" />
            ))}
          </div>
        </div>
      ) : (
        <Calendar
          events={events || []}
          aria-label="Kalendarz wydarzeń"
          className="w-full"
          onChange={(val) => {
            const k = `${val.year}-${String(val.month).padStart(2, '0')}-${String(val.day).padStart(2, '0')}`;
            setSelectedKey(prev => prev === k ? null : k);
          }}
        />
      )}

      {/* Selected day preview */}
      {selectedKey && (
        <div className="mt-3 space-y-1.5 animate-in fade-in slide-in-from-top-1 duration-200">
          <p className="text-[9px] font-bold uppercase tracking-wider text-neutral-500 mb-1">
            {(() => { const [y, m, d] = selectedKey.split('-').map(Number); return new Date(y, m - 1, d).toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'long' }); })()}
          </p>

          {selectedDayEvents.length === 0 ? (
            <p className="text-[10px] text-neutral-600 italic">Brak wydarzeń w tym dniu</p>
          ) : (
            selectedDayEvents.slice(0, 3).map(event => (
              <div
                key={event.id}
                className="flex items-center gap-2 p-2 rounded-xl bg-white/4 border border-white/6 hover:bg-white/8 transition-colors group"
              >
                {/* Thumbnail or dot */}
                {event.imageUrl ? (
                  <div className="shrink-0 w-9 h-9 rounded-lg overflow-hidden border border-white/8">
                    <img
                      src={event.imageUrl}
                      alt=""
                      className="w-full h-full object-cover"
                      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                    />
                  </div>
                ) : (
                  <div className={`shrink-0 w-2 h-2 rounded-full ${getCategoryDot(event.category)} mt-0.5`} />
                )}

                {/* Info */}
                <div className="min-w-0 flex-1">
                  <p className="text-[11px] font-semibold text-neutral-200 leading-snug line-clamp-1 group-hover:text-blue-300 transition-colors">
                    {event.title}
                  </p>
                  <div className="flex items-center gap-2 mt-0.5 text-[9px] text-neutral-600">
                    <span className="flex items-center gap-0.5">
                      <Clock size={8} />
                      {formatTime(event.date)}
                    </span>
                    {event.location && (
                      <span className="flex items-center gap-0.5 truncate">
                        <MapPin size={8} />
                        {event.location}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}

          {selectedDayEvents.length > 3 && (
            <p className="text-[9px] text-neutral-600 text-right">
              +{selectedDayEvents.length - 3} więcej
            </p>
          )}
        </div>
      )}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Legend */}
      {!loading && !selectedKey && (
        <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2 mb-1">
          {CATEGORY_LEGEND.map(({ label, color }) => (
            <div key={label} className="flex items-center gap-1">
              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${color}`} />
              <span className="text-[9px] text-neutral-600">{label}</span>
            </div>
          ))}
        </div>
      )}

      {/* See all button */}
      <button
        onClick={() => onNavigate?.('events')}
        className="mt-2 flex items-center justify-center gap-1.5 w-full py-2 rounded-xl bg-white/5 border border-white/8 hover:bg-white/10 hover:border-white/15 transition-all group"
      >
        <span className="text-[10px] font-bold text-neutral-400 group-hover:text-neutral-200 transition-colors">
          Zobacz wszystkie wydarzenia
        </span>
        <ArrowRight size={10} className="text-neutral-500 group-hover:text-neutral-300 group-hover:translate-x-0.5 transition-all" />
      </button>
    </div>
  );
};

export default EventsTile;
