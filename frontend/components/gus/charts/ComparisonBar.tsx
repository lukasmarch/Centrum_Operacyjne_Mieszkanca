/**
 * ComparisonBar Component
 *
 * Horizontal bar chart for comparing Gmina Rybno with other gminy in powiat
 * Highlights Rybno's bar with special color
 *
 * Used in:
 * - GUSOverview: Top 3-5 gminy comparison
 * - GUSSectionPage: Full powiat comparison
 * - GUSVariableDetail: Ranking among all gminy
 *
 * Features:
 * - Horizontal BarChart (better for long gmina names)
 * - Highlighted bar for Rybno
 * - Tooltip with ranking
 * - Sorted by value (descending)
 */

import React, { useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

interface ComparisonData {
  unit_name: string;
  unit_id: string;
  value: number;
  year?: number;
}

interface ComparisonBarProps {
  data: ComparisonData[];
  title?: string;
  unit?: string;
  highlightUnitId?: string; // Default: Rybno's unit_id
  maxItems?: number; // Show top N items
  height?: number;
  formatType?: 'integer' | 'decimal' | 'percentage' | 'currency';
}

const RYBNO_UNIT_ID = '042815403062';

const ComparisonBar: React.FC<ComparisonBarProps> = ({
  data,
  title,
  unit = '',
  highlightUnitId = RYBNO_UNIT_ID,
  maxItems = 10,
  height = 400,
  formatType = 'integer',
}) => {
  // Sort data by value (descending) and limit to maxItems
  const sortedData = useMemo(() => {
    return [...data]
      .sort((a, b) => b.value - a.value)
      .slice(0, maxItems)
      .map((item, index) => ({
        ...item,
        rank: index + 1,
        // Shorten long gmina names
        display_name: item.unit_name.length > 25
          ? item.unit_name.substring(0, 22) + '...'
          : item.unit_name,
      }));
  }, [data, maxItems]);

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
      const item = payload[0].payload;
      return (
        <div className="bg-white px-4 py-3 rounded-lg shadow-lg border border-gray-200">
          <p className="text-sm font-semibold text-gray-900 mb-1">
            {item.unit_name}
          </p>
          <p className="text-lg font-bold text-blue-600">
            {formatValue(item.value)} {unit}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            Pozycja #{item.rank} w powiecie
          </p>
        </div>
      );
    }
    return null;
  };

  // Get bar color (highlight Rybno)
  const getBarColor = (unitId: string) => {
    return unitId === highlightUnitId ? '#3b82f6' : '#e5e7eb'; // blue-500 vs gray-200
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
      {title && (
        <h3 className="text-lg font-bold text-gray-900 mb-4">{title}</h3>
      )}

      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          data={sortedData}
          layout="vertical"
          margin={{ top: 5, right: 30, left: 5, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />

          <XAxis
            type="number"
            stroke="#9ca3af"
            style={{ fontSize: '12px', fontWeight: 500 }}
            tick={{ fill: '#6b7280' }}
            tickFormatter={(value) => formatValue(value).split(',')[0]}
          />

          <YAxis
            type="category"
            dataKey="display_name"
            stroke="#9ca3af"
            style={{ fontSize: '12px', fontWeight: 500 }}
            tick={{ fill: '#6b7280' }}
            width={120}
          />

          <Tooltip content={<CustomTooltip />} />

          <Bar
            dataKey="value"
            radius={[0, 4, 4, 0]}
            animationDuration={800}
            animationEasing="ease-out"
          >
            {sortedData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={getBarColor(entry.unit_id)}
                opacity={entry.unit_id === highlightUnitId ? 1 : 0.6}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="mt-4 pt-4 border-t border-gray-100 flex items-center justify-center gap-4 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-blue-500 rounded"></div>
          <span className="text-gray-700 font-medium">Gmina Rybno</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-gray-200 rounded"></div>
          <span className="text-gray-700">Pozostałe gminy</span>
        </div>
      </div>

      {/* Rybno's ranking */}
      {sortedData.find(item => item.unit_id === highlightUnitId) && (
        <div className="mt-3 p-3 bg-blue-50 rounded-lg border border-blue-100">
          <p className="text-sm text-gray-700">
            <span className="font-bold text-blue-700">Gmina Rybno</span> zajmuje{' '}
            <span className="font-bold text-blue-700">
              #{sortedData.find(item => item.unit_id === highlightUnitId)?.rank}
            </span>{' '}
            miejsce w powiecie
          </p>
        </div>
      )}
    </div>
  );
};

export default ComparisonBar;
