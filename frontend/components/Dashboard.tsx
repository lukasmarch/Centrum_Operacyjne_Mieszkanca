
import React from 'react';
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
      case 'ai_briefing':
        return <AIBriefingTile onNavigate={onNavigate} />;
      case 'weather':
        return <WeatherTile />;
      case 'traffic':
        return <TrafficTile />;
      case 'events':
        return <EventsTile />;
      case 'airly':
        return <AirlyTile />;
      case 'gmina':
        return <GminaMonitoringTile />;
      case 'news':
        return <NewsTile onNavigate={onNavigate} />;
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700">

      {/* Header */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-violet-400">
            {user ? `Witaj, ${user.full_name.split(' ')[0]}! 👋` : 'Witaj, mieszkańcu! 👋'}
          </h2>
          <p className="text-neutral-400">Centrum Dowodzenia RybnoLive gotowe do działania.</p>
        </div>
        <div className="hidden md:flex items-center gap-4 text-neutral-300/80">
          <div className="text-right">
            <p className="text-xl font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-violet-400">
              {today.toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'long' })}
            </p>
            {holiday && <p className="text-sm font-medium text-blue-400 mt-0.5">🎉 {holiday}</p>}
            {nameDays && <p className="text-xs text-neutral-500 mt-0.5">Imieniny: {nameDays}</p>}
          </div>
          <div className="w-11 h-11 rounded-xl bg-gray-900 border border-gray-800/50 flex items-center justify-center text-xl shadow-inner">
            📅
          </div>
        </div>
      </header>

      {/* Hero Section - AI Assistant with Spline 3D */}
      <HeroSection onNavigate={onNavigate} onSubmit={onQuerySubmit} />

      {/* ===== BENTO GRID (data-driven by layout preset) ===== */}
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

      {/* ===== BELOW GRID: Cinema + Health + Firmy (3 columns) ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Repertuar kina */}
        <div className="h-[500px]">
          <CinemaWidget />
        </div>

        {/* Twoje Zdrowie */}
        <HealthTile />

        {/* Katalog Firm */}
        <div className="h-[500px]">
          <RegonSearchWidget />
        </div>
      </div>

      {/* ===== Bus Monitoring – full width ===== */}
      <BusTrackerWidget />

      {/* ===== Waste (premium) ===== */}
      {isPremium
        ? <WasteWidget events={wasteEvents} town={userLocation} />
        : user
          ? <WasteWidgetPaywall />
          : null
      }

    </div>
  );
};

export default Dashboard;
