/**
 * GUSSectionPage Component
 *
 * Premium tier section view for detailed category analysis
 * Requires Premium or Business tier
 *
 * Sections: demografia, rynek_pracy, przedsiebiorczosc, finanse_gminy,
 *           mieszkalnictwo, edukacja, transport, bezpieczenstwo, zdrowie, turystyka
 *
 * Layout:
 * 1. Section header with navigation
 * 2. KPI Cards Row (all variables in section)
 * 3. Main Trend Chart (primary variable historical trend)
 * 4. Comparison Charts (2x2 grid):
 *    - Gminy comparison (bar chart)
 *    - National average gauge (vs Poland)
 *    - Detailed metrics (donut/bar)
 *    - Additional trend
 * 5. Data table (all variables with YoY change)
 * 6. Business Upsell (AI insights)
 * 7. Data freshness footer
 */

import React, { useState, useRef } from 'react';
import { RefreshCw, ChevronLeft, Info } from 'lucide-react';
import { Notice, Skeleton, Tag } from '../simple/tv';
import { GUS_CHART, TOOLTIP_CLASS } from './charts/palette';
import { useGUSSection } from '../../src/hooks/useGUSStats';
import { useAuth } from '../../src/context/AuthContext';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import KPICard from './charts/KPICard';
import TrendChart from './charts/TrendChart';
import ComparisonBar from './charts/ComparisonBar';
import GaugeChart from './charts/GaugeChart';
import GUSTierGate from './layout/GUSTierGate';

interface GUSSectionPageProps {
  sectionKey: string;
  onBack?: () => void;
}

