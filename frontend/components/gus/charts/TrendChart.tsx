/**
 * TrendChart Component
 *
 * Line/Area chart for displaying historical trends (10-30 years)
 * Used in:
 * - GUSOverview: 10-year population trend
 * - GUSSectionPage: Main variable trend visualization
 * - GUSVariableDetail: Full historical trend
 *
 * Features:
 * - Responsive Recharts AreaChart
 * - Gradient fill
 * - Tooltip with formatted values
 * - Grid lines
 * - Customizable colors
 */

import React from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

interface TrendChartProps {
  data: Array<{ year: number; value: number; label?: string }>;
  title?: string;
  unit?: string;
  color?: string;
  height?: number;
  showLegend?: boolean;
  formatType?: 'integer' | 'decimal' | 'percentage' | 'currency';
}

const TrendChart: React.FC<TrendChartProps> = ({
  data,
  title,
  unit = '',
  color = '#3b82f6', // blue-500
  height = 300,
  showLegend = false,
  formatType = 'integer',
}) => {
  // Format value based on type
  const formatValue = (val: number): string => {
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

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-gray-950 px-4 py-3 rounded-lg shadow-lg border border-gray-700/50">
          <p className="text-sm font-semibold text-neutral-200">
            Rok {payload[0].payload.year}
          </p>
          <p className="text-lg font-bold text-blue-400 mt-1">
            {formatValue(payload[0].value)} {unit}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-transparent rounded-xl min-w-0">
      {title && (
        <h3 className="text-lg font-bold text-neutral-100 mb-4">{title}</h3>
      )}

      <div style={{ width: '100%', height: `${height}px`, minWidth: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={data}
            margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
          >
            <defs>
              <linearGradient id={`areaGradient-${color}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.3} />
                <stop offset="100%" stopColor={color} stopOpacity={0.05} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />

            <XAxis
              dataKey="year"
              stroke="#94a3b8"
              style={{ fontSize: '12px', fontWeight: 500 }}
              tick={{ fill: '#94a3b8' }}
            />

            <YAxis
              stroke="#94a3b8"
              style={{ fontSize: '12px', fontWeight: 500 }}
              tick={{ fill: '#94a3b8' }}
              tickFormatter={(value) => formatValue(value).split(',')[0]} // Remove decimals for axis
            />

            <Tooltip content={<CustomTooltip />} />

            {showLegend && (
              <Legend
                wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }}
                iconType="line"
              />
            )}

            <Area
              type="monotone"
              dataKey="value"
              stroke={color}
              strokeWidth={2.5}
              fill={`url(#areaGradient-${color})`}
              animationDuration={1000}
              animationEasing="ease-in-out"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Stats summary below chart */}
      {data.length > 1 && (
        <div className="mt-4 pt-4 border-t border-gray-800/50 flex items-center justify-between text-sm">
          <div>
            <span className="text-neutral-500">Najwcześniejszy: </span>
            <span className="font-semibold text-neutral-200">
              {formatValue(data[0].value)} {unit} ({data[0].year})
            </span>
          </div>
          <div>
            <span className="text-neutral-500">Najnowszy: </span>
            <span className="font-semibold text-neutral-200">
              {formatValue(data[data.length - 1].value)} {unit} ({data[data.length - 1].year})
            </span>
          </div>
          <div>
            <span className="text-neutral-500">Zmiana: </span>
            <span
              className={`font-semibold ${data[data.length - 1].value >= data[0].value
                ? 'text-green-600'
                : 'text-red-600'
                }`}
            >
              {((((data[data.length - 1].value - data[0].value) / data[0].value) * 100).toFixed(1))}%
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default TrendChart;
