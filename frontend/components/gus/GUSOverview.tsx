/**
 * GUSOverview Component
 *
 * Free tier GUS dashboard showing 9 core KPI variables
 * Accessible to all users (no authentication required)
 *
 * Layout (inspired by polskawliczbach.pl):
 * 1. Hero KPI Row (4 cards): Population, Unemployment, Avg Salary, Businesses/10k
 * 2. Key Charts Grid (2x2):
 *    - Population trend (10 years)
 *    - Age structure (donut: 0-14, 15-64, 65+)
 *    - Business dynamics (new vs closed)
 *    - Gminy comparison (top 3 metrics)
 * 3. Additional KPI cards (5 more variables)
 * 4. Premium Upsell
 * 5. Data freshness footer
 *
 * Total: 9 Free tier variables displayed
 */

import React from 'react';
import { Users, Briefcase, TrendingDown, Building2, RefreshCw, AlertCircle } from 'lucide-react';
import { useGUSOverview } from '../../src/hooks/useGUSStats';
import { useAuth } from '../../src/context/AuthContext';
import KPICard from './charts/KPICard';
import TrendChart from './charts/TrendChart';
import DonutChart from './charts/DonutChart';
import ComparisonBar from './charts/ComparisonBar';
import GUSTierGate from './layout/GUSTierGate';

