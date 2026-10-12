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
import { GUS_CHART, TOOLTIP_CLASS } from './palette';

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
        return `${val.toLocaleString('pl-PL', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
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
        <div className={TOOLTIP_CLASS}>
          <p className={`mb-0.5 text-[13px] font-bold ${isRybno ? 'text-tv-bluesoft' : 'text-tv-paper'}`}>
            {item.unit_name}
          </p>
          <p className="font-cond tabular text-[20px] font-extrabold text-white">
            {formatValue(item.value)} {unit}
          </p>
          <p className="tabular mt-0.5 text-[13px] text-tv-muted">
            Pozycja #{item.rank} w powiecie
          </p>
        </div>
      );
    }
    return null;
  };

  const getBarColor = (unitId: string) => {
    return unitId === highlightUnitId ? GUS_CHART.series : GUS_CHART.compare;
  };

  const rybnoItem = sortedData.find(item => item.unit_id === highlightUnitId);

  return (
    <div className="h-full min-w-0 bg-tv-panel p-4 lg:p-5">
      {title && (
        <h3 className="font-cond mb-3 text-[20px] font-extrabold leading-snug text-white">{title}</h3>
      )}

      <div style={{ width: '100%', height: `${height}px`, minWidth: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={sortedData}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 5, bottom: 5 }}
          >
            <CartesianGrid stroke={GUS_CHART.seam} horizontal={false} />

            <XAxis
              type="number"
              stroke={GUS_CHART.seam}
              style={{ fontSize: '13px', fontVariantNumeric: 'tabular-nums' }}
              tick={{ fill: GUS_CHART.muted }}
              tickLine={false}
              tickFormatter={(value) => formatValue(value).split(',')[0]}
            />

            <YAxis
              type="category"
              dataKey="display_name"
              stroke={GUS_CHART.seam}
              style={{ fontSize: '13px' }}
              tick={{ fill: GUS_CHART.paper }}
              tickLine={false}
              width={120}
            />

            <Tooltip content={<CustomTooltip />} cursor={{ fill: GUS_CHART.panel2 }} />

            <Bar
              dataKey="value"
              animationDuration={800}
              animationEasing="ease-out"
            >
              {sortedData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={getBarColor(entry.unit_id)}
                  fillOpacity={entry.unit_id === highlightUnitId ? 1 : 0.45}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-tv-seam pt-3 text-[13px]">
        <div className="flex items-center gap-2">
          <span className="inline-block h-3 w-3 bg-tv-blue" aria-hidden></span>
          <span className="font-bold text-tv-paper">Gmina Rybno</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-block h-3 w-3" style={{ backgroundColor: GUS_CHART.compare, opacity: 0.45 }} aria-hidden></span>
          <span className="text-tv-muted">Pozostałe gminy</span>
        </div>
      </div>

      {/* Rybno's ranking */}
      {rybnoItem && (
        <p className="mt-3 bg-tv-panel2 px-3 py-2.5 text-[15px] text-[#d7dbe8]">
          <span className="font-bold text-white">Gmina Rybno</span> zajmuje{' '}
          <span className="tabular font-bold text-white">#{rybnoItem.rank}</span>{' '}
          miejsce w powiecie
        </p>
      )}
    </div>
  );
};

export default ComparisonBar;
