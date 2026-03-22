import React from 'react';
import { AppSection } from '../../types';

interface TopBarProps {
  user: { full_name: string; tier: string; location: string } | null;
  isAuthenticated: boolean;
  onNavigate: (section: AppSection) => void;
}

const TopBar: React.FC<TopBarProps> = ({ user, isAuthenticated, onNavigate }) => {
  return (
    <header className="relative z-40 px-4 md:px-8 py-3 flex items-center justify-between">
      {/* Logo */}
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-violet-600 rounded-lg flex items-center justify-center font-bold text-sm text-white shadow-lg shadow-blue-500/20">
          R
        </div>
        <div className="hidden sm:block">
          <span className="text-sm font-bold text-white tracking-tight">RybnoLive</span>
          <span className="text-[9px] text-neutral-500 font-medium uppercase tracking-widest block -mt-0.5">Centrum Operacyjne</span>
        </div>
      </div>

      {/* Location pill (center) */}
      {isAuthenticated && user && (
        <div className="absolute left-1/2 -translate-x-1/2 hidden md:flex items-center gap-3 bg-black/60 backdrop-blur-md border border-white/10 rounded-full py-1.5 px-5">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500" />
          </span>
          <span className="text-xs text-neutral-400">
            <strong className="text-indigo-300 font-semibold">{user.location}</strong>
          </span>
          <button
            onClick={() => onNavigate('profile')}
            className="text-[10px] font-bold uppercase tracking-wider text-neutral-600 hover:text-white transition-colors"
          >
            Zmień
          </button>
        </div>
      )}

      {/* Right side: auth */}
      <div className="flex items-center gap-2">
        {isAuthenticated && user ? (
          <button
            onClick={() => onNavigate('profile')}
            className="group transition-transform hover:scale-105 active:scale-95"
          >
            <div className={`px-4 py-1.5 rounded-full font-bold text-white text-xs shadow-lg tracking-wide bg-gradient-to-r ${
              user.tier === 'business' ? 'from-blue-600 via-indigo-600 to-purple-600 shadow-indigo-500/20' :
              user.tier === 'premium' ? 'from-indigo-500 via-purple-500 to-pink-500 shadow-purple-500/20' :
              'from-neutral-700 to-neutral-600'
            }`}>
              {user.tier === 'business' ? 'Business' : user.tier === 'premium' ? 'Premium' : 'Free'}
            </div>
          </button>
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
              className="bg-gradient-to-b from-white via-white/95 to-white/70 text-black px-4 py-1.5 rounded-full transition-all shadow-lg hover:shadow-white/20 hover:scale-105 active:scale-95 text-sm font-bold"
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
