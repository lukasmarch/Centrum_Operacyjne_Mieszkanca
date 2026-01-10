
import React from 'react';
import { AppSection } from '../types';

interface SidebarProps {
  activeSection: AppSection;
  onSectionChange: (section: AppSection) => void;
}

const Sidebar: React.FC<SidebarProps> = ({ activeSection, onSectionChange }) => {
  const menuItems: { id: AppSection; label: string; icon: string }[] = [
    { id: 'dashboard', label: 'Panel Główny', icon: '🏠' },
    { id: 'news', label: 'Wiadomości', icon: '📰' },
    { id: 'events', label: 'Wydarzenia', icon: '📅' },
    { id: 'weather', label: 'Pogoda i Jeziora', icon: '🌊' },
    { id: 'traffic', label: 'Ruch Drogowy', icon: '🚗' },
    { id: 'stats', label: 'Statystyki GUS', icon: '📊' },
    { id: 'premium', label: 'Strefa Premium', icon: '⭐' },
  ];

  return (
    <aside className="fixed left-0 top-0 h-screen w-64 bg-slate-900 text-white p-6 z-50 transition-all duration-300 md:translate-x-0 -translate-x-full">
      <div className="flex items-center gap-3 mb-10">
        <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center font-bold text-xl">D</div>
        <div>
          <h1 className="font-bold text-lg leading-tight">Działdowo<span className="text-blue-400">Live</span></h1>
          <p className="text-xs text-slate-400 italic">Centrum Operacyjne</p>
        </div>
      </div>

      <nav className="space-y-1">
        {menuItems.map((item) => (
          <button
            key={item.id}
            onClick={() => onSectionChange(item.id)}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
              activeSection === item.id 
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/50' 
                : 'text-slate-400 hover:bg-slate-800 hover:text-white'
            }`}
          >
            <span className="text-xl">{item.icon}</span>
            <span className="font-medium">{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="absolute bottom-10 left-6 right-6 p-4 bg-slate-800/50 rounded-2xl border border-slate-700">
        <p className="text-xs text-slate-400 mb-2">Pobierz aplikację mobilną</p>
        <div className="flex gap-2">
            <div className="w-full h-8 bg-slate-700 rounded flex items-center justify-center text-[10px]">App Store</div>
            <div className="w-full h-8 bg-slate-700 rounded flex items-center justify-center text-[10px]">Google Play</div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
