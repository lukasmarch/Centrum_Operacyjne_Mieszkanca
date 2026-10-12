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
import { GUS_CHART, TOOLTIP_CLASS } from './palette';

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
  color = GUS_CHART.series,
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
        return val.toLocaleString('pl-PL', { maximumFractionDigits: 0 }); // jednostkę dokłada `unit` obok
      default:
        return val.toLocaleString('pl-PL');
    }
  };

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className={TOOLTIP_CLASS}>
          <p className="tabular text-[13px] font-bold text-tv-muted">
            Rok {payload[0].payload.year}
          </p>
          <p className="font-cond tabular mt-0.5 text-[20px] font-extrabold text-white">
            {formatValue(payload[0].value)} {unit}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="min-w-0">
      {title && (
        <h3 className="font-cond mb-3 text-[20px] font-extrabold leading-snug text-white">{title}</h3>
      )}

      <div style={{ width: '100%', height: `${height}px`, minWidth: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={data}
            margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
          >
            <CartesianGrid vertical={false} stroke={GUS_CHART.seam} />

            <XAxis
              dataKey="year"
              stroke={GUS_CHART.seam}
              style={{ fontSize: '13px', fontVariantNumeric: 'tabular-nums' }}
              tick={{ fill: GUS_CHART.muted }}
              tickLine={false}
            />

            <YAxis
              stroke={GUS_CHART.seam}
              style={{ fontSize: '13px', fontVariantNumeric: 'tabular-nums' }}
              tick={{ fill: GUS_CHART.muted }}
              tickLine={false}
              tickFormatter={(value) => formatValue(value).split(',')[0]} // Remove decimals for axis
            />

            <Tooltip content={<CustomTooltip />} cursor={{ stroke: GUS_CHART.muted, strokeWidth: 1 }} />

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
              fill="none"
              activeDot={{ r: 4, fill: color, stroke: GUS_CHART.ink, strokeWidth: 2 }}
              animationDuration={1000}
              animationEasing="ease-in-out"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Stats summary below chart */}
      {data.length > 1 && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-t border-tv-seam pt-3 text-[13px]">
          <div>
            <span className="text-tv-muted">Najwcześniejszy: </span>
            <span className="tabular font-bold text-tv-paper">
              {formatValue(data[0].value)} {unit} ({data[0].year})
            </span>
          </div>
          <div>
            <span className="text-tv-muted">Najnowszy: </span>
            <span className="tabular font-bold text-tv-paper">
              {formatValue(data[data.length - 1].value)} {unit} ({data[data.length - 1].year})
            </span>
          </div>
          <div>
            <span className="text-tv-muted">Zmiana: </span>
            {/* Kierunek bez koloru — zieleń/czerwień nie są tu stanem */}
            <span className="tabular font-bold text-white">
              {((((data[data.length - 1].value - data[0].value) / data[0].value) * 100).toFixed(1))}%
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default TrendChart;
