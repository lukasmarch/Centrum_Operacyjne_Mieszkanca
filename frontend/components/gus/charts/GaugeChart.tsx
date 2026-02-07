/**
 * GaugeChart Component
 *
 * Semicircle gauge chart for displaying percentage comparisons
 * Primary use: "X% średniej krajowej/wojewódzkiej"
 *
 * Used in:
 * - GUSSectionPage: National comparison for each section
 * - GUSVariableDetail: Detailed comparison view
 *
 * Features:
 * - Semicircle progress indicator (0-200%)
 * - Color coding (red < 80%, yellow 80-120%, green > 120%)
 * - Center label with percentage
 * - Comparison values displayed below
 */

import React from 'react';

interface GaugeChartProps {
  value: number; // Gmina value
  nationalValue: number; // National/voivodeship average
  title?: string;
  unit?: string;
  maxPercentage?: number; // Max gauge range (default 200%)
  formatType?: 'integer' | 'decimal' | 'percentage' | 'currency';
  comparisonLevel?: 'krajowa' | 'wojewódzka' | 'powiatowa';
}

const GaugeChart: React.FC<GaugeChartProps> = ({
  value,
  nationalValue,
  title,
  unit = '',
  maxPercentage = 200,
  formatType = 'integer',
  comparisonLevel = 'krajowa',
}) => {
  // Calculate percentage
  const percentage = nationalValue > 0 ? (value / nationalValue) * 100 : 0;
  const displayPercentage = Math.min(percentage, maxPercentage); // Cap at maxPercentage

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

  // Determine color based on percentage
  const getColor = () => {
    if (percentage < 80) return { bg: '#ef4444', text: 'text-red-600', label: 'Poniżej średniej' };
    if (percentage < 120) return { bg: '#f59e0b', text: 'text-amber-600', label: 'Zbliżone do średniej' };
    return { bg: '#10b981', text: 'text-green-600', label: 'Powyżej średniej' };
  };

  const color = getColor();

  // Calculate arc path (semicircle)
  const radius = 80;
  const strokeWidth = 12;
  const circumference = Math.PI * radius;
  const offset = circumference - (displayPercentage / maxPercentage) * circumference;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
      {title && (
        <h3 className="text-lg font-bold text-gray-900 mb-4">{title}</h3>
      )}

      {/* Gauge SVG */}
      <div className="flex flex-col items-center justify-center py-6">
        <svg width="200" height="120" viewBox="0 0 200 120" className="mb-4">
          {/* Background arc (gray) */}
          <path
            d={`M ${100 - radius} 100 A ${radius} ${radius} 0 0 1 ${100 + radius} 100`}
            fill="none"
            stroke="#e5e7eb"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />

          {/* Progress arc (colored) */}
          <path
            d={`M ${100 - radius} 100 A ${radius} ${radius} 0 0 1 ${100 + radius} 100`}
            fill="none"
            stroke={color.bg}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{
              transition: 'stroke-dashoffset 1s ease-out',
            }}
          />

          {/* Center percentage label */}
          <text
            x="100"
            y="85"
            textAnchor="middle"
            className="font-bold"
            style={{ fontSize: '32px', fill: color.bg }}
          >
            {percentage.toFixed(1)}%
          </text>
          <text
            x="100"
            y="105"
            textAnchor="middle"
            className="text-gray-500"
            style={{ fontSize: '12px', fill: '#6b7280' }}
          >
            średniej {comparisonLevel === 'krajowa' ? 'krajowej' : comparisonLevel === 'wojewódzka' ? 'woj.' : 'pow.'}
          </text>
        </svg>

        {/* Status label */}
        <div
          className={`px-4 py-2 rounded-full text-sm font-semibold ${color.text} bg-opacity-10`}
          style={{ backgroundColor: `${color.bg}20` }}
        >
          {color.label}
        </div>
      </div>

      {/* Values comparison */}
      <div className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-2 gap-4">
        <div className="text-center">
          <p className="text-xs text-gray-500 mb-1">Gmina Rybno</p>
          <p className="text-lg font-bold text-gray-900">
            {formatValue(value)} {unit}
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500 mb-1">
            Średnia {comparisonLevel === 'krajowa' ? 'krajowa' : comparisonLevel === 'wojewódzka' ? 'wojewódzka' : 'powiatowa'}
          </p>
          <p className="text-lg font-bold text-gray-900">
            {formatValue(nationalValue)} {unit}
          </p>
        </div>
      </div>

      {/* Additional context */}
      <div className="mt-4 p-3 bg-gray-50 rounded-lg text-sm text-gray-600 text-center">
        {percentage < 80 && (
          <p>Wartość dla Rybna jest <strong>poniżej</strong> średniej {comparisonLevel === 'krajowa' ? 'krajowej' : comparisonLevel === 'wojewódzka' ? 'wojewódzkiej' : 'powiatowej'}</p>
        )}
        {percentage >= 80 && percentage < 120 && (
          <p>Wartość dla Rybna jest <strong>zbliżona</strong> do średniej {comparisonLevel === 'krajowa' ? 'krajowej' : comparisonLevel === 'wojewódzka' ? 'wojewódzkiej' : 'powiatowej'}</p>
        )}
        {percentage >= 120 && (
          <p>Wartość dla Rybna jest <strong>powyżej</strong> średniej {comparisonLevel === 'krajowa' ? 'krajowej' : comparisonLevel === 'wojewódzka' ? 'wojewódzkiej' : 'powiatowej'}</p>
        )}
      </div>
    </div>
  );
};

export default GaugeChart;
