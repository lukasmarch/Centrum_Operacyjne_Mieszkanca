import React, { useState, useRef, useEffect } from 'react';
import { User, Settings, LogOut, Crown, Zap, LogIn } from 'lucide-react';
import { AppSection } from '../../types';

interface TopBarProps {
  user: { full_name: string; tier: string; location: string; email?: string; avatarUrl?: string } | null;
  isAuthenticated: boolean;
  onNavigate: (section: AppSection | 'logout' | 'preferences' | 'subscription') => void;
}

const TIER_LABELS: Record<string, string> = {
  free: 'Free',
  premium: 'Premium',
  business: 'Firma',
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
    // Przyklejony, bo to jedyne miejsce ze znakiem marki i z „Zarejestruj":
    // przy stronie długiej na trzy ekrany oba znikały po pierwszym przewinięciu.
    // Rozmycie zamiast pełnego tła — pasmo powitalne ma pod nim prześwitywać
    <header className="sticky top-0 z-40 flex items-center justify-between border-b border-white/5 bg-[#05080f]/80 px-4 py-3 backdrop-blur-md md:px-8">
      {/*
        Znak marki. Do 11.08.2026 stał w nagłówku bento-panelu (`Dashboard.tsx`),
        więc razem z wycofaniem panelu zniknął z CAŁEGO serwisu — zostało tu puste
        `<div/>`. Miejsce jest teraz właściwsze: górny pasek widać na każdej
        podstronie, więc „R" i nazwa wracają też na cenniku, w wiadomościach
        i na stronach, które ktoś otworzy prosto z Google.

        Nazwa stoi obok „R" TAKŻE na telefonie. Wcześniej była ukryta poniżej
        640 px, bo pełna nazwa i trzy przyciski nie mieszczą się w jednym wierszu
        — ale to znaczyło, że ktoś wchodzący z Google na telefonie (czyli
        większość) nie widział nazwy serwisu nigdzie nad zgięciem. Miejsce
        wygospodarowane po prawej: „Zaloguj" schodzi do samej ikony, a „Cennik"
        i „Zarejestruj" dostają ciaśniejsze paddingi (zmierzone przy 360 px:
        122 px po lewej + 188 px po prawej = 310 z 320 dostępnych).
      */}
      <a
        href="/"
        onClick={(e) => {
          if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
          e.preventDefault();
          onNavigate('dashboard');
        }}
        aria-label="RybnoLive — strona główna"
        className="flex shrink-0 items-center gap-2 transition-opacity hover:opacity-90 sm:gap-2.5"
      >
        <span
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-lg font-black text-white shadow-lg shadow-blue-500/20"
          style={{ background: 'linear-gradient(135deg, var(--chart-1), var(--chart-2))' }}
        >
          R
        </span>
        <span
          // Poniżej 340 px (stare iPhone'y SE) nazwa znika — tam nawet ciasny
          // wiersz się nie mieści i pasek zaczyna przewijać się w poziomie
          className="hidden text-base font-black tracking-tight min-[340px]:inline sm:text-2xl"
          style={{
            background: 'linear-gradient(to right, var(--chart-1), var(--chart-2))',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}
        >
          RybnoLive
        </span>
      </a>

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
                    onClick={() => handleNavigate('premium')}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-neutral-300 hover:text-white hover:bg-white/5 transition-colors"
                  >
                    <Crown size={15} className="text-neutral-500" />
                    Cennik i plany
                  </button>
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
          <div className="flex items-center gap-1 sm:gap-2">
            {/* Oferta płatna dostępna z każdej podstrony, także bez konta —
                wymóg weryfikacji Przelewy24 (oferta + przejście przez zakup).
                Dlatego „Cennik" zostaje słowem także na telefonie: ikona byłaby
                oszczędnością 20 px kosztem jedynego widocznego wejścia w ofertę */}
            <a
              href="/cennik"
              onClick={(e) => {
                if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
                e.preventDefault();
                onNavigate('premium');
              }}
              className="rounded-full px-2 py-1.5 text-[13px] font-medium text-neutral-400 transition-colors hover:text-white sm:px-3 sm:text-sm"
            >
              Cennik
            </a>
            {/* Na telefonie sama ikona: „Zaloguj" to jedyny z trzech przycisków,
                który dotyczy wyłącznie osób już zarejestrowanych — a te wiedzą,
                czego szukają. „Cennik" i „Zarejestruj" mówią do nowego i muszą
                zostać słowami */}
            <button
              onClick={() => onNavigate('login')}
              aria-label="Zaloguj się"
              className="flex h-9 w-9 items-center justify-center rounded-full text-neutral-400 transition-colors hover:text-white sm:h-auto sm:w-auto sm:px-3 sm:py-1.5 sm:text-sm sm:font-medium"
            >
              <LogIn size={18} aria-hidden className="sm:hidden" />
              <span className="hidden sm:inline">Zaloguj</span>
            </button>
            <button
              onClick={() => onNavigate('register')}
              className="btn-primary rounded-full !px-3 !py-2.5 !text-[13px] sm:!px-5 sm:!py-3 sm:!text-sm"
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
