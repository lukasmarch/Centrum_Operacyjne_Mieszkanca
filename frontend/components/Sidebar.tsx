
import React from 'react';
import { AppSection, User } from '../types';

interface SidebarProps {
  activeSection: AppSection;
  onSectionChange: (section: AppSection | 'logout') => void;
  user: User | null;
  isOpen: boolean;
  onToggle: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ activeSection, onSectionChange, user, isOpen, onToggle }) => {
  const menuItems: { id: AppSection; label: string; icon: string; requiresAuth?: boolean }[] = [
    { id: 'dashboard', label: 'Panel Główny', icon: '🏠' },
    { id: 'news', label: 'Wiadomości', icon: '📰' },
    { id: 'events', label: 'Wydarzenia', icon: '📅' },
    { id: 'weather', label: 'Pogoda i Powietrze', icon: '🌊' },
    { id: 'traffic', label: 'Ruch Drogowy', icon: '🚗' },
    { id: 'stats', label: 'Statystyki GUS', icon: '📊' },
    { id: 'business', label: 'Katalog Firm', icon: '🏢' },
    { id: 'reports', label: 'Zgłoszenie24', icon: '🚨' },
    { id: 'premium', label: 'Strefa Premium', icon: '⭐' },
  ];

  const isAuthenticated = !!user;

  return (
    <aside className={`fixed left-0 top-0 h-screen w-64 bg-slate-900 text-white p-6 z-50 transition-all duration-300 flex flex-col ${
      isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
    }`}>
      <div className="flex items-center gap-3 mb-10">
        <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center font-bold text-xl">D</div>
        <div>
          <h1 className="font-bold text-lg leading-tight">Działdowo<span className="text-blue-400">Live</span></h1>
          <p className="text-xs text-slate-400 italic">Centrum Operacyjne</p>
        </div>
      </div>

      {/* Main navigation */}
      <nav className="space-y-1 flex-1">
        {menuItems.map((item) => (
          <button
            key={item.id}
            onClick={() => onSectionChange(item.id)}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${activeSection === item.id
              ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/50'
              : 'text-slate-400 hover:bg-slate-800 hover:text-white'
              }`}
          >
            <span className="text-xl">{item.icon}</span>
            <span className="font-medium">{item.label}</span>
          </button>
        ))}
      </nav>

      {/* User section */}
      <div className="border-t border-slate-700 pt-4 mt-4">
        {isAuthenticated && user ? (
          <div className="space-y-2">
            {/* Profile button */}
            <button
              onClick={() => onSectionChange('profile')}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${activeSection === 'profile'
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/50'
                : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                }`}
            >
              <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center font-bold text-sm">
                {user.full_name.split(' ').map(n => n[0]).join('').toUpperCase()}
              </div>
              <div className="flex-1 text-left">
                <p className="font-medium text-sm leading-tight">{user.full_name}</p>
                <p className="text-xs text-slate-500">{user.location}</p>
              </div>
              {user.tier === 'premium' && (
                <span className="text-xs bg-blue-400/20 text-blue-300 px-1.5 py-0.5 rounded font-bold">PRO</span>
              )}
            </button>

            {/* Logout button */}
            <button
              onClick={() => onSectionChange('logout')}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-slate-500 hover:bg-slate-800 hover:text-red-400 transition-all"
            >
              <span className="text-xl">🚪</span>
              <span className="font-medium">Wyloguj się</span>
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <button
              onClick={() => onSectionChange('login')}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${activeSection === 'login'
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                }`}
            >
              <span className="text-xl">🔑</span>
              <span className="font-medium">Zaloguj się</span>
            </button>
            <button
              onClick={() => onSectionChange('register')}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${activeSection === 'register'
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                }`}
            >
              <span className="text-xl">✨</span>
              <span className="font-medium">Zarejestruj się</span>
            </button>
          </div>
        )}
      </div>

      {/* App download section */}
      <div className="mt-4 p-4 bg-slate-800/50 rounded-2xl border border-slate-700">
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
