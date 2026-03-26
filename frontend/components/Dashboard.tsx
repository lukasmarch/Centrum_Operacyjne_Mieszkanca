
import React from 'react';
import { CalendarDays } from 'lucide-react';
import TrafficTile from './TrafficTile';
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
import HeroSection from './hero/HeroSection';
import AIBriefingTile from './AIBriefingTile';
import WeatherTile from './WeatherTile';
import EventsTile from './EventsTile';
import NewsTile from './NewsTile';
import AirlyTile from './AirlyTile';
import GminaMonitoringTile from './GminaMonitoringTile';
import HealthTile from './HealthTile';

import { DASHBOARD_LAYOUTS, TileId } from '../src/config/dashboardLayouts';

const Dashboard: React.FC<{ onNavigate?: (section: AppSection) => void; onQuerySubmit?: (query: string) => void }> = ({ onNavigate, onQuerySubmit }) => {
  const { user, isPremium, userLocation, dashboardLayout } = useAuth();
  const wasteEvents = useWasteSchedule(userLocation);

  const today = new Date();
  const holiday = getHoliday(today);
  const nameDays = getNameDays(today);

  const activeLayout = DASHBOARD_LAYOUTS[dashboardLayout];

  const renderTile = (tileId: TileId): React.ReactNode => {
    switch (tileId) {
      case 'ai_briefing': return <AIBriefingTile onNavigate={onNavigate} />;
      case 'weather':     return <WeatherTile />;
      case 'traffic':     return <TrafficTile />;
      case 'events':      return <EventsTile />;
      case 'airly':       return <AirlyTile />;
      case 'gmina':       return <GminaMonitoringTile />;
      case 'news':        return <NewsTile onNavigate={onNavigate} />;
      default:            return null;
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700">

      {/* Header – style.txt chart colors (blue gradient) */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-4 relative z-[70]">
        <div>
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center font-black text-xl text-white shadow-lg shadow-blue-500/20"
                 style={{ background: 'linear-gradient(135deg, var(--chart-1), var(--chart-2))' }}>
              R
            </div>
            <span className="text-3xl font-black tracking-tight"
                  style={{ background: 'linear-gradient(to right, var(--chart-1), var(--chart-2))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              RybnoLive
            </span>
          </div>
          <h2 className="text-2xl font-black text-neutral-100">
            {user ? `Witaj, ${user.full_name.split(' ')[0]}!` : 'Witaj, mieszkańcu!'}
          </h2>
        </div>
        <div className="hidden md:flex items-center gap-4 text-neutral-400">
          <div className="text-right">
            <p className="text-xl font-black tracking-tight text-gradient" style={{ letterSpacing: '-0.02em' }}>
              {today.toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'long' })}
            </p>
            {holiday && <p className="text-sm font-medium mt-0.5" style={{ color: 'var(--chart-1)' }}>{holiday}</p>}
            {nameDays && <p className="text-xs text-neutral-600 mt-0.5">Imieniny: {nameDays}</p>}
          </div>
          {/* SVG icon zamiast emoji – style.txt compliance */}
          <div className="w-11 h-11 rounded-xl bg-black border border-white/10 flex items-center justify-center shadow-inner">
            <CalendarDays size={20} style={{ color: 'var(--chart-2)' }} />
          </div>
        </div>
      </header>

      {/* Hero – full-bleed: ujemne marginesy znoszą padding kontenera.
          -mt-10: likwiduje space-y-6 i wsuwamy się pod header by poświata kuli
          przebijała się przez dolną część nagłówka. */}
      <div className="-mx-4 md:-mx-8 -mt-10 relative z-[60] pointer-events-none">
        <div className="pointer-events-auto">
          <HeroSection onNavigate={onNavigate} onSubmit={onQuerySubmit} />
        </div>
      </div>

      {/* bentogrid.txt: BentoGrid z dark tiles */}
      <BentoGrid>
        {activeLayout.tiles.map((tile) => (
          <BentoTile
            key={tile.id}
            variant={tile.variant}
            colSpan={tile.colSpan}
            rowSpan={tile.rowSpan}
          >
            {renderTile(tile.id)}
          </BentoTile>
        ))}
      </BentoGrid>

      {/* Cinema + Health + Firmy */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <BentoTile className="h-[500px]" colSpan={1} rowSpan={1}>
          <CinemaWidget />
        </BentoTile>
        <BentoTile className="h-[500px]" colSpan={1} rowSpan={1}>
          <HealthTile />
        </BentoTile>
        <BentoTile className="h-[500px]" colSpan={1} rowSpan={1}>
          <RegonSearchWidget />
        </BentoTile>
      </div>

      <BentoTile colSpan={1} rowSpan={1}>
        <BusTrackerWidget />
      </BentoTile>

      <BentoTile colSpan={1} rowSpan={1}>
        {isPremium
          ? <WasteWidget events={wasteEvents} town={userLocation} />
          : user ? <WasteWidgetPaywall /> : null
        }
      </BentoTile>
    </div>
  );
};

export default Dashboard;
