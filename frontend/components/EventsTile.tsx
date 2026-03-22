import React from 'react';
import { CalendarDays, MapPin } from 'lucide-react';
import { useEvents } from '../src/hooks/useEvents';

const EventsTile: React.FC = () => {
  const { events, loading } = useEvents(3);

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return {
      day: d.getDate(),
      month: d.toLocaleDateString('pl-PL', { month: 'short' }).replace('.', '').toUpperCase(),
    };
  };

  const formatTime = (dateStr: string) => {
    const d = new Date(dateStr);
    const h = d.getHours();
    const m = d.getMinutes();
    if (h === 0 && m === 0) return '';
    return `${h}:${m.toString().padStart(2, '0')}`;
  };

  return (
    <div className="h-full flex flex-col p-5">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <CalendarDays size={14} className="text-blue-400" />
        <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider">Wydarzenia</p>
      </div>

      {loading ? (
        <div className="space-y-2 flex-1 animate-pulse">
          {[1, 2].map(i => (
            <div key={i} className="h-20 bg-gray-900/50 rounded-xl" />
          ))}
        </div>
      ) : events && events.length > 0 ? (
        <div className="flex flex-col flex-1">
          {/* Featured event */}
          {(() => {
            const featured = events[0];
            const { day, month } = formatDate(featured.date);
            return (
              <div className="cursor-pointer group">
                {/* Image with date badge */}
                <div className="relative rounded-xl overflow-hidden h-[130px] mb-3">
                  {featured.imageUrl ? (
                    <img
                      src={featured.imageUrl}
                      alt={featured.title}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                    />
                  ) : (
                    <div className="w-full h-full bg-gradient-to-br from-blue-900/40 to-gray-900" />
                  )}

                  {/* Date badge - top right */}
                  <div className="absolute top-2.5 right-2.5 w-10 h-10 rounded-lg bg-gray-950/80 backdrop-blur-sm border border-white/10 flex flex-col items-center justify-center">
                    <span className="text-[7px] text-neutral-400 font-bold uppercase leading-none">{month}</span>
                    <span className="text-sm font-black text-white leading-none">{day}</span>
                  </div>
                </div>

                {/* Title & location below image */}
                <h4 className="text-sm font-bold text-blue-400 leading-snug line-clamp-2 group-hover:text-blue-300 transition-colors">
                  {featured.title}
                </h4>
                {featured.location && (
                  <p className="flex items-center gap-1 text-[10px] text-neutral-500 mt-1">
                    <MapPin size={9} className="shrink-0" />
                    <span className="truncate">{featured.location}</span>
                  </p>
                )}
              </div>
            );
          })()}

          {/* Separator */}
          <div className="border-t border-white/5 my-3" />

          {/* Secondary events */}
          <div className="space-y-1.5 mt-auto">
            {events.slice(1, 3).map(event => {
              const { day } = formatDate(event.date);
              const time = formatTime(event.date);
              return (
                <div key={event.id} className="flex gap-3 items-center p-2 rounded-lg hover:bg-white/5 transition-colors cursor-default">
                  <div className="shrink-0 w-9 h-9 rounded-lg bg-gray-900 border border-gray-700/50/50 flex items-center justify-center">
                    <span className="text-xs font-black text-neutral-300">{day}</span>
                  </div>
                  <div className="min-w-0">
                    <p className="text-[11px] font-semibold text-neutral-200 leading-snug line-clamp-1">{event.title}</p>
                    <p className="text-[9px] text-neutral-500 mt-0.5 truncate">
                      {event.location}{time ? `, ${time}` : ''}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <p className="text-xs text-neutral-500 italic flex-1 pt-2">Brak nadchodzących wydarzeń</p>
      )}
    </div>
  );
};

export default EventsTile;
