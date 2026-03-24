import React from 'react';
import { Home, Bot, Building2, BarChart3, ClipboardList } from 'lucide-react';
import { motion } from 'framer-motion';
import { TabId } from '../../types';
import { cn } from '../../lib/utils';

interface BottomTabBarProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  isAuthenticated: boolean;
}

const TABS: { id: TabId; label: string; icon: React.ElementType }[] = [
  { id: 'home', label: 'Home', icon: Home },
  { id: 'assistant', label: 'Asystent', icon: Bot },
  { id: 'miasto', label: 'Miasto', icon: Building2 },
  { id: 'dane', label: 'Dane', icon: BarChart3 },
  { id: 'zgloszenia', label: 'Zgłoszenia', icon: ClipboardList },
];

const BottomTabBar: React.FC<BottomTabBarProps> = React.memo(({ activeTab, onTabChange, isAuthenticated }) => {
  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 bg-black/90 backdrop-blur-xl border-t border-gray-800/50"
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
                'relative flex flex-col items-center gap-0.5 px-3 py-2 rounded-2xl transition-all duration-200 min-w-[56px]',
                isActive
                  ? 'text-white'
                  : 'text-neutral-500 hover:text-neutral-300 active:scale-95'
              )}
              aria-label={tab.label}
            >
              <div className="relative">
                <Icon
                  size={22}
                  className={cn(
                    'transition-all duration-200',
                    isActive && 'drop-shadow-[0_0_8px_rgba(255,255,255,0.3)]'
                  )}
                  strokeWidth={isActive ? 2.5 : 1.8}
                />
              </div>
              <span className={cn(
                'text-[10px] font-medium transition-all duration-200',
                isActive ? 'text-white' : 'text-neutral-500'
              )}>
                {tab.label}
              </span>
              {isActive && (
                <motion.div
                  layoutId="tab-indicator"
                  className="absolute -bottom-1 w-5 h-0.5 rounded-full"
                  style={{ background: 'linear-gradient(to right, var(--chart-2), var(--chart-3))' }}
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
});

BottomTabBar.displayName = 'BottomTabBar';

export default BottomTabBar;
