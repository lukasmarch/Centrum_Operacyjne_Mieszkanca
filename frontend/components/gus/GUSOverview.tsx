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
import { Users, Building2, Wallet, TrendingUp, TrendingDown, RefreshCw } from 'lucide-react';
import { Notice, Skeleton, Tag } from '../simple/tv';
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
      <div aria-label="Ładowanie danych GUS..." className="space-y-6">
        <p className="text-[15px] text-tv-muted">Pobieranie statystyk dla Gminy Rybno…</p>
        <div className="grid grid-cols-1 gap-px bg-tv-seam md:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-32" />)}
        </div>
        <div className="grid grid-cols-1 gap-px bg-tv-seam lg:grid-cols-2">
          {[1, 2].map(i => <Skeleton key={i} className="h-72" />)}
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="max-w-2xl space-y-px" role="alert">
        <Notice tone="warn"><strong>Błąd ładowania danych.</strong> {error}</Notice>
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

  const { variables, latest_year, last_refresh } = data;

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
    <div className="space-y-8">
      {/* Hero KPI Row (8 Free tier variables - Gmina Rybno only).
          Siatka `gap-px` na tle szwu, jak kafle „Na dziś” na pulpicie */}
      <div className="grid min-w-0 grid-cols-2 gap-px border-t-2 border-tv-blue bg-tv-seam lg:grid-cols-4">
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
              unit="zł"
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
              unit="zł"
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
      <section className="flex flex-col">
        <h2 className="flex"><Tag>Trendy historyczne (10 lat)</Tag></h2>
        <p className="mb-3 mt-2 text-[15px] text-tv-muted">
          Wykresy pokazują jak wskaźniki zmieniały się w czasie • Dane od <span className="tabular">{latest_year - 9}</span> do <span className="tabular">{latest_year}</span>
        </p>

        <div className="grid min-w-0 grid-cols-1 gap-px border-t-2 border-tv-blue bg-tv-seam lg:grid-cols-2">
          {/* Population Trend */}
          {population && population.historical && population.historical.length > 0 && (
            <div className="min-w-0 bg-tv-panel p-4 lg:p-5">
              <div className="mb-4">
                <h3 className="font-cond mb-0.5 text-[20px] font-extrabold leading-snug text-white">Ludność gminy</h3>
                <p className="tabular flex items-center gap-1 text-[13px] text-tv-muted">
                  Trend: {population.trend_pct && population.trend_pct > 0 ? <TrendingUp size={14} aria-hidden /> : <TrendingDown size={14} aria-hidden />}
                  {Math.abs(population.trend_pct || 0).toLocaleString('pl-PL', { maximumFractionDigits: 1 })}% rok do roku
                </p>
              </div>
              <TrendChart
                data={population.historical}
                title=""
                unit="os."
                height={250}
                formatType="integer"
              />
            </div>
          )}

          {/* Births Trend */}
          {births && births.historical && births.historical.length > 0 && (
            <div className="min-w-0 bg-tv-panel p-4 lg:p-5">
              <div className="mb-4">
                <h3 className="font-cond mb-0.5 text-[20px] font-extrabold leading-snug text-white">Urodzenia żywe</h3>
                <p className="tabular flex items-center gap-1 text-[13px] text-tv-muted">
                  Trend: {births.trend_pct && births.trend_pct > 0 ? <TrendingUp size={14} aria-hidden /> : <TrendingDown size={14} aria-hidden />}
                  {Math.abs(births.trend_pct || 0).toLocaleString('pl-PL', { maximumFractionDigits: 1 })}% rok do roku
                </p>
              </div>
              <TrendChart
                data={births.historical}
                title=""
                unit="os."
                height={250}
                formatType="integer"
              />
            </div>
          )}

          {/* Migration Balance Trend */}
          {migration && migration.historical && migration.historical.length > 0 && (
            <div className="min-w-0 bg-tv-panel p-4 lg:p-5">
              <div className="mb-4">
                <h3 className="font-cond mb-0.5 text-[20px] font-extrabold leading-snug text-white">Saldo migracji na 1000 ludności</h3>
                <p className="tabular flex items-center gap-1 text-[13px] text-tv-muted">
                  Trend: {migration.trend_pct && migration.trend_pct > 0 ? <TrendingUp size={14} aria-hidden /> : <TrendingDown size={14} aria-hidden />}
                  {Math.abs(migration.trend_pct || 0).toLocaleString('pl-PL', { maximumFractionDigits: 1 })}% rok do roku
                </p>
              </div>
              <TrendChart
                data={migration.historical}
                title=""
                unit=""
                height={250}
                formatType="decimal"
              />
            </div>
          )}

          {/* Business Dynamics - Entity Registrations */}
          {entities && entities.historical && entities.historical.length > 0 && (
            <div className="min-w-0 bg-tv-panel p-4 lg:p-5">
              <div className="mb-4">
                <h3 className="font-cond mb-0.5 text-[20px] font-extrabold leading-snug text-white">Podmioty REGON na 10k</h3>
                <p className="tabular flex items-center gap-1 text-[13px] text-tv-muted">
                  Trend: {entities.trend_pct && entities.trend_pct > 0 ? <TrendingUp size={14} aria-hidden /> : <TrendingDown size={14} aria-hidden />}
                  {Math.abs(entities.trend_pct || 0).toLocaleString('pl-PL', { maximumFractionDigits: 1 })}% rok do roku
                </p>
              </div>
              <TrendChart
                data={entities.historical}
                title=""
                unit=""
                height={250}
                formatType="decimal"
              />
            </div>
          )}

          {/* Revenue Per Capita Trend */}
          {revenue && revenue.historical && revenue.historical.length > 0 && (
            <div className="min-w-0 bg-tv-panel p-4 lg:p-5">
              <div className="mb-4">
                <h3 className="font-cond mb-0.5 text-[20px] font-extrabold leading-snug text-white">Dochody gminy per capita</h3>
                <p className="tabular flex items-center gap-1 text-[13px] text-tv-muted">
                  Trend: {revenue.trend_pct && revenue.trend_pct > 0 ? <TrendingUp size={14} aria-hidden /> : <TrendingDown size={14} aria-hidden />}
                  {Math.abs(revenue.trend_pct || 0).toLocaleString('pl-PL', { maximumFractionDigits: 1 })}% rok do roku
                </p>
              </div>
              <TrendChart
                data={revenue.historical}
                title=""
                unit="zł"
                height={250}
                formatType="currency"
              />
            </div>
          )}

          {/* Expenditure Per Capita Trend */}
          {expenditure && expenditure.historical && expenditure.historical.length > 0 && (
            <div className="min-w-0 bg-tv-panel p-4 lg:p-5">
              <div className="mb-4">
                <h3 className="font-cond mb-0.5 text-[20px] font-extrabold leading-snug text-white">Wydatki gminy per capita</h3>
                <p className="tabular flex items-center gap-1 text-[13px] text-tv-muted">
                  Trend: {expenditure.trend_pct && expenditure.trend_pct > 0 ? <TrendingUp size={14} aria-hidden /> : <TrendingDown size={14} aria-hidden />}
                  {Math.abs(expenditure.trend_pct || 0).toLocaleString('pl-PL', { maximumFractionDigits: 1 })}% rok do roku
                </p>
              </div>
              <TrendChart
                data={expenditure.historical}
                title=""
                unit="zł"
                height={250}
                formatType="currency"
              />
            </div>
          )}
        </div>
      </section>

      {/* Premium Upsell - only for free/anonymous users */}
      {(!user || user.tier === 'free') && (
        <GUSTierGate requiredTier="premium" context="overview" />
      )}

      {/* Footer - Data Freshness */}
      {last_refresh && (
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-tv-seam pt-4 text-[13px] text-tv-muted">
          <div className="flex items-center gap-2">
            <RefreshCw size={14} aria-hidden />
            <span>Ostatnia aktualizacja danych: <span className="tabular">{new Date(last_refresh).toLocaleDateString('pl-PL')}</span></span>
          </div>
          <div>
            <span className="font-bold text-tv-paper">Dane gminy Rybno</span> • Powiat Działdowski • Woj. warmińsko-mazurskie
          </div>
        </div>
      )}
    </div>
  );
};

export default GUSOverview;
