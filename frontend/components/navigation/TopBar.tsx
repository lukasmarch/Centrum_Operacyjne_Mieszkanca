import React, { useState, useRef, useEffect } from 'react';
import { User, Settings, LogOut, Crown, Zap, LogIn } from 'lucide-react';
import { AppSection } from '../../types';

export interface TopNavItem {
  id: AppSection;
  label: string;
  href: string;
}

interface TopBarProps {
  user: { full_name: string; tier: string; location: string; email?: string; avatarUrl?: string } | null;
  isAuthenticated: boolean;
  onNavigate: (section: AppSection | 'logout' | 'preferences' | 'subscription') => void;
  /** Sekcje w drugim wierszu nagłówka — tylko od `lg`, na telefonie nawigacją jest dolna belka */
  navItems?: TopNavItem[];
  activeSection?: AppSection;
}

const TIER_LABELS: Record<string, string> = {
  free: 'Free',
  premium: 'Premium',
  business: 'Firma',
};

const TIER_COLORS: Record<string, string> = {
  free: 'bg-tv-seam text-tv-paper',
  premium: 'bg-tv-blue text-white',
  business: 'bg-tv-paper text-tv-ink',
};

// Opis planu słowami. Do 11.10.2026 stał tu pasek „4/10 pytań AI dziś” z liczbami
// wpisanymi na sztywno — nieprawdziwy dla każdego (plan darmowy to 5 pytań dziennie,
// a licznik nigdy nie był podłączony). Prawda albo nic: zostaje sam limit.
const AI_LIMITS: Record<string, { label: string }> = {
  free: { label: 'Plan darmowy: 5 pytań do asystenta dziennie' },
  premium: { label: 'Pytania do asystenta bez limitu' },
  business: { label: 'Pytania do asystenta bez limitu' },
};

const MENU: { id: 'premium' | 'profile' | 'preferences'; label: string; Icon: typeof User }[] = [
  { id: 'profile', label: 'Profil i miejscowość', Icon: User },
  { id: 'preferences', label: 'Preferencje', Icon: Settings },
  { id: 'premium', label: 'Cennik i plany', Icon: Crown },
];

/** Inicjały albo zdjęcie — kwadrat, jak każda miniatura w tym świecie */
const Initials: React.FC<{ user: NonNullable<TopBarProps['user']>; size: string }> = ({ user, size }) =>
  user.avatarUrl ? (
    <img src={user.avatarUrl} alt="" className={`${size} shrink-0 bg-tv-panel2 object-cover`} />
  ) : (
    <span aria-hidden className={`font-cond flex ${size} shrink-0 items-center justify-center bg-tv-blue font-extrabold text-white`}>
      {user.full_name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)}
    </span>
  );

