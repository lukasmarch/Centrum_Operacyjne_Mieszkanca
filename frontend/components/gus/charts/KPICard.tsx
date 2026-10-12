/**
 * KPICard Component
 *
 * Displays a single KPI metric with:
 * - Current value with unit
 * - Year-over-year trend (arrow + percentage)
 * - Optional icon
 *
 * Used in GUSOverview and GUSSectionPage
 */

import React from 'react';
import { TrendingUp, TrendingDown, Minus, LucideIcon } from 'lucide-react';
import { Tag } from '../../simple/tv';

interface KPICardProps {
  label: string;
  value: number | string;
  unit: string;
  trend?: number; // Year-over-year change percentage
  sparklineData?: Array<{ year: number; value: number }>; // Optional 5-year trend
  icon?: LucideIcon;
  formatType?: 'integer' | 'decimal' | 'float' | 'percentage' | 'currency';
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
        return `${val.toLocaleString('pl-PL', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
      case 'currency':
        // Zaokrąglij kwoty do pełnych złotych (bez groszy). Jednostkę podaje
        // `unit` obok wartości — doklejona tutaj dawała „9370 PLN PLN”
        return Math.round(val).toLocaleString('pl-PL');
      default:
        return Math.round(val).toLocaleString('pl-PL');
    }
  };

  // Kierunek zmiany bez oceny kolorem: wzrost liczby wykreślonych firm i wzrost
  // dochodów to ta sama strzałka w górę — zieleń/czerwień sugerowałyby werdykt,
  // a czerwień w tym systemie znaczy wyłącznie awarię.
  const getTrendIcon = () => {
    if (!trend || trend === 0) return <Minus size={14} />;
    return trend > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />;
  };

  return (
    <div
      className={`relative h-full min-w-0 bg-tv-panel px-3.5 pb-3 pt-3 transition-colors hover:bg-tv-panel2 ${className}`}
    >
      {/* Wskaźnik bez danych gminnych — żółć = kontekst: liczba dotyczy powiatu */}
      {level === 'powiat' && (
        <Tag tone="yellow" className="absolute right-0 top-0">Powiat</Tag>
      )}

      {/* Label */}
      <p className={`mb-1.5 line-clamp-2 text-[13px] leading-snug text-tv-muted ${level === 'powiat' ? 'pr-16' : ''}`} title={label}>{label}</p>

      {/* Value */}
      <div className="flex flex-wrap items-baseline gap-x-1.5">
        <span className="font-cond tabular text-[26px] font-extrabold leading-[1.05] text-white">{formatValue(value)}</span>
        <span className="text-[13px] text-tv-muted">{unit}</span>
      </div>

      {/* Trend indicator */}
      {trend !== undefined && (
        <div className="mt-1.5 flex items-center gap-1.5 text-[13px]">
          <span className="tabular inline-flex items-center gap-0.5 font-bold text-tv-paper">
            {getTrendIcon()}
            {Math.abs(trend).toLocaleString('pl-PL', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%
          </span>
          <span className="text-tv-muted">r/r</span>
        </div>
      )}

      {/* Sparkline usunięty (przegląd 11.10.2026): mała linia pod każdą liczbą to szablon
          „hero-metric”, a pełne wykresy trendu stoją tuż pod kaflami. `sparklineData`
          zostaje w interfejsie, żeby nie ruszać wołających */}
    </div>
  );
};

export default KPICard;
