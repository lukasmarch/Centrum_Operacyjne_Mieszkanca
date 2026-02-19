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
    if (!trend || trend === 0) return 'bg-slate-800';
    return trend > 0 ? 'bg-green-500/10' : 'bg-red-500/10';
  };

  const getTrendIcon = () => {
    if (!trend || trend === 0) return <Minus size={14} />;
    return trend > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />;
  };

  return (
    <div
      className={`bg-slate-900 rounded-xl shadow-sm border border-slate-800 p-5 hover:border-slate-700 transition-all relative overflow-hidden min-w-0 ${className}`}
    >
      {/* Level Badge (if powiat) */}
      {level === 'powiat' && (
        <div className="absolute top-0 right-0 bg-amber-500/10 text-amber-500 text-[10px] font-bold px-2 py-1 rounded-bl-lg uppercase tracking-wide border-b border-l border-amber-500/20">
          Powiat
        </div>
      )}

      {/* Header with icon and label */}
      <div className="flex items-start justify-between mb-3 mt-1">
        <div className="flex-1 pr-4">
          <p className="text-sm text-slate-400 font-medium mb-1 line-clamp-2 min-h-[40px]" title={label}>{label}</p>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-100">{formatValue(value)}</span>
            <span className="text-sm text-slate-500 font-medium">{unit}</span>
          </div>
        </div>
        {Icon && (
          <div className="bg-gradient-to-br from-slate-800 to-slate-900 p-2.5 rounded-lg flex-shrink-0 border border-slate-700">
            <Icon className="text-blue-400" size={20} />
          </div>
        )}
      </div>

      {/* Trend indicator */}
      {trend !== undefined && (
        <div className="flex items-center gap-2 mt-3">
          <span
            className={`flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded-full ${getTrendBgColor()} ${getTrendColor()}`}
          >
            {getTrendIcon()}
            {Math.abs(trend).toFixed(2)}%
          </span>
          <span className="text-xs text-slate-500">rok do roku</span>
        </div>
      )}

      {/* Sparkline (5-year mini trend) */}
      {sparklineData && sparklineData.length > 0 && (
        <div className="mt-3 h-12" style={{ minWidth: 0 }}>
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
                animationDuration={800}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};

export default KPICard;
