import React from 'react';
import { cn } from '../../lib/utils';

interface SubNavItem {
  id: string;
  label: string;
}

interface SubNavBarProps {
  items: SubNavItem[];
  activeItem: string;
  onItemChange: (id: string) => void;
}

const SubNavBar: React.FC<SubNavBarProps> = ({ items, activeItem, onItemChange }) => {
  return (
    <div className="sticky top-0 z-30 border-b border-white/5 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-4 py-2">
        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
          {items.map((item) => {
            const isActive = activeItem === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onItemChange(item.id)}
                className={cn(
                  'px-4 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-all duration-200 border',
                  isActive
                    ? 'bg-white/10 text-white border-white/20 shadow-sm'
                    : 'bg-transparent text-neutral-500 border-transparent hover:text-neutral-300 hover:bg-white/5'
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
