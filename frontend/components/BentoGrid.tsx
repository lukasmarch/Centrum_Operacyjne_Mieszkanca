import React from 'react';

interface BentoGridProps {
  children: React.ReactNode;
  className?: string;
}

const BentoGrid: React.FC<BentoGridProps> = ({ children, className = '' }) => (
  <div className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 auto-rows-[minmax(180px,auto)] ${className}`}>
    {children}
  </div>
);

export default BentoGrid;
