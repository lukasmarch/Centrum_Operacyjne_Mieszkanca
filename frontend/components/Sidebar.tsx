
import React from 'react';
import { AppSection, User } from '../types';
import {
  Home,
  Newspaper,
  CalendarDays,
  CloudSun,
  Car,
  BarChart3,
  Building2,
  Megaphone,
  Sparkles,
  LogOut,
  User as UserIcon,
  Menu,
  LogIn
} from 'lucide-react';

interface SidebarProps {
  activeSection: AppSection;
  onSectionChange: (section: AppSection | 'logout') => void;
  user: User | null;
  isOpen: boolean;
  onToggle: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ activeSection, onSectionChange, user, isOpen, onToggle }) => {
  const menuItems: { id: AppSection; label: string; icon: React.ReactNode; requiresAuth?: boolean }[] = [
    { id: 'dashboard', label: 'Panel Główny', icon: <Home size={20} /> },
    { id: 'news', label: 'Wiadomości', icon: <Newspaper size={20} /> },
    { id: 'events', label: 'Wydarzenia', icon: <CalendarDays size={20} /> },
    { id: 'weather', label: 'Pogoda i Powietrze', icon: <CloudSun size={20} /> },
    { id: 'traffic', label: 'Ruch Drogowy', icon: <Car size={20} /> },
    { id: 'stats', label: 'Statystyki GUS', icon: <BarChart3 size={20} /> },
    { id: 'business', label: 'Katalog Firm', icon: <Building2 size={20} /> },
    { id: 'reports', label: 'Zgłoszenie24', icon: <Megaphone size={20} /> },
    { id: 'premium', label: 'Strefa Premium', icon: <Sparkles size={20} /> },
  ];

  const isAuthenticated = !!user;

  return (
    <>
      {/* Mobile Backdrop */}
      <div
        className={`fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-40 transition-opacity duration-300 md:hidden ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        onClick={onToggle}
      />

      <aside className={`fixed left-0 top-0 bottom-0 w-64 bg-slate-950/50 md:bg-transparent border-r border-white/5 md:border-none backdrop-blur-xl md:backdrop-blur-none z-50 transition-transform duration-300 flex flex-col p-4 md:p-6 ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}>

        {/* Brand */}
        <div className="flex items-center gap-3 mb-8 px-2">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <span className="font-black text-white italic text-lg leading-none pt-0.5">R</span>
          </div>
          <div>
            <h1 className="font-bold text-slate-100 leading-none tracking-tight">Rybno<span className="text-blue-500">Live</span></h1>
            <p className="text-[10px] text-slate-500 font-medium tracking-widest uppercase mt-0.5">Centrum Operacyjne</p>
          </div>
        </div>

        {/* Main navigation */}
        <nav className="space-y-1 flex-1 overflow-y-auto scrollbar-hide">
          {menuItems.map((item) => (
            <button
              key={item.id}
              onClick={() => onSectionChange(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-sm font-medium group relative ${activeSection === item.id
                ? 'text-blue-400 bg-blue-500/10'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                }`}
            >
              {activeSection === item.id && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-blue-500 rounded-r-full"></div>
              )}
              <span className={`transition-transform ${activeSection === item.id ? 'scale-110' : 'group-hover:scale-110'}`}>{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        {/* Footer / User */}
        <div className="pt-4 mt-4 border-t border-white/5">
          {isAuthenticated && user ? (
            <div className="space-y-2">
              <button
                onClick={() => onSectionChange('profile')}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-all group ${activeSection === 'profile'
                  ? 'bg-blue-500/10'
                  : 'hover:bg-white/5'
                  }`}
              >
                <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 text-xs font-bold group-hover:border-blue-500/50 transition-colors">
                  {user.full_name.split(' ').map(n => n[0]).join('').toUpperCase()}
                </div>
                <div className="flex-1 text-left min-w-0">
                  <p className="font-medium text-slate-200 text-sm truncate">{user.full_name}</p>
                  <p className="text-[10px] text-slate-500 truncate">{user.email}</p>
                </div>
              </button>

              <button
                onClick={() => onSectionChange('logout')}
                className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-colors text-sm font-medium"
              >
                <LogOut size={16} />
                <span>Wyloguj się</span>
              </button>
            </div>
          ) : (
            <button
              onClick={() => onSectionChange('login')}
              className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-slate-400 hover:text-white hover:bg-blue-600/20 transition-colors text-sm font-medium"
            >
              <LogIn size={16} />
              <span>Zaloguj się</span>
            </button>
          )}
        </div>
      </aside >
    </>
  );
};

export default Sidebar;
