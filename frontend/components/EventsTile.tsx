import React from 'react';
import { CalendarDays, MapPin } from 'lucide-react';
import { useEvents } from '../src/hooks/useEvents';

const EventsTile: React.FC = () => {
  const { events, loading } = useEvents(3);

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return {
      day: d.getDate(),
      month: d.toLocaleDateString('pl-PL', { month: 'short' }).replace('.', ''),
    };
  };

  return (
    <div className="h-full flex flex-col p-5">

      <div className="flex items-center gap-2 mb-4">
        <CalendarDays size={13} className="text-purple-400" />
        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Nadchodzące</p>
      </div>

      {loading ? (
        <div className="space-y-2 flex-1 animate-pulse">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-12 bg-slate-800/50 rounded-xl" />
          ))}
        </div>
      ) : events && events.length > 0 ? (
        <div className="space-y-1.5 flex-1">
          {events.slice(0, 3).map(event => {
            const { day, month } = formatDate(event.date);
            return (
              <div key={event.id} className="flex gap-3 items-start p-2 rounded-xl hover:bg-white/5 transition-colors cursor-default">
                <div className="shrink-0 w-10 h-10 rounded-xl bg-purple-500/20 border border-purple-500/20 flex flex-col items-center justify-center">
                  <span className="text-[8px] text-purple-300 font-bold uppercase leading-none">{month}</span>
                  <span className="text-sm font-black text-purple-200 leading-none mt-0.5">{day}</span>
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-slate-200 leading-snug line-clamp-2">{event.title}</p>
                  {event.location && (
                    <p className="flex items-center gap-1 text-[10px] text-slate-500 mt-0.5">
                      <MapPin size={8} />
                      <span className="truncate">{event.location}</span>
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="text-xs text-slate-500 italic flex-1 pt-2">Brak nadchodzących wydarzeń</p>
      )}
    </div>
  );
};

export default EventsTile;
