import React, { useState, useRef, useEffect } from 'react';
import { User, Settings, LogOut, Crown, Zap } from 'lucide-react';
import { AppSection } from '../../types';

interface TopBarProps {
  user: { full_name: string; tier: string; location: string; email?: string; avatarUrl?: string } | null;
  isAuthenticated: boolean;
  onNavigate: (section: AppSection | 'logout' | 'preferences' | 'subscription') => void;
}

const TIER_LABELS: Record<string, string> = {
  free: 'Free',
  premium: 'Premium',
  business: 'Pro',
};

const TIER_COLORS: Record<string, string> = {
  free: 'bg-white/10 text-neutral-400',
  premium: 'bg-blue-500/20 text-blue-300 border border-blue-500/30',
  business: 'bg-violet-500/20 text-violet-300 border border-violet-500/30',
};

const AI_LIMITS: Record<string, { used: number; max: number; label: string }> = {
  free: { used: 4, max: 10, label: '4/10 pytań AI dziś' },
  premium: { used: 0, max: -1, label: 'Nieograniczone pytania AI' },
  business: { used: 0, max: -1, label: 'Nieograniczone pytania AI' },
};

const TopBar: React.FC<TopBarProps> = ({ user, isAuthenticated, onNavigate }) => {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleNavigate = (section: AppSection | 'logout' | 'preferences' | 'subscription') => {
    setDropdownOpen(false);
    onNavigate(section);
  };

  const tier = user?.tier ?? 'free';
  const aiInfo = AI_LIMITS[tier] ?? AI_LIMITS.free;

  return (
    <header className="relative z-40 px-4 md:px-8 py-3 flex items-center justify-between">
      {/* Left side */}
      <div className="flex items-center gap-2.5" />

      {/* Location pill - desktop */}
      {isAuthenticated && user && (
        <div className="absolute left-1/2 -translate-x-1/2 hidden md:flex items-center gap-3 bg-black/60 backdrop-blur-md border border-white/10 rounded-full py-1.5 px-5">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
          </span>
          <span className="text-xs text-neutral-400">
            <strong className="text-blue-300 font-semibold">{user.location}</strong>
          </span>
          <button
            onClick={() => handleNavigate('profile')}
            className="text-[10px] font-bold uppercase tracking-wider text-neutral-600 hover:text-white transition-colors"
          >
            Zmień
          </button>
        </div>
      )}

      {/* Right: auth */}
      <div className="flex items-center gap-2">
        {isAuthenticated && user ? (
          <div className="relative" ref={dropdownRef}>
            {/* Avatar + badge + name — single clickable button */}
            <button
              onClick={() => setDropdownOpen((v) => !v)}
              className="flex items-center gap-2.5 hover:opacity-90 transition-opacity focus:outline-none"
            >
              {tier !== 'free' && (
                <span
                  onClick={(e) => { e.stopPropagation(); setDropdownOpen(false); onNavigate('subscription'); }}
                  className={`hidden sm:flex items-center gap-1 px-2.5 py-1 rounded-full text-[9px] font-bold uppercase tracking-wider cursor-pointer hover:opacity-80 transition-opacity ${TIER_COLORS[tier]}`}
                >
                  {tier === 'business' && <Zap size={9} />}
                  {tier === 'premium' && <Crown size={9} />}
                  {TIER_LABELS[tier]}
                </span>
              )}
              <div className="hidden sm:flex flex-col items-end gap-0.5">
                <span className="text-sm font-bold text-neutral-100 leading-tight">{user.full_name}</span>
                <span className="text-[11px] text-neutral-500 leading-tight">{user.email ?? ''}</span>
              </div>
              {user.avatarUrl ? (
                <img
                  src={user.avatarUrl}
                  alt="Avatar"
                  className="w-9 h-9 rounded-full object-cover border border-white/10 bg-white/5"
                />
              ) : (
                <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center font-bold text-sm text-white border border-white/10">
                  {user.full_name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)}
                </div>
              )}
            </button>

            {/* Dropdown */}
            {dropdownOpen && (
              <div className="absolute right-0 top-full mt-2 w-72 bg-[#111318] border border-white/10 rounded-2xl shadow-2xl shadow-black/60 overflow-hidden z-50">
                {/* User header */}
                <div className="px-4 py-4 border-b border-white/8">
                  <div className="flex items-center gap-3">
                    {user.avatarUrl ? (
                      <img src={user.avatarUrl} alt="Avatar" className="w-10 h-10 rounded-full object-cover" />
                    ) : (
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center font-bold text-sm text-white">
                        {user.full_name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)}
                      </div>
                    )}
                    <div>
                      <p className="font-semibold text-sm text-white leading-tight">{user.full_name}</p>
                      <p className="text-xs text-neutral-500">{TIER_LABELS[tier]} Plan</p>
                    </div>
                  </div>

                  {/* Credits bar (free only) */}
                  {tier === 'free' && (
                    <div className="mt-3">
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-xs text-amber-400 font-medium">{aiInfo.label}</span>
                      </div>
                      <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-amber-500 to-red-500 rounded-full transition-all"
                          style={{ width: `${(aiInfo.used / aiInfo.max) * 100}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* Menu items */}
                <div className="py-2">
                  <button
                    onClick={() => handleNavigate('profile')}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-neutral-300 hover:text-white hover:bg-white/5 transition-colors"
                  >
                    <User size={15} className="text-neutral-500" />
                    Profil
                  </button>
                  <button
                    onClick={() => handleNavigate('preferences')}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-neutral-300 hover:text-white hover:bg-white/5 transition-colors"
                  >
                    <Settings size={15} className="text-neutral-500" />
                    Preferencje
                  </button>
                </div>

                <div className="border-t border-white/8 py-2">
                  <button
                    onClick={() => handleNavigate('logout')}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-neutral-500 hover:text-red-400 hover:bg-red-500/5 transition-colors"
                  >
                    <LogOut size={15} />
                    Wyloguj się
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <button
              onClick={() => onNavigate('login')}
              className="text-neutral-400 hover:text-white px-3 py-1.5 rounded-full transition-colors font-medium text-sm"
            >
              Zaloguj
            </button>
            <button
              onClick={() => onNavigate('register')}
              className="btn-primary rounded-full"
            >
              Zarejestruj
            </button>
          </div>
        )}
      </div>
    </header>
  );
};

export default TopBar;
