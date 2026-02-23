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

import React, { useState } from 'react';
import { RefreshCw, AlertCircle, ChevronLeft, TrendingUp, Info } from 'lucide-react';
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

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <RefreshCw className="animate-spin text-blue-400 mx-auto mb-4" size={48} />
          <p className="text-slate-400 text-lg font-medium">Ładowanie sekcji...</p>
        </div>
      </div>
    );
  }

  // Error state (403 = tier insufficient)
  if (error) {
    if (error.includes('Premium tier required') || error.includes('403')) {
      return (
        <div className="max-w-4xl mx-auto mt-12 px-4">
          <GUSTierGate
            requiredTier="premium"
            currentTier={user?.tier || 'free'}
            context="section"
          />
        </div>
      );
    }

    return (
      <div className="max-w-2xl mx-auto mt-12 p-8 bg-red-900/20 border border-red-500/30 rounded-xl">
        <div className="flex items-start gap-4">
          <AlertCircle className="text-red-400 flex-shrink-0" size={32} />
          <div>
            <h3 className="text-xl font-bold text-red-300 mb-2">Błąd ładowania sekcji</h3>
            <p className="text-red-400 mb-4">{error}</p>
            <button
              onClick={() => refetch()}
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors font-medium"
            >
              Spróbuj ponownie
            </button>
          </div>
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
      <div className="max-w-2xl mx-auto mt-12 p-8 bg-amber-900/20 border border-amber-500/30 rounded-xl text-center">
        <AlertCircle className="text-amber-400 mx-auto mb-4" size={32} />
        <h3 className="text-xl font-bold text-slate-100 mb-2">Brak danych dla tej sekcji</h3>
        <p className="text-slate-400 mb-4">
          Sekcja nie zawiera jeszcze danych dla Gminy Rybno.
        </p>
        <button
          onClick={onBack}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
        >
          Powrót do przeglądu
        </button>
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

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header with back button */}
      <div className="mb-8">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-blue-400 hover:text-blue-300 font-medium mb-4 transition-colors"
        >
          <ChevronLeft size={20} />
          Powrót do przeglądu
        </button>

        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold text-slate-100 mb-2">{section_name}</h1>
            <p className="text-slate-400">
              Szczegółowe statystyki dla Gminy Rybno · {variableKeys.length} wskaźników
            </p>
          </div>
          {user_tier && (
            <span className="px-4 py-2 rounded-full text-sm font-bold uppercase bg-indigo-900/30 text-indigo-300 border border-indigo-500/30">
              {user_tier}
            </span>
          )}
        </div>
      </div>

      {/* KPI Cards Row (all variables in section) */}
      <div className="mb-8">
        <h2 className="text-xl font-bold text-slate-100 mb-4">Kluczowe wskaźniki</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 min-w-0">
          {variableKeys.map(varKey => {
            const variable = variables[varKey];
            return (
              <button
                key={varKey}
                onClick={() => setSelectedVariable(varKey)}
                className={`text-left transition-all min-w-0 ${selectedVariable === varKey || (!selectedVariable && varKey === firstVariableKey)
                  ? 'ring-2 ring-blue-500'
                  : ''
                  }`}
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
      </div>

      {/* Main Trend Chart */}
      {trendData.length > 0 && (
        <div className="mb-8">
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
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8 min-w-0">
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
          <div className="bg-slate-800/60 rounded-xl border border-white/5 p-5 min-w-0">
            <h3 className="text-lg font-bold text-slate-100 mb-4">Gmina vs Powiat</h3>
            <div style={{ width: '100%', height: '320px', minWidth: 0 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={[
                    { name: 'Gmina Rybno', value: primaryVariable.powiat_comparison.gmina_value, fill: '#3b82f6' },
                    { name: 'Powiat Działdowski', value: primaryVariable.powiat_comparison.powiat_value, fill: '#64748b' }
                  ]}
                  margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" />
                  <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#94a3b8' }} />
                  <YAxis tick={{ fontSize: 12, fill: '#94a3b8' }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1e293b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#f1f5f9' }}
                    formatter={(value: number) => [
                      value.toLocaleString('pl-PL') + ' ' + primaryVariable.current.metadata.unit,
                      'Wartość'
                    ]}
                  />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {
                      [
                        { name: 'Gmina Rybno', fill: '#3b82f6' },
                        { name: 'Powiat Działdowski', fill: '#64748b' }
                      ].map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.fill} />
                      ))
                    }
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-4 p-3 bg-blue-900/20 rounded-lg text-sm text-slate-300 text-center border border-blue-500/20">
              Gmina stanowi <strong className="text-blue-400">{primaryVariable.powiat_comparison.percentage_of_powiat}%</strong> wartości powiatu.
            </div>
          </div>
        )}

        {/* Powiat Level Information (Fallback for missing gmina data) */}
        {primaryVariable.current.metadata.level === 'powiat' && (
          <div className="bg-slate-800/60 rounded-xl border border-white/5 p-5 flex flex-col justify-center items-center text-center h-full min-h-[400px] min-w-0">
            <div className="bg-amber-900/20 p-4 rounded-full mb-4">
              <Info className="text-amber-400" size={32} />
            </div>
            <h3 className="text-lg font-bold text-slate-100 mb-2">Dane na poziomie powiatu</h3>
            <p className="text-slate-400 max-w-sm">
              Dla tego wskaźnika szczegółowe dane dla Gminy Rybno nie są dostępne w Banku Danych Lokalnych GUS.
            </p>
            <div className="mt-6 p-4 bg-slate-700/50 rounded-lg border border-white/10">
              <p className="text-xs text-slate-500 uppercase tracking-wide font-semibold mb-1">
                Wartość dla Powiatu Działdowskiego
              </p>
              <p className="text-2xl font-bold text-slate-100">
                {primaryVariable.current.value.toLocaleString('pl-PL')} {primaryVariable.current.metadata.unit}
              </p>
            </div>
          </div>
        )}

        {/* Additional metrics - placeholder for future donut/bar charts */}
        <div className="bg-slate-800/60 rounded-xl border border-white/5 p-5 min-w-0">
          <h3 className="text-lg font-bold text-slate-100 mb-4">Dodatkowe metryki</h3>
          <div className="space-y-3">
            {variableKeys.slice(0, 5).map(varKey => {
              const variable = variables[varKey];
              return (
                <div key={varKey} className="flex items-center justify-between text-sm">
                  <span className="text-slate-300 font-medium">{variable.current.metadata.name}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-slate-100 font-bold">
                      {variable.current.value.toLocaleString('pl-PL')} {variable.current.metadata.unit}
                    </span>
                    {variable.current.trend_pct != null && (
                      <span
                        className={`text-xs font-semibold ${variable.current.trend_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}
                      >
                        {variable.current.trend_pct >= 0 ? '+' : ''}
                        {variable.current.trend_pct.toFixed(1)}%
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Quick stats summary */}
        <div className="bg-gradient-to-br from-blue-900/30 to-indigo-900/30 rounded-xl border border-blue-500/20 p-5">
          <h3 className="text-lg font-bold text-slate-100 mb-4 flex items-center gap-2">
            <TrendingUp className="text-blue-400" size={20} />
            Podsumowanie
          </h3>
          <div className="space-y-3 text-sm">
            <div>
              <p className="text-slate-400 mb-1">Liczba wskaźników w sekcji</p>
              <p className="text-2xl font-bold text-slate-100">{variableKeys.length}</p>
            </div>
            <div>
              <p className="text-slate-400 mb-1">Ostatnia aktualizacja</p>
              <p className="text-lg font-semibold text-slate-100">
                {new Date(last_refresh).toLocaleDateString('pl-PL')}
              </p>
            </div>
            <div>
              <p className="text-slate-400 mb-1">Zakres danych</p>
              <p className="text-lg font-semibold text-slate-100">
                {trendData.length > 0
                  ? `${trendData[0].year} - ${trendData[trendData.length - 1].year}`
                  : 'Brak danych'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Data Table (all variables with YoY change) */}
      <div className="mb-8 bg-slate-800/60 rounded-xl border border-white/5 overflow-hidden">
        <div className="p-5 border-b border-white/5">
          <h2 className="text-xl font-bold text-slate-100">Wszystkie wskaźniki</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-slate-700/40 border-b border-white/5">
              <tr>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Wskaźnik
                </th>
                <th className="px-5 py-3 text-right text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Wartość (2024)
                </th>
                <th className="px-5 py-3 text-right text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Zmiana r/r
                </th>
                <th className="px-5 py-3 text-center text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Poziom
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {variableKeys.map(varKey => {
                const variable = variables[varKey];
                return (
                  <tr key={varKey} className="hover:bg-slate-700/30 transition-colors">
                    <td className="px-5 py-4 text-sm font-medium text-slate-200">
                      {variable.current.metadata.name}
                    </td>
                    <td className="px-5 py-4 text-sm text-right text-slate-100 font-semibold">
                      {variable.current.value.toLocaleString('pl-PL')} {variable.current.metadata.unit}
                    </td>
                    <td className="px-5 py-4 text-sm text-right">
                      {variable.current.trend_pct != null ? (
                        <span
                          className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-semibold ${variable.current.trend_pct >= 0
                            ? 'bg-green-900/30 text-green-400'
                            : 'bg-red-900/30 text-red-400'
                            }`}
                        >
                          {variable.current.trend_pct >= 0 ? '+' : ''}
                          {variable.current.trend_pct.toFixed(2)}%
                        </span>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>
                    <td className="px-5 py-4 text-center">
                      <span className="inline-block px-2 py-1 rounded text-xs font-semibold bg-slate-700 text-slate-400">
                        {variable.current.metadata.level === 'gmina' ? 'Gmina' : 'Powiat'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Business Upsell (AI Insights) */}
      {user?.tier !== 'business' && (
        <div className="mb-8">
          <GUSTierGate
            requiredTier="business"
            currentTier={user?.tier || 'premium'}
            context="insights"
          />
        </div>
      )}

      {/* Data freshness footer */}
      <div className="mt-8 p-4 bg-slate-800/40 rounded-lg border border-white/5 text-sm text-slate-400 text-center">
        <RefreshCw size={16} className="inline mr-2" />
        Ostatnia aktualizacja danych:{' '}
        <strong className="text-slate-100">
          {new Date(last_refresh).toLocaleDateString('pl-PL', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
          })}
        </strong>
        {' · '}
        Dane GUS są aktualizowane kwartalnie
      </div>
    </div>
  );
};

export default GUSSectionPage;
