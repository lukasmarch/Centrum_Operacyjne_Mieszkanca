/**
 * ComparisonBar Component
 *
 * Horizontal bar chart for comparing Gmina Rybno with other gminy in powiat
 * Highlights Rybno's bar with special color
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
  highlightUnitId?: string;
  maxItems?: number;
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
  const sortedData = useMemo(() => {
    return [...data]
      .sort((a, b) => b.value - a.value)
      .slice(0, maxItems)
      .map((item, index) => ({
        ...item,
        rank: index + 1,
        display_name: item.unit_name.length > 25
          ? item.unit_name.substring(0, 22) + '...'
          : item.unit_name,
      }));
  }, [data, maxItems]);

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

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const item = payload[0].payload;
      const isRybno = item.unit_id === highlightUnitId;
      return (
        <div className="bg-gray-800 border border-white/10 px-4 py-3 rounded-lg shadow-xl">
          <p className={`text-sm font-semibold mb-1 ${isRybno ? 'text-blue-400' : 'text-neutral-200'}`}>
            {item.unit_name}
          </p>
          <p className="text-lg font-bold text-neutral-100">
            {formatValue(item.value)} {unit}
          </p>
          <p className="text-xs text-neutral-500 mt-1">
            Pozycja #{item.rank} w powiecie
          </p>
        </div>
      );
    }
    return null;
  };

  const getBarColor = (unitId: string) => {
    return unitId === highlightUnitId ? '#3b82f6' : '#334155';
  };

  const rybnoItem = sortedData.find(item => item.unit_id === highlightUnitId);

  return (
    <div className="bg-white/[0.04] rounded-xl border border-white/5 p-5 min-w-0">
      {title && (
        <h3 className="text-lg font-bold text-neutral-100 mb-4">{title}</h3>
      )}

      <div style={{ width: '100%', height: `${height}px`, minWidth: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={sortedData}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 5, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />

            <XAxis
              type="number"
              stroke="#334155"
              style={{ fontSize: '12px', fontWeight: 500 }}
              tick={{ fill: '#64748b' }}
              tickFormatter={(value) => formatValue(value).split(',')[0]}
            />

            <YAxis
              type="category"
              dataKey="display_name"
              stroke="#334155"
              style={{ fontSize: '12px', fontWeight: 500 }}
              tick={{ fill: '#94a3b8' }}
              width={120}
            />

            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />

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
                  opacity={entry.unit_id === highlightUnitId ? 1 : 0.7}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="mt-4 pt-4 border-t border-white/5 flex items-center justify-center gap-4 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-blue-500 rounded-sm"></div>
          <span className="text-neutral-400 font-medium">Gmina Rybno</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#334155' }}></div>
          <span className="text-neutral-500">Pozostałe gminy</span>
        </div>
      </div>

      {/* Rybno's ranking */}
      {rybnoItem && (
        <div className="mt-3 p-3 bg-blue-900/20 rounded-lg border border-blue-500/20">
          <p className="text-sm text-neutral-300">
            <span className="font-bold text-blue-400">Gmina Rybno</span> zajmuje{' '}
            <span className="font-bold text-blue-400">#{rybnoItem.rank}</span>{' '}
            miejsce w powiecie
          </p>
        </div>
      )}
    </div>
  );
};

export default ComparisonBar;