const TopBar: React.FC<TopBarProps> = ({ user, isAuthenticated, onNavigate, navItems = [], activeSection }) => {
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
    <header className="sticky top-0 z-40 border-b border-tv-seam bg-tv-ink">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-2.5 md:px-8">
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
        className="flex shrink-0 items-center transition-opacity hover:opacity-90"
      >
        {/* Znak: „Rybno” + plakietka „Live” — ta sama plakietka, co w belce
            i sekcjach pulpitu. Bez gradientu i poświaty (odświeżenie 10.2026).
            Czyta się dalej jako jedna nazwa: RybnoLive */}
        <span className="font-cond flex items-center text-[22px] font-black leading-none text-white sm:text-[26px]">
          Rybno
          <span className="ml-0.5 bg-tv-blue px-1.5 py-1 text-[17px] uppercase tracking-wide text-white sm:text-[20px]">Live</span>
        </span>
      </a>

      {/* Right: auth */}
      <div className="flex items-center gap-2">
        {isAuthenticated && user ? (
          <div className="relative" ref={dropdownRef}>
            {/* Avatar + badge + name — single clickable button */}
            <button
              onClick={() => setDropdownOpen((v) => !v)}
              aria-expanded={dropdownOpen}
              aria-label={`Konto: ${user.full_name}`}
              className="flex min-h-[44px] items-center gap-2.5 transition-opacity hover:opacity-90"
            >
              {tier !== 'free' && (
                <span
                  onClick={(e) => { e.stopPropagation(); setDropdownOpen(false); onNavigate('subscription'); }}
                  className={`font-cond hidden sm:flex items-center gap-1 px-2 py-1 text-[13px] font-extrabold uppercase tracking-wide cursor-pointer hover:opacity-80 transition-opacity ${TIER_COLORS[tier]}`}
                >
                  {tier === 'business' && <Zap size={9} />}
                  {tier === 'premium' && <Crown size={9} />}
                  {TIER_LABELS[tier]}
                </span>
              )}
              <div className="hidden sm:flex flex-col items-end gap-0.5">
                <span className="text-[15px] font-bold text-white leading-tight">{user.full_name}</span>
                <span className="text-[13px] text-tv-muted leading-tight">{user.email ?? ''}</span>
              </div>
              <Initials user={user} size="h-11 w-11 text-[16px]" />
            </button>

            {/* Menu konta — płaski panel ze szwem, jak rozwijany wybór wsi.
                Do 11.10.2026 stało tu zaokrąglone okno z cieniem i gradientowym
                awatarem — ostatni kawałek starego świata w szkielecie */}
            {dropdownOpen && (
              <div
                className="absolute right-0 top-full z-50 mt-2 w-72 border border-tv-seam bg-tv-panel"
                onKeyDown={(e) => { if (e.key === 'Escape') setDropdownOpen(false); }}
              >
                <div className="border-t-2 border-tv-blue px-4 py-3">
                  <div className="flex items-center gap-3">
                    <Initials user={user} size="h-10 w-10 text-[15px]" />
                    <div className="min-w-0">
                      <p className="truncate text-[15px] font-bold leading-tight text-white">{user.full_name}</p>
                      <p className="truncate text-[13px] text-tv-muted">{user.email ?? ''}</p>
                    </div>
                  </div>
                  <p className="mt-3 flex flex-wrap items-center gap-2 text-[14px] text-tv-muted">
                    <span className={`font-cond px-2 py-1 text-[13px] font-extrabold uppercase leading-none tracking-wide ${TIER_COLORS[tier]}`}>
                      {TIER_LABELS[tier]}
                    </span>
                    {aiInfo.label}
                  </p>
                </div>

                <ul className="border-t border-tv-seam py-1">
                  {MENU.map(({ id, label, Icon }) => (
                    <li key={id}>
                      <button
                        onClick={() => handleNavigate(id)}
                        className="flex min-h-[44px] w-full items-center gap-3 px-4 text-left text-[15px] font-semibold text-tv-paper transition-colors hover:bg-tv-panel2 hover:text-white"
                      >
                        <Icon size={17} aria-hidden className="text-tv-muted" />
                        {label}
                      </button>
                    </li>
                  ))}
                </ul>

                <div className="border-t border-tv-seam py-1">
                  <button
                    onClick={() => handleNavigate('logout')}
                    className="flex min-h-[44px] w-full items-center gap-3 px-4 text-left text-[15px] font-semibold text-tv-muted transition-colors hover:bg-tv-panel2 hover:text-white"
                  >
                    <LogOut size={17} aria-hidden />
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
              className="flex min-h-[44px] items-center px-1.5 text-[15px] font-semibold text-tv-paper transition-colors hover:text-white min-[380px]:px-2 sm:px-3"
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
              className="flex h-11 w-10 items-center justify-center text-tv-paper transition-colors hover:text-white min-[380px]:w-11 sm:w-auto sm:px-3 sm:text-[15px] sm:font-semibold"
            >
              <LogIn size={18} aria-hidden className="sm:hidden" />
              <span className="hidden sm:inline">Zaloguj</span>
            </button>
            <button
              onClick={() => onNavigate('register')}
              className="font-cond flex min-h-[44px] items-center bg-tv-blue px-2 text-[15px] font-extrabold uppercase tracking-normal text-white transition-colors hover:bg-[#3a63ff] min-[380px]:px-3 min-[380px]:text-[16px] min-[380px]:tracking-wide sm:px-4 sm:text-[17px]"
            >
              Zarejestruj
            </button>
          </div>
        )}
      </div>
      </div>

      {/* Drugi wiersz — sekcje serwisu, tylko na szerokim ekranie. Na telefonie
          tę rolę pełni dolna belka; dwie nawigacje naraz (stan sprzed 10.2026)
          to krytyka „podwójna nawigacja na komputerze” */}
      {navItems.length > 0 && (
        <nav aria-label="Sekcje serwisu" className="hidden border-t border-tv-seam lg:block">
          <ul className="mx-auto flex max-w-7xl items-stretch px-4 md:px-8">
            {navItems.map((item) => {
              const active = item.id === activeSection;
              return (
                <li key={item.id}>
                  <a
                    href={item.href}
                    aria-current={active ? 'page' : undefined}
                    onClick={(e) => {
                      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
                      e.preventDefault();
                      onNavigate(item.id);
                    }}
                    className={`font-cond flex min-h-[44px] items-center px-3 text-[16px] font-bold uppercase tracking-wide transition-colors ${
                      active ? 'bg-tv-paper text-tv-ink' : 'text-tv-paper hover:bg-tv-panel hover:text-white'
                    }`}
                  >
                    {item.label}
                  </a>
                </li>
              );
            })}
          </ul>
        </nav>
      )}
    </header>
  );
};

export default TopBar;
