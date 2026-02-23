
import React from 'react';
import TrafficWidget from './TrafficWidget';
import { CinemaWidget } from './CinemaWidget';
import BusTrackerWidget from './BusTrackerWidget';
import RegonSearchWidget from './RegonSearchWidget';
import WasteWidget from './WasteWidget';
import WasteWidgetPaywall from './WasteWidgetPaywall';

import { useWasteSchedule } from '../src/hooks/useWasteSchedule';
import { useAuth } from '../src/context/AuthContext';
import { AppSection } from '../types';

import { getHoliday, getNameDays } from '../src/utils/calendarUtils';

import BentoGrid from './BentoGrid';
import BentoTile from './BentoTile';
import PromptBar from './PromptBar';
import AIBriefingTile from './AIBriefingTile';
import WeatherTile from './WeatherTile';
import EventsTile from './EventsTile';
import NewsTile from './NewsTile';

const Dashboard: React.FC<{ onNavigate?: (section: AppSection) => void; onQuerySubmit?: (query: string) => void }> = ({ onNavigate, onQuerySubmit }) => {
  const { user, isPremium, userLocation } = useAuth();
  const wasteEvents = useWasteSchedule(userLocation);

  const today = new Date();
  const holiday = getHoliday(today);
  const nameDays = getNameDays(today);

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700">

      {/* Header */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-violet-400">
            {user ? `Witaj, ${user.full_name.split(' ')[0]}! 👋` : 'Witaj, mieszkańcu! 👋'}
          </h2>
          <p className="text-slate-400">Centrum Dowodzenia RybnoLive gotowe do działania.</p>
        </div>
        <div className="hidden md:flex items-center gap-4 text-slate-300/80">
          <div className="text-right">
            <p className="text-xl font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-violet-400">
              {today.toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'long' })}
            </p>
            {holiday && <p className="text-sm font-medium text-blue-400 mt-0.5">🎉 {holiday}</p>}
            {nameDays && <p className="text-xs text-slate-500 mt-0.5">Imieniny: {nameDays}</p>}
          </div>
          <div className="w-11 h-11 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-xl shadow-inner">
            📅
          </div>
        </div>
      </header>

      {/* PromptBar - AI Assistant Hero */}
      <PromptBar onNavigate={onNavigate} onSubmit={onQuerySubmit} />

      {/* Bento Grid */}
      <BentoGrid>
        {/* AI Daily Briefing - large 2x2 */}
        <BentoTile variant="gradient" colSpan={2} rowSpan={2}>
          <AIBriefingTile onNavigate={onNavigate} />
        </BentoTile>

        {/* Weather */}
        <BentoTile variant="dark">
          <WeatherTile />
        </BentoTile>

        {/* Upcoming Events */}
        <BentoTile variant="glass">
          <EventsTile />
        </BentoTile>

        {/* News horizontal scroll - full remaining width */}
        <BentoTile variant="dark" colSpan={2}>
          <NewsTile />
        </BentoTile>
      </BentoGrid>

      {/* Existing Widgets - 3-col grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* REGON Search */}
        <div className="h-[400px]">
          <RegonSearchWidget />
        </div>

        {/* Right column: Waste + Traffic + Cinema + Bus */}
        <div className="lg:col-span-2 space-y-6">
          {isPremium
            ? <WasteWidget events={wasteEvents} town={userLocation} />
            : user
              ? <WasteWidgetPaywall />
              : null
          }
          <TrafficWidget />
          <CinemaWidget />
          <BusTrackerWidget />
        </div>
      </div>

    </div>
  );
};

export default Dashboard;
