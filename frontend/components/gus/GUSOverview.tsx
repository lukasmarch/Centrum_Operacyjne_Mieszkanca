/**
 * GUSOverview Component - REBUILT (2026-02-08)
 *
 * Free tier GUS dashboard - GMINA ONLY (8 variables with historical trends)
 * Focus: MORE charts showing historical data (1995-2024), LESS single-value KPIs
 *
 * Layout:
 * 1. Hero KPI Row (4 cards with sparklines): Population, Businesses, Revenue, Expenditure
 * 2. Historical Trend Charts (4 large charts): Population, Births, Migration, Business Dynamics
 * 3. Premium Upsell + Footer
 */

import React from 'react';
import { Users, Building2, Wallet, RefreshCw, AlertCircle, TrendingUp, ArrowUpRight } from 'lucide-react';
import { useGUSOverview } from '../../src/hooks/useGUSStats';
import { useAuth } from '../../src/context/AuthContext';
import KPICard from './charts/KPICard';
import TrendChart from './charts/TrendChart';
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

  const { variables, user_tier, latest_year, last_refresh } = data;

  // Extract Free tier variables (ONLY 8 verified gmina Rybno variables)
  // Demografia (3 vars)
  const population = variables.population_total;
  const births = variables.births_live;
  const migration = variables.migration_balance_per_1k;

  // Przedsiębiorczość (3 vars)
  const entities = variables.entities_regon_per_10k;
  const newEntities = variables.new_entities_per_10k;
  const deregistered = variables.deregistered_per_10k;

  // Finanse Gminy (2 vars)
  const revenue = variables.revenue_per_capita;
  const expenditure = variables.expenditure_per_capita;

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
              Dane historyczne z Banku Danych Lokalnych GUS (1995-{latest_year})
            </p>
            <p className="text-sm text-gray-500 mt-1">
              Pokazujemy TYLKO dane gminy Rybno • 8 wskaźników • {user_tier === 'free' ? 'Free tier' : user_tier}
            </p>
          </div>
          {user_tier && (
            <span className="px-4 py-2 rounded-full text-sm font-bold uppercase bg-gray-100 text-gray-600">
              {user_tier === 'free' ? 'FREE (8 wskaźników)' : user_tier}
            </span>
          )}
        </div>
      </div>

      {/* Hero KPI Row (8 Free tier variables - Gmina Rybno only) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8 min-w-0">
        {/* Row 1: Core Metrics */}
        {population && (
          <div className="min-w-0">
            <KPICard
              label="Liczba ludności"
              value={population.value}
              unit="osób"
              trend={population.trend_pct}
              sparklineData={population.historical}
              icon={Users}
              formatType="integer"
            />
          </div>
        )}

        {births && (
          <div className="min-w-0">
            <KPICard
              label="Urodzenia żywe"
              value={births.value}
              unit="os."
              trend={births.trend_pct}
              sparklineData={births.historical}
              icon={Users}
              formatType="integer"
            />
          </div>
        )}

        {revenue && (
          <div className="min-w-0">
            <KPICard
              label="Dochody per capita"
              value={revenue.value}
              unit="PLN"
              trend={revenue.trend_pct}
              sparklineData={revenue.historical}
              icon={Wallet}
              formatType="currency"
            />
          </div>
        )}

        {expenditure && (
          <div className="min-w-0">
            <KPICard
              label="Wydatki per capita"
              value={expenditure.value}
              unit="PLN"
              trend={expenditure.trend_pct}
              sparklineData={expenditure.historical}
              icon={Wallet}
              formatType="currency"
            />
          </div>
        )}

        {/* Row 2: Business & Migration */}
        {entities && (
          <div className="min-w-0">
            <KPICard
              label="Firmy na 10k mieszkańców"
              value={entities.value}
              unit=""
              trend={entities.trend_pct}
              sparklineData={entities.historical}
              icon={Building2}
              formatType="float"
            />
          </div>
        )}

        {newEntities && (
          <div className="min-w-0">
            <KPICard
              label="Nowe firmy na 10k"
              value={newEntities.value}
              unit=""
              trend={newEntities.trend_pct}
              sparklineData={newEntities.historical}
              icon={TrendingUp}
              formatType="float"
            />
          </div>
        )}

        {deregistered && (
          <div className="min-w-0">
            <KPICard
              label="Wykreślone firmy na 10k"
              value={deregistered.value}
              unit=""
              trend={deregistered.trend_pct}
              sparklineData={deregistered.historical}
              icon={Building2}
              formatType="float"
            />
          </div>
        )}

        {migration && (
          <div className="min-w-0">
            <KPICard
              label="Saldo migracji na 1000"
              value={migration.value}
              unit=""
              trend={migration.trend_pct}
              sparklineData={migration.historical}
              icon={Users}
              formatType="float"
            />
          </div>
        )}
      </div>

      {/* Historical Trend Charts Section */}
      <div className="mb-8">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Trendy historyczne (10 lat)</h2>
          <p className="text-gray-600">
            Wykresy pokazują jak wskaźniki zmieniały się w czasie • Dane od {latest_year - 9} do {latest_year}
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 min-w-0">
          {/* Population Trend */}
          {population && population.historical && population.historical.length > 0 && (
            <div className="bg-gray-50 rounded-xl p-6 min-w-0">
              <div className="mb-4">
                <h3 className="text-lg font-bold text-gray-900 mb-1">Ludność gminy</h3>
                <p className="text-sm text-gray-500">
                  Trend: {population.trend_pct && population.trend_pct > 0 ? '▲' : '▼'}{' '}
                  {Math.abs(population.trend_pct || 0).toFixed(2)}% rok do roku
                </p>
              </div>
              <TrendChart
                data={population.historical}
                title=""
                unit="os."
                height={250}
                color="#3b82f6"
                formatType="integer"
              />
            </div>
          )}

          {/* Births Trend */}
          {births && births.historical && births.historical.length > 0 && (
            <div className="bg-gray-50 rounded-xl p-6 min-w-0">
              <div className="mb-4">
                <h3 className="text-lg font-bold text-gray-900 mb-1">Urodzenia żywe</h3>
                <p className="text-sm text-gray-500">
                  Trend: {births.trend_pct && births.trend_pct > 0 ? '▲' : '▼'}{' '}
                  {Math.abs(births.trend_pct || 0).toFixed(2)}% rok do roku
                </p>
              </div>
              <TrendChart
                data={births.historical}
                title=""
                unit="os."
                height={250}
                color="#10b981"
                formatType="integer"
              />
            </div>
          )}

          {/* Migration Balance Trend */}
          {migration && migration.historical && migration.historical.length > 0 && (
            <div className="bg-gray-50 rounded-xl p-6 min-w-0">
              <div className="mb-4">
                <h3 className="text-lg font-bold text-gray-900 mb-1">Saldo migracji na 1000 ludności</h3>
                <p className="text-sm text-gray-500">
                  Trend: {migration.trend_pct && migration.trend_pct > 0 ? '▲' : '▼'}{' '}
                  {Math.abs(migration.trend_pct || 0).toFixed(2)}% zmiana YoY
                </p>
              </div>
              <TrendChart
                data={migration.historical}
                title=""
                unit=""
                height={250}
                color="#f59e0b"
                formatType="decimal"
              />
            </div>
          )}

          {/* Business Dynamics - Entity Registrations */}
          {entities && entities.historical && entities.historical.length > 0 && (
            <div className="bg-gray-50 rounded-xl p-6 min-w-0">
              <div className="mb-4">
                <h3 className="text-lg font-bold text-gray-900 mb-1">Podmioty REGON na 10k</h3>
                <p className="text-sm text-gray-500">
                  Trend: {entities.trend_pct && entities.trend_pct > 0 ? '▲' : '▼'}{' '}
                  {Math.abs(entities.trend_pct || 0).toFixed(2)}% rok do roku
                </p>
              </div>
              <TrendChart
                data={entities.historical}
                title=""
                unit=""
                height={250}
                color="#8b5cf6"
                formatType="decimal"
              />
            </div>
          )}

          {/* Revenue Per Capita Trend */}
          {revenue && revenue.historical && revenue.historical.length > 0 && (
            <div className="bg-gray-50 rounded-xl p-6 min-w-0">
              <div className="mb-4">
                <h3 className="text-lg font-bold text-gray-900 mb-1">Dochody gminy per capita</h3>
                <p className="text-sm text-gray-500">
                  Trend: {revenue.trend_pct && revenue.trend_pct > 0 ? '▲' : '▼'}{' '}
                  {Math.abs(revenue.trend_pct || 0).toFixed(2)}% rok do roku
                </p>
              </div>
              <TrendChart
                data={revenue.historical}
                title=""
                unit="PLN"
                height={250}
                color="#0ea5e9"
                formatType="currency"
              />
            </div>
          )}

          {/* Expenditure Per Capita Trend */}
          {expenditure && expenditure.historical && expenditure.historical.length > 0 && (
            <div className="bg-gray-50 rounded-xl p-6 min-w-0">
              <div className="mb-4">
                <h3 className="text-lg font-bold text-gray-900 mb-1">Wydatki gminy per capita</h3>
                <p className="text-sm text-gray-500">
                  Trend: {expenditure.trend_pct && expenditure.trend_pct > 0 ? '▲' : '▼'}{' '}
                  {Math.abs(expenditure.trend_pct || 0).toFixed(2)}% rok do roku
                </p>
              </div>
              <TrendChart
                data={expenditure.historical}
                title=""
                unit="PLN"
                height={250}
                color="#f43f5e"
                formatType="currency"
              />
            </div>
          )}
        </div>
      </div>

      {/* Premium Upsell */}
      <GUSTierGate requiredTier="premium" currentTier={user_tier || 'free'}>
        <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-8 border border-blue-100">
          <div className="flex items-start gap-6">
            <div className="p-4 bg-white rounded-lg shadow-sm">
              <TrendingUp className="text-blue-600" size={32} />
            </div>
            <div className="flex-1">
              <h3 className="text-2xl font-bold text-gray-900 mb-2">
                Odblokuj Premium - 47 dodatkowych wskaźników
              </h3>
              <p className="text-gray-700 mb-4 leading-relaxed">
                Uzyskaj dostęp do pełnej analizy gminy:
              </p>
              <ul className="space-y-2 mb-6">
                <li className="flex items-center gap-2 text-gray-700">
                  <ArrowUpRight className="text-blue-600" size={18} />
                  <span>7 kategorii danych (Demografia, Finanse, Przedsiębiorczość, Edukacja, Zdrowie, Rynek Pracy, Mieszkalnictwo)</span>
                </li>
                <li className="flex items-center gap-2 text-gray-700">
                  <ArrowUpRight className="text-blue-600" size={18} />
                  <span>Porównania gmina vs powiat Działdowski</span>
                </li>
                <li className="flex items-center gap-2 text-gray-700">
                  <ArrowUpRight className="text-blue-600" size={18} />
                  <span>Dane historyczne od 1995 roku</span>
                </li>
                <li className="flex items-center gap-2 text-gray-700">
                  <ArrowUpRight className="text-blue-600" size={18} />
                  <span>Export danych do CSV/Excel</span>
                </li>
              </ul>
              <a
                href="/pricing"
                className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-semibold shadow-sm"
              >
                Zobacz plany Premium
                <ArrowUpRight size={18} />
              </a>
            </div>
          </div>
        </div>
      </GUSTierGate>

      {/* Footer - Data Freshness */}
      {last_refresh && (
        <div className="mt-8 pt-6 border-t border-gray-200">
          <div className="flex items-center justify-between text-sm text-gray-500">
            <div className="flex items-center gap-2">
              <RefreshCw size={16} />
              <span>Ostatnia aktualizacja danych: {new Date(last_refresh).toLocaleDateString('pl-PL')}</span>
            </div>
            <div>
              <span className="font-medium">Dane gminy Rybno</span> • Powiat Działdowski • Woj. warmińsko-mazurskie
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default GUSOverview;
