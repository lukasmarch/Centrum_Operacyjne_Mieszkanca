import React from 'react';

type TileVariant = 'glass' | 'gradient' | 'highlight' | 'dark';

interface BentoTileProps {
  children: React.ReactNode;
  colSpan?: 1 | 2 | 3 | 4;
  rowSpan?: 1 | 2 | 3;
  variant?: TileVariant;
  className?: string;
}

const variantClasses: Record<TileVariant, string> = {
  glass:     'glass-panel',
  gradient:  'bg-gradient-to-br from-blue-900/30 via-black to-purple-900/30 border border-white/10',
  highlight: 'bg-gradient-to-br from-blue-600/20 via-indigo-600/10 to-purple-600/20 border border-blue-500/20',
  dark:      'bg-gray-950 border border-gray-800/50',
};

// On mobile always col-span-1; tablet (sm) max 2; desktop (lg) full colSpan
const colSpanClasses: Record<number, string> = {
  1: 'col-span-1',
  2: 'col-span-1 sm:col-span-2',
  3: 'col-span-1 sm:col-span-2 lg:col-span-3',
  4: 'col-span-1 sm:col-span-2 lg:col-span-4',
};

const rowSpanClasses: Record<number, string> = {
  1: 'row-span-1',
  2: 'row-span-1 lg:row-span-2',
  3: 'row-span-1 lg:row-span-3',
};

const BentoTile: React.FC<BentoTileProps> = ({
  children,
  colSpan = 1,
  rowSpan = 1,
  variant = 'glass',
  className = '',
}) => (
  <div className={`rounded-3xl overflow-hidden ${variantClasses[variant]} ${colSpanClasses[colSpan]} ${rowSpanClasses[rowSpan]} ${className}`}>
    {children}
  </div>
);

export default BentoTile;