const GUSOverview: React.FC = () => {
  const { data, loading, error, refetch } = useGUSOverview();
  const { user } = useAuth();

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <RefreshCw className="animate-spin text-blue-600 mx-auto mb-4" size={48} />
          <p className="text-gray-600 text-lg font-medium">Ładowanie danych GUS...</p>
          <p className="text-gray-400 text-sm mt-2">Pobieranie statystyk dla Gminy Rybno</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="max-w-2xl mx-auto mt-12 p-8 bg-red-50 border border-red-200 rounded-xl">
        <div className="flex items-start gap-4">
          <AlertCircle className="text-red-600 flex-shrink-0" size={32} />
          <div>
            <h3 className="text-xl font-bold text-red-900 mb-2">Błąd ładowania danych</h3>
            <p className="text-red-700 mb-4">{error}</p>
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

  const { variables, user_tier, last_refresh } = data;

  // Extract specific variables (9 Free tier)
  const population = variables.population_total;
  const unemployment = variables.unemployment_rate;
  const avgSalary = variables.avg_salary;
  const businesses = variables.businesses_total;
  const businessesPer10k = variables.businesses_per_10k;
  const populationDensity = variables.population_density;
  const workingAge = variables.population_working_age_pct;
  const births = variables.births_total;
  const deaths = variables.deaths_total;

  // Prepare data for charts

  // 1. Population trend (last 10 years) - mock data, real would come from historical
  const populationTrendData = [
    { year: 2015, value: 7200 },
    { year: 2016, value: 7150 },
    { year: 2017, value: 7100 },
    { year: 2018, value: 7000 },
    { year: 2019, value: 6900 },
    { year: 2020, value: 6850 },
    { year: 2021, value: 6800 },
    { year: 2022, value: 6750 },
    { year: 2023, value: 6700 },
    { year: 2024, value: population?.value || 6682 },
  ];

  // 2. Age structure (mock - would need age breakdown variables)
  const ageStructureData = [
    { name: '0-14 lat', value: Math.round((population?.value || 6682) * 0.15), color: '#3b82f6' },
    { name: '15-64 lat', value: Math.round((population?.value || 6682) * 0.65), color: '#10b981' },
    { name: '65+ lat', value: Math.round((population?.value || 6682) * 0.20), color: '#f59e0b' },
  ];

  // 3. Business dynamics (mock - new vs closed)
  const businessDynamicsData = [
    { name: 'Nowe firmy', value: 45, color: '#10b981' },
    { name: 'Wykreślone', value: 28, color: '#ef4444' },
  ];

  // 4. Gminy comparison (mock - would come from backend)
  const gminyComparisonData = [
    { unit_name: 'Gmina Rybno', unit_id: '042815403062', value: population?.value || 6682, year: 2024 },
    { unit_name: 'Gmina Działdowo', unit_id: '0428154', value: 8500, year: 2024 },
    { unit_name: 'Gmina Lidzbark', unit_id: '0428155', value: 7800, year: 2024 },
    { unit_name: 'Gmina Iłowo-Osada', unit_id: '0428156', value: 5200, year: 2024 },
    { unit_name: 'Gmina Płośnica', unit_id: '0428157', value: 4500, year: 2024 },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              Statystyki GUS - Gmina Rybno
            </h1>
            <p className="text-gray-600">
              Dane statystyczne z Banku Danych Lokalnych GUS
            </p>
          </div>
          {user_tier && (
            <span className="px-4 py-2 rounded-full text-sm font-bold uppercase bg-gray-100 text-gray-600">
              {user_tier === 'free' ? 'Free (9 wskaźników)' : user_tier}
            </span>
          )}
        </div>
      </div>

      {/* Hero KPI Row (4 main cards) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {population && (
          <KPICard
            label="Liczba ludności"
            value={population.value}
            unit="osób"
            trend={population.trend_pct}
            icon={Users}
            formatType="integer"
          />
        )}
        {unemployment && (
          <KPICard
            label="Stopa bezrobocia"
            value={unemployment.value}
            unit="%"
            trend={unemployment.trend_pct}
            icon={TrendingDown}
            formatType="decimal"
          />
        )}
        {avgSalary && (
          <KPICard
            label="Średnie wynagrodzenie"
            value={avgSalary.value}
            unit="PLN"
            trend={avgSalary.trend_pct}
            icon={Briefcase}
            formatType="currency"
          />
        )}
        {businessesPer10k && (
          <KPICard
            label="Firmy na 10k mieszkańców"
            value={businessesPer10k.value}
            unit="firm"
            trend={businessesPer10k.trend_pct}
            icon={Building2}
            formatType="integer"
          />
        )}
      </div>

      {/* Key Charts Grid (2x2) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <TrendChart
          data={populationTrendData}
          title="Trend populacji (10 lat)"
          unit="osób"
          color="#3b82f6"
          height={280}
          formatType="integer"
        />

        <DonutChart
          data={ageStructureData}
          title="Struktura wieku"
          unit="osób"
          height={280}
          innerRadius={60}
          formatType="integer"
        />

        <DonutChart
          data={businessDynamicsData}
          title="Dynamika firm (2024)"
          unit="firm"
          height={280}
          innerRadius={60}
          formatType="integer"
        />

        <ComparisonBar
          data={gminyComparisonData}
          title="Porównanie populacji gmin"
          unit="osób"
          maxItems={5}
          height={280}
          formatType="integer"
        />
      </div>

      {/* Additional KPI cards (5 more) */}
      <div className="mb-8">
        <h2 className="text-xl font-bold text-gray-900 mb-4">Dodatkowe wskaźniki</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
          {businesses && (
            <KPICard
              label="Liczba firm"
              value={businesses.value}
              unit="firm"
              trend={businesses.trend_pct}
              formatType="integer"
            />
          )}
          {populationDensity && (
            <KPICard
              label="Gęstość zaludnienia"
              value={populationDensity.value}
              unit="os/km²"
              trend={populationDensity.trend_pct}
              formatType="integer"
            />
          )}
          {workingAge && (
            <KPICard
              label="% w wieku produkcyjnym"
              value={workingAge.value}
              unit="%"
              trend={workingAge.trend_pct}
              formatType="decimal"
            />
          )}
          {births && (
            <KPICard
              label="Urodzenia (rok)"
              value={births.value}
              unit="dzieci"
              trend={births.trend_pct}
              formatType="integer"
            />
          )}
          {deaths && (
            <KPICard
              label="Zgony (rok)"
              value={deaths.value}
              unit="osób"
              trend={deaths.trend_pct}
              formatType="integer"
            />
          )}
        </div>
      </div>

      {/* Premium Upsell */}
      <div className="mb-8">
        <GUSTierGate
          requiredTier="premium"
          currentTier={user?.tier || 'free'}
          context="overview"
        />
      </div>

      {/* Data freshness footer */}
      <div className="mt-8 p-4 bg-gray-50 rounded-lg border border-gray-200 text-sm text-gray-600 text-center">
        <RefreshCw size={16} className="inline mr-2" />
        Ostatnia aktualizacja danych:{' '}
        <strong className="text-gray-900">
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

export default GUSOverview;