const GUSSectionPage: React.FC<GUSSectionPageProps> = ({ sectionKey, onBack }) => {
  const { data, loading, error, refetch } = useGUSSection(sectionKey);
  const { user } = useAuth();
  const [selectedVariable, setSelectedVariable] = useState<string | null>(null);
  const chartRef = useRef<HTMLDivElement>(null);

  // Loading state
  if (loading) {
    return (
      <div aria-label="Ładowanie sekcji..." className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-2 gap-px bg-tv-seam md:grid-cols-4">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-28" />)}
        </div>
        <Skeleton className="h-80" />
      </div>
    );
  }

  // Error state (403 = tier insufficient)
  if (error) {
    if (error.includes('Premium tier required') || error.includes('403')) {
      return (
        <div className="max-w-4xl">
          <GUSTierGate
            requiredTier="premium"
            currentTier={user?.tier || 'free'}
            context="section"
          />
        </div>
      );
    }

    return (
      <div className="max-w-2xl space-y-px" role="alert">
        <Notice tone="warn"><strong>Błąd ładowania sekcji.</strong> {error}</Notice>
        <div className="bg-tv-panel px-4 py-3">
          <button
            onClick={() => refetch()}
            className="font-cond inline-flex min-h-[44px] items-center bg-tv-blue px-4 text-[15px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff]"
          >
            Spróbuj ponownie
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { section_name, variables, user_tier, last_refresh } = data;

  // Get all variable keys
  const variableKeys = Object.keys(variables);
  const firstVariableKey = selectedVariable || variableKeys[0];
  const primaryVariable = variables[firstVariableKey];

  // Guard: no variables returned for this section
  if (!primaryVariable || variableKeys.length === 0) {
    return (
      <div className="max-w-2xl space-y-px">
        <Notice><strong>Brak danych dla tej sekcji.</strong> Sekcja nie zawiera jeszcze danych dla Gminy Rybno.</Notice>
        <div className="bg-tv-panel px-4 py-3">
          <button
            onClick={onBack}
            className="inline-flex min-h-[44px] items-center gap-1 text-[15px] font-bold text-tv-bluesoft underline-offset-4 hover:text-white hover:underline"
          >
            <ChevronLeft size={16} aria-hidden />
            Powrót do przeglądu
          </button>
        </div>
      </div>
    );
  }

  // Prepare data for main trend chart
  const trendData = primaryVariable?.trend?.map(item => ({
    year: item.year,
    value: item.value,
  })) || [];

  // Prepare comparison data
  const comparisonData = primaryVariable?.comparison?.map(item => ({
    unit_name: item.unit_name,
    unit_id: item.unit_id,
    value: item.value,
    year: item.year,
  })) || [];

  const trendText = (pct: number) => `${pct >= 0 ? '+' : ''}${pct.toLocaleString('pl-PL', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;

  return (
    <div className="space-y-8">
      {/* Header with back button */}
      <div>
        <button
          onClick={onBack}
          className="mb-2 inline-flex min-h-[44px] items-center gap-1 text-[15px] font-bold text-tv-bluesoft underline-offset-4 transition-colors hover:text-white hover:underline"
        >
          <ChevronLeft size={16} aria-hidden />
          Powrót do przeglądu
        </button>

        <div className="border-b border-tv-seam pb-3">
          <h2 className="font-cond text-[24px] font-extrabold leading-tight text-white lg:text-[30px]">{section_name}</h2>
          <p className="mt-0.5 text-[15px] text-tv-muted">
            Szczegółowe statystyki dla Gminy Rybno · <span className="tabular">{variableKeys.length}</span> wskaźników
          </p>
        </div>
      </div>

      {/* KPI Cards Row (all variables in section) */}
      <section className="flex flex-col">
        <h3 className="flex"><Tag>Kluczowe wskaźniki</Tag></h3>
        <div className="grid min-w-0 grid-cols-2 gap-px border-t-2 border-tv-blue bg-tv-seam md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {variableKeys.map(varKey => {
            const variable = variables[varKey];
            const isActive = selectedVariable === varKey || (!selectedVariable && varKey === firstVariableKey);
            return (
              <button
                key={varKey}
                onClick={() => {
                  setSelectedVariable(varKey);
                  setTimeout(() => {
                    chartRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                  }, 50);
                }}
                aria-pressed={isActive}
                // Wybrany wskaźnik: obrys chabrem wewnątrz pola (bez poświaty pierścienia)
                className={`min-w-0 text-left ${isActive ? 'outline outline-2 -outline-offset-2 outline-tv-blue' : ''}`}
              >
                <KPICard
                  label={variable.current.metadata.name}
                  value={variable.current.value}
                  unit={variable.current.metadata.unit}
                  trend={variable.current.trend_pct}
                  formatType={variable.current.metadata.format_type}
                  level={variable.current.metadata.level as 'gmina' | 'powiat'}
                />
              </button>
            );
          })}
        </div>
      </section>

      {/* Main Trend Chart */}
      {trendData.length > 0 && (
        <div className="scroll-mt-24 bg-tv-panel p-4 lg:p-5" ref={chartRef}>
          <TrendChart
            data={trendData}
            title={`Trend historyczny: ${primaryVariable.current.metadata.name}`}
            unit={primaryVariable.current.metadata.unit}
            height={350}
            formatType={primaryVariable.current.metadata.format_type}
            showLegend={false}
          />
        </div>
      )}

      {/* Comparison Charts Grid (2x2) */}
      <div className="grid min-w-0 grid-cols-1 gap-px bg-tv-seam lg:grid-cols-2">
        {/* Gminy comparison */}
        {comparisonData.length > 0 && (
          <div className="min-w-0">
            <ComparisonBar
              data={comparisonData}
              title="Porównanie z innymi gminami"
              unit={primaryVariable.current.metadata.unit}
              maxItems={8}
              height={320}
              formatType={primaryVariable.current.metadata.format_type}
            />
          </div>
        )}

        {/* Gmina vs Powiat Comparison (Only for Gmina-level variables) */}
        {primaryVariable.current.metadata.level === 'gmina' && primaryVariable.powiat_comparison && (
          <div className="min-w-0 bg-tv-panel p-4 lg:p-5">
            <h3 className="font-cond mb-3 text-[20px] font-extrabold leading-snug text-white">Gmina vs Powiat</h3>
            <div style={{ width: '100%', height: '280px', minWidth: 0 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={[
                    { name: 'Gmina Rybno', value: primaryVariable.powiat_comparison.gmina_value },
                    { name: 'Powiat Działdowski', value: primaryVariable.powiat_comparison.powiat_value }
                  ]}
                  margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
                >
                  <CartesianGrid vertical={false} stroke={GUS_CHART.seam} />
                  <XAxis dataKey="name" tick={{ fontSize: 13, fill: GUS_CHART.paper }} axisLine={{ stroke: GUS_CHART.seam }} tickLine={false} />
                  <YAxis tick={{ fontSize: 13, fill: GUS_CHART.muted }} axisLine={false} tickLine={false} />
                  <Tooltip
                    content={({ active, payload }: any) =>
                      active && payload?.length ? (
                        <div className={TOOLTIP_CLASS}>
                          <p className="text-[13px] font-bold text-tv-muted">{payload[0].payload.name}</p>
                          <p className="font-cond tabular mt-0.5 text-[20px] font-extrabold text-white">
                            {(payload[0].value as number).toLocaleString('pl-PL') + ' ' + primaryVariable.current.metadata.unit}
                          </p>
                        </div>
                      ) : null
                    }
                    cursor={{ fill: GUS_CHART.panel2 }}
                  />
                  <Bar dataKey="value">
                    <Cell fill={GUS_CHART.series} />
                    <Cell fill={GUS_CHART.compare} fillOpacity={0.45} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-tv-seam pt-3 text-[13px]">
              <span className="flex items-center gap-2 font-bold text-tv-paper"><span className="inline-block h-3 w-3 bg-tv-blue" aria-hidden></span>Gmina Rybno</span>
              <span className="flex items-center gap-2 text-tv-muted"><span className="inline-block h-3 w-3" style={{ backgroundColor: GUS_CHART.compare, opacity: 0.45 }} aria-hidden></span>Powiat Działdowski</span>
            </div>
            <p className="mt-3 bg-tv-panel2 px-3 py-2.5 text-[15px] text-[#d7dbe8]">
              Gmina stanowi <strong className="tabular text-white">{primaryVariable.powiat_comparison.percentage_of_powiat}%</strong> wartości powiatu.
            </p>
          </div>
        )}

        {/* Powiat Level Information (Fallback for missing gmina data) */}
        {primaryVariable.current.metadata.level === 'powiat' && (
          <div className="flex h-full min-w-0 flex-col items-start justify-center bg-tv-panel p-4 lg:p-5">
            <h3 className="font-cond flex items-center gap-2 text-[20px] font-extrabold leading-snug text-white">
              <Info className="text-tv-muted" size={18} aria-hidden />
              Dane na poziomie powiatu
            </h3>
            <p className="mt-1 max-w-[60ch] text-[15px] leading-relaxed text-[#d7dbe8]">
              Dla tego wskaźnika szczegółowe dane dla Gminy Rybno nie są dostępne w Banku Danych Lokalnych GUS.
            </p>
            <div className="mt-5 flex flex-col">
              <Tag tone="yellow">Wartość dla Powiatu Działdowskiego</Tag>
              <p className="font-cond tabular bg-tv-panel2 px-3.5 py-3 text-[26px] font-extrabold leading-none text-white">
                {primaryVariable.current.value.toLocaleString('pl-PL')} {primaryVariable.current.metadata.unit}
              </p>
            </div>
          </div>
        )}

        {/* Additional metrics - placeholder for future donut/bar charts */}
        <div className="min-w-0 bg-tv-panel p-4 lg:p-5">
          <h3 className="font-cond mb-2 text-[20px] font-extrabold leading-snug text-white">Dodatkowe metryki</h3>
          <ul className="divide-y divide-tv-seam">
            {variableKeys.slice(0, 5).map(varKey => {
              const variable = variables[varKey];
              return (
                <li key={varKey} className="flex items-baseline justify-between gap-3 py-2 text-[15px]">
                  <span className="min-w-0 text-[#d7dbe8]">{variable.current.metadata.name}</span>
                  <span className="tabular flex shrink-0 items-baseline gap-2">
                    <span className="font-bold text-white">
                      {variable.current.value.toLocaleString('pl-PL')} {variable.current.metadata.unit}
                    </span>
                    {variable.current.trend_pct != null && (
                      <span className="text-[13px] text-tv-muted">{trendText(variable.current.trend_pct)}</span>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>

        {/* Quick stats summary */}
        <div className="min-w-0 bg-tv-panel p-4 lg:p-5">
          <h3 className="font-cond mb-3 text-[20px] font-extrabold leading-snug text-white">Podsumowanie</h3>
          <dl className="space-y-3">
            <div>
              <dt className="text-[13px] text-tv-muted">Liczba wskaźników w sekcji</dt>
              <dd className="font-cond tabular text-[26px] font-extrabold leading-tight text-white">{variableKeys.length}</dd>
            </div>
            <div>
              <dt className="text-[13px] text-tv-muted">Ostatnia aktualizacja</dt>
              <dd className="tabular text-[17px] font-bold text-white">
                {new Date(last_refresh).toLocaleDateString('pl-PL')}
              </dd>
            </div>
            <div>
              <dt className="text-[13px] text-tv-muted">Zakres danych</dt>
              <dd className="tabular text-[17px] font-bold text-white">
                {trendData.length > 0
                  ? `${trendData[0].year} - ${trendData[trendData.length - 1].year}`
                  : 'Brak danych'}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      {/* Data Table (all variables with YoY change) */}
      <section className="flex flex-col">
        <h3 className="flex"><Tag>Wszystkie wskaźniki</Tag></h3>
        <div className="overflow-x-auto border-t-2 border-tv-blue bg-tv-panel">
          <table className="w-full text-[15px]">
            <thead className="border-b border-tv-seam">
              <tr>
                <th className="font-cond px-4 py-3 text-left text-[13px] font-extrabold uppercase tracking-wide text-tv-muted">
                  Wskaźnik
                </th>
                <th className="font-cond px-4 py-3 text-right text-[13px] font-extrabold uppercase tracking-wide text-tv-muted">
                  Wartość (2024)
                </th>
                <th className="font-cond px-4 py-3 text-right text-[13px] font-extrabold uppercase tracking-wide text-tv-muted">
                  Zmiana r/r
                </th>
                <th className="font-cond px-4 py-3 text-center text-[13px] font-extrabold uppercase tracking-wide text-tv-muted">
                  Poziom
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-tv-seam">
              {variableKeys.map(varKey => {
                const variable = variables[varKey];
                return (
                  <tr key={varKey} className="transition-colors hover:bg-tv-panel2">
                    <td className="px-4 py-3 text-[#d7dbe8]">
                      {variable.current.metadata.name}
                    </td>
                    <td className="tabular whitespace-nowrap px-4 py-3 text-right font-bold text-white">
                      {variable.current.value.toLocaleString('pl-PL')} {variable.current.metadata.unit}
                    </td>
                    <td className="tabular whitespace-nowrap px-4 py-3 text-right text-tv-paper">
                      {variable.current.trend_pct != null ? (
                        <>
                          {variable.current.trend_pct >= 0 ? '+' : ''}
                          {variable.current.trend_pct.toFixed(2)}%
                        </>
                      ) : (
                        <span className="text-tv-muted">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {variable.current.metadata.level === 'gmina'
                        ? <Tag tone="seam">Gmina</Tag>
                        : <Tag tone="yellow">Powiat</Tag>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Pro Upsell - only for anonymous/free users */}
      {(!user || user.tier === 'free') && (
        <GUSTierGate
          requiredTier="business"
          currentTier={user?.tier || 'free'}
          context="insights"
        />
      )}

      {/* Data freshness footer */}
      <p className="flex flex-wrap items-center gap-x-2 border-t border-tv-seam pt-4 text-[13px] text-tv-muted">
        <RefreshCw size={14} aria-hidden />
        Ostatnia aktualizacja danych:{' '}
        <strong className="tabular text-tv-paper">
          {new Date(last_refresh).toLocaleDateString('pl-PL', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
          })}
        </strong>
        {' · '}
        Dane GUS są aktualizowane kwartalnie
      </p>
    </div>
  );
};

export default GUSSectionPage;
