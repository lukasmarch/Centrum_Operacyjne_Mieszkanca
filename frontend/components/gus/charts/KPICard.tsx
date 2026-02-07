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
  className = '',
}) => {
  // Format value based on type
  const formatValue = (val: number | string): string => {
    if (typeof val === 'string') return val;

    switch (formatType) {
      case 'integer':
        return val.toLocaleString('pl-PL');
      case 'decimal':
        return val.toLocaleString('pl-PL', { minimumFractionDigits: 1, maximumFractionDigits: 2 });
      case 'percentage':
        return `${val.toFixed(1)}%`;
      case 'currency':
        return `${val.toLocaleString('pl-PL')} PLN`;
      default:
        return val.toLocaleString('pl-PL');
    }
  };

  // Determine trend styling
  const getTrendColor = () => {
    if (!trend || trend === 0) return 'text-gray-500';
    return trend > 0 ? 'text-green-600' : 'text-red-600';
  };

  const getTrendBgColor = () => {
    if (!trend || trend === 0) return 'bg-gray-50';
    return trend > 0 ? 'bg-green-50' : 'bg-red-50';
  };

  const getTrendIcon = () => {
    if (!trend || trend === 0) return <Minus size={14} />;
    return trend > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />;
  };

  return (
    <div
      className={`bg-white rounded-xl shadow-sm border border-gray-100 p-5 hover:shadow-md transition-shadow ${className}`}
    >
      {/* Header with icon and label */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <p className="text-sm text-gray-500 font-medium mb-1">{label}</p>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-gray-900">{formatValue(value)}</span>
            <span className="text-sm text-gray-500 font-medium">{unit}</span>
          </div>
        </div>
        {Icon && (
          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 p-2.5 rounded-lg">
            <Icon className="text-blue-600" size={20} />
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
          <span className="text-xs text-gray-500">rok do roku</span>
        </div>
      )}

      {/* Sparkline (5-year mini trend) */}
      {sparklineData && sparklineData.length > 0 && (
        <div className="mt-3 h-12">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={sparklineData}>
              <defs>
                <linearGradient id="sparklineGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="value"
                stroke="#3b82f6"
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
