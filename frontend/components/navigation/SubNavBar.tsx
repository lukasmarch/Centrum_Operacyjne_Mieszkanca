import React, { useEffect, useRef } from 'react';
import { cn } from '../../lib/utils';

interface SubNavItem {
  id: string;
  label: string;
}

interface SubNavBarProps {
  items: SubNavItem[];
  activeItem: string;
  onItemChange: (id: string) => void;
  className?: string;
}

const SubNavBar: React.FC<SubNavBarProps> = ({ items, activeItem, onItemChange, className }) => {
  // Na telefonie siedem pozycji nie mieści się w szerokości — aktywna (Odpady,
  // Kino…) stała za prawą krawędzią i pasek nie mówił, gdzie jesteś
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>('[aria-current="page"]');
    el?.scrollIntoView({ block: 'nearest', inline: 'center' });
  }, [activeItem]);

  return (
    <div className={cn('border-b border-tv-seam bg-tv-ink', className)}>
      <div className="max-w-7xl mx-auto px-4 py-2">
        {/* Maska na prawej krawędzi mówi, że pasek przewija się dalej */}
        <div
          ref={listRef}
          className="flex items-center gap-1 overflow-x-auto no-scrollbar [mask-image:linear-gradient(to_right,#000_85%,transparent)] lg:[mask-image:none]"
        >
          {items.map((item) => {
            const isActive = activeItem === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onItemChange(item.id)}
                aria-current={isActive ? 'page' : undefined}
                className={cn(
                  'font-cond min-h-[44px] whitespace-nowrap px-3 text-[16px] font-bold uppercase tracking-wide transition-colors',
                  isActive
                    ? 'bg-tv-paper text-tv-ink'
                    : 'text-tv-paper hover:bg-tv-panel hover:text-white'
                )}
              >
                {item.label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default SubNavBar;
