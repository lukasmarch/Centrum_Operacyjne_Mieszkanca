/**
 * KPICard Component
 *
 * Displays a single KPI metric with:
 * - Current value with unit
 * - Year-over-year trend (arrow + percentage)
 * - Optional sparkline showing 5-year trend
 * - Optional icon
 *
 * Used in GUSOverview and GUSSectionPage
 */

import React from 'react';
import { TrendingUp, TrendingDown, Minus, LucideIcon } from 'lucide-react';
import { AreaChart, Area, ResponsiveContainer } from 'recharts';

interface KPICardProps {
  label: string;
  value: number | string;
  unit: string;
  trend?: number; // Year-over-year change percentage
  sparklineData?: Array<{ year: number; value: number }>; // Optional 5-year trend
  icon?: LucideIcon;
  formatType?: 'integer' | 'decimal' | 'percentage' | 'currency';
  level?: 'gmina' | 'powiat';
  className?: string;
}

const KPICard: React.FC<KPICardProps> = ({
  label,
  value,
  unit,
  trend,
  sparklineData,
  icon: Icon,
  formatType = 'integer',
  level = 'gmina',
  className = '',
}) => {
  // Format value based on type
  const formatValue = (val: number | string): string => {
    if (typeof val === 'string') return val;

    switch (formatType) {
      case 'integer':
        // Zaokrąglij do pełnych liczb
        return Math.round(val).toLocaleString('pl-PL');
      case 'decimal':
      case 'float':
        // Zaokrąglij do 1 miejsca po przecinku
        return val.toLocaleString('pl-PL', { minimumFractionDigits: 0, maximumFractionDigits: 1 });
      case 'percentage':
        // Zaokrąglij procenty do 1 miejsca
        return `${val.toFixed(1)}%`;
      case 'currency':
        // Zaokrąglij kwoty do pełnych złotych (bez groszy)
        return `${Math.round(val).toLocaleString('pl-PL')} PLN`;
      default:
        return Math.round(val).toLocaleString('pl-PL');
    }
  };

  // Determine trend styling
  const getTrendColor = () => {
    if (!trend || trend === 0) return 'text-gray-500';
    return trend > 0 ? 'text-green-600' : 'text-red-600';
  };

  const getTrendBgColor = () => {
    if (!trend || trend === 0) return 'bg-gray-900';
    return trend > 0 ? 'bg-green-500/10' : 'bg-red-500/10';
  };

  const getTrendIcon = () => {
    if (!trend || trend === 0) return <Minus size={14} />;
    return trend > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />;
  };

  return (
    <div
      className={`bg-white/[0.04] rounded-lg border border-white/5 p-3 hover:border-blue-500/30 hover:bg-gray-900/80 transition-all relative overflow-hidden min-w-0 ${className}`}
    >
      {/* Level Badge (if powiat) */}
      {level === 'powiat' && (
        <div className="absolute top-0 right-0 bg-amber-500/10 text-amber-500 text-[9px] font-bold px-1.5 py-0.5 rounded-bl-lg uppercase tracking-wide border-b border-l border-amber-500/20">
          Powiat
        </div>
      )}

      {/* Label */}
      <p className="text-xs text-neutral-500 font-medium mb-1.5 line-clamp-2 leading-tight" title={label}>{label}</p>

      {/* Value */}
      <div className="flex items-baseline gap-1.5">
        <span className="text-xl font-bold text-neutral-100 leading-none">{formatValue(value)}</span>
        <span className="text-xs text-neutral-500">{unit}</span>
      </div>

      {/* Trend indicator */}
      {trend !== undefined && (
        <div className="flex items-center gap-1.5 mt-2">
          <span
            className={`flex items-center gap-0.5 text-[11px] font-semibold px-1.5 py-0.5 rounded-full ${getTrendBgColor()} ${getTrendColor()}`}
          >
            {getTrendIcon()}
            {Math.abs(trend).toFixed(1)}%
          </span>
          <span className="text-[11px] text-neutral-600">r/r</span>
        </div>
      )}

      {/* Sparkline */}
      {sparklineData && sparklineData.length > 0 && (
        <div className="mt-2 h-8" style={{ minWidth: 0 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={sparklineData}>
              <defs>
                <linearGradient id="sparklineGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#60a5fa" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#60a5fa" stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="value"
                stroke="#60a5fa"
                strokeWidth={1.5}
                fill="url(#sparklineGradient)"
                animationDuration={600}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};

export default KPICard;
