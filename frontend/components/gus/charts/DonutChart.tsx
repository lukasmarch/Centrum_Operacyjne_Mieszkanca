/**
 * DonutChart Component
 *
 * Pie/Donut chart for displaying categorical distributions
 * Used for:
 * - Age structure (0-14, 15-64, 65+)
 * - Employment sectors (rolnictwo, przemysł, usługi)
 * - Budget breakdown (dochody własne, subwencje, dotacje)
 *
 * Features:
 * - Recharts PieChart with custom colors
 * - Center label showing total
 * - Legend with percentages
 * - Tooltip with detailed values
 */

import React from 'react';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

interface DonutChartData {
  name: string;
  value: number;
  color?: string;
}

interface DonutChartProps {
  data: DonutChartData[];
  title?: string;
  unit?: string;
  height?: number;
  innerRadius?: number; // 0 = pie chart, >0 = donut chart
  formatType?: 'integer' | 'decimal' | 'percentage' | 'currency';
}

// Default color palette
const DEFAULT_COLORS = [
  '#3b82f6', // blue-500
  '#10b981', // green-500
  '#f59e0b', // amber-500
  '#ef4444', // red-500
  '#8b5cf6', // violet-500
  '#ec4899', // pink-500
  '#06b6d4', // cyan-500
  '#f97316', // orange-500
];

const DonutChart: React.FC<DonutChartProps> = ({
  data,
  title,
  unit = '',
  height = 350,
  innerRadius = 60,
  formatType = 'integer',
}) => {
  // Calculate total
  const total = data.reduce((sum, item) => sum + item.value, 0);

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
      const item = payload[0];
      const percentage = ((item.value / total) * 100).toFixed(1);
      return (
        <div className="bg-white px-4 py-3 rounded-lg shadow-lg border border-gray-200">
          <p className="text-sm font-semibold text-gray-900 mb-1">
            {item.name}
          </p>
          <p className="text-lg font-bold text-blue-600">
            {formatValue(item.value)} {unit}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            {percentage}% całości
          </p>
        </div>
      );
    }
    return null;
  };

  // Custom legend
  const renderLegend = (props: any) => {
    const { payload } = props;
    return (
      <div className="flex flex-col gap-2 mt-4">
        {payload.map((entry: any, index: number) => {
          const percentage = ((entry.payload.value / total) * 100).toFixed(1);
          return (
            <div key={`legend-${index}`} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: entry.color }}
                ></div>
                <span className="text-gray-700 font-medium">{entry.value}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-gray-900 font-semibold">
                  {formatValue(entry.payload.value)} {unit}
                </span>
                <span className="text-gray-500 min-w-[3rem] text-right">
                  {percentage}%
                </span>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  // Prepare data with colors
  const chartData = data.map((item, index) => ({
    ...item,
    color: item.color || DEFAULT_COLORS[index % DEFAULT_COLORS.length],
  }));

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
      {title && (
        <h3 className="text-lg font-bold text-gray-900 mb-4">{title}</h3>
      )}

      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="45%"
            innerRadius={innerRadius}
            outerRadius={100}
            paddingAngle={2}
            dataKey="value"
            animationDuration={800}
            animationEasing="ease-out"
            label={({ name, percent }) => `${(percent * 100).toFixed(0)}%`}
            labelLine={false}
          >
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
          <Legend content={renderLegend} />
        </PieChart>
      </ResponsiveContainer>

      {/* Total summary */}
      <div className="mt-4 pt-4 border-t border-gray-100 text-center">
        <p className="text-sm text-gray-500 mb-1">Suma całkowita</p>
        <p className="text-2xl font-bold text-gray-900">
          {formatValue(total)} {unit}
        </p>
      </div>
    </div>
  );
};

export default DonutChart;
