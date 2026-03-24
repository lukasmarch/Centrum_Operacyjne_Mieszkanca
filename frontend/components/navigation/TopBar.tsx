import React from 'react';
import { AppSection } from '../../types';

interface TopBarProps {
  user: { full_name: string; tier: string; location: string; email?: string; avatarUrl?: string } | null;
  isAuthenticated: boolean;
  onNavigate: (section: AppSection) => void;
}

const TopBar: React.FC<TopBarProps> = ({ user, isAuthenticated, onNavigate }) => {
  return (
    <header className="relative z-40 px-4 md:px-8 py-3 flex items-center justify-between">
      {/* Left side empty or reserved for mobile menu toggle later, removed logo per request */}
      <div className="flex items-center gap-2.5">
      </div>

      {/* Location pill */}
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
            onClick={() => onNavigate('profile')}
            className="text-[10px] font-bold uppercase tracking-wider text-neutral-600 hover:text-white transition-colors"
          >
            Zmień
          </button>
        </div>
      )}

      {/* Right: auth */}
      <div className="flex items-center gap-2">
        {isAuthenticated && user ? (
          <div className="flex items-center gap-4 cursor-pointer hover:opacity-80 transition-opacity" onClick={() => onNavigate('profile')}>
            <div className="hidden sm:flex items-center gap-2 pr-4 border-r border-white/10">
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                user.tier === 'business' ? 'bg-indigo-500 text-white' : 
                user.tier === 'premium' ? 'bg-blue-100 text-blue-700' : 
                'bg-white/10 text-neutral-400'
              }`}>
                {user.tier}
              </span>
            </div>
            
            {/* User Profile */}
            <div className="flex items-center gap-3">
              <img 
                src={user.avatarUrl || "https://i.pravatar.cc/150?u=a042581f4e29026024d"} 
                alt="Avatar" 
                className="w-10 h-10 rounded-full object-cover border border-white/10 bg-white/5"
              />
              <div className="hidden sm:flex flex-col">
                <span className="text-sm font-bold text-neutral-100 leading-tight">{user.full_name}</span>
                <span className="text-xs text-neutral-500 leading-tight">{user.email || 'cameron20@mail.com'}</span>
              </div>
            </div>
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
