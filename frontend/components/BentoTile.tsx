import React from 'react';

type TileVariant = 'glass' | 'gradient' | 'highlight' | 'dark';

interface BentoTileProps {
  children: React.ReactNode;
  colSpan?: 1 | 2 | 3 | 4;
  rowSpan?: 1 | 2 | 3;
  variant?: TileVariant;
  className?: string;
}

/*
 * taste-skill: Liquid Glass refraction — 1px inner border + subtle inner shadow
 * bentogrid.txt: dark dark cards, border-white/10, hover subtleties
 * NO pure black (#000) — use off-black: #0d1117 / #0b0f18
 */
const variantStyles: Record<TileVariant, React.CSSProperties> = {
  glass: {
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,255,255,0.08)',
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.07), 0 8px 32px rgba(0,0,0,0.4)',
    backdropFilter: 'blur(12px)',
    WebkitBackdropFilter: 'blur(12px)',
  },
  gradient: {
    background: 'linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%)',
    border: '1px solid rgba(255,255,255,0.08)',
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.06), 0 4px 24px rgba(0,0,0,0.3)',
  },
  highlight: {
    background: 'linear-gradient(145deg, rgba(58,129,246,0.07) 0%, rgba(255,255,255,0.02) 100%)',
    border: '1px solid rgba(58,129,246,0.2)',
    boxShadow: 'inset 0 1px 0 rgba(58,129,246,0.1), 0 4px 24px rgba(58,129,246,0.08)',
  },
  dark: {
    background: '#0d1117',
    border: '1px solid rgba(255,255,255,0.07)',
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.05), 0 2px 16px rgba(0,0,0,0.5)',
  },
};

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
  variant = 'glass', // No longer strictly needed as glow handles theme, but kept for API compat
  className = '',
}) => (
  <div
    className={[
      'glow-tile-container group',
      colSpanClasses[colSpan],
      rowSpanClasses[rowSpan],
      className,
    ].join(' ')}
  >
    <div className="glow-tile-layer"></div>
    <div className="glow-tile-content">
      {/* Background layer inside to give that dark off-black taste-skill vibe */}
      <div className="absolute inset-0 bg-[#0d1117] pointer-events-none rounded-[inherit]" />
      
      {/* Inner subtle glow from old BentoTile */}
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none z-0 rounded-[inherit]"
        style={{ background: 'radial-gradient(600px circle at 50% 0%, rgba(58,129,246,0.06), transparent 50%)' }}
      />
      
      {/* Dot pattern */}
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none z-0">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.015)_1px,transparent_1px)] bg-[length:6px_6px]" />
      </div>

      <div className="relative z-10 h-full">
        {children}
      </div>
    </div>
  </div>
);

export default BentoTile;
