import React from 'react';
import { Home, Bot, Building2, Store, ClipboardList } from 'lucide-react';
import { TabId } from '../../types';
import { cn } from '../../lib/utils';

interface BottomTabBarProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  isAuthenticated: boolean;
}

const TABS: { id: TabId; label: string; icon: React.ElementType }[] = [
  { id: 'home', label: 'Start', icon: Home },
  { id: 'assistant', label: 'Asystent', icon: Bot },
  // „Gmina”, nie „Info”: pod tą zakładką są wiadomości, wydarzenia, odpady,
  // autobus i pogoda — słowo „Info” nie mówiło, czego tam szukać (krytyka 11.10)
  { id: 'miasto', label: 'Gmina', icon: Building2 },
  { id: 'dane', label: 'Firmy', icon: Store },
  { id: 'zgloszenia', label: 'Zgłoszenia 24', icon: ClipboardList },
];

const BottomTabBar: React.FC<BottomTabBarProps> = React.memo(({ activeTab, onTabChange, isAuthenticated }) => {
  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-tv-seam bg-tv-ink lg:hidden"
      style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
    >
      <div className="max-w-lg lg:max-w-2xl mx-auto flex items-center justify-around px-2 py-1">
        {TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          const Icon = tab.icon;

          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={cn(
                'relative flex min-h-[56px] min-w-[60px] flex-col items-center justify-center gap-1 px-1.5 transition-colors sm:px-3',
                isActive
                  ? 'text-white'
                  : 'text-tv-muted hover:text-white'
              )}
              aria-current={isActive ? 'page' : undefined}
            >
              <div className="relative">
                <Icon size={22} strokeWidth={isActive ? 2.5 : 2} aria-hidden />
              </div>
              <span className={cn(
                'whitespace-nowrap text-[13px] leading-none',
                isActive ? 'font-bold text-white' : 'font-medium'
              )}>
                {tab.label}
              </span>
              {/* Plakietka aktywnej zakładki: pas chabru na górnej krawędzi */}
              {isActive && <span aria-hidden className="absolute inset-x-2 top-0 h-[3px] bg-tv-blue" />}
            </button>
          );
        })}
      </div>
    </nav>
  );
});

BottomTabBar.displayName = 'BottomTabBar';

export default BottomTabBar;
