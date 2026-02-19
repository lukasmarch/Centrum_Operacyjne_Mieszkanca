
import React, { useState } from 'react';
import TrafficWidget from './TrafficWidget';
import { CinemaWidget } from './CinemaWidget';
import BusTrackerWidget from './BusTrackerWidget';
import RegonSearchWidget from './RegonSearchWidget';
import WasteWidget from './WasteWidget';
import WasteWidgetPaywall from './WasteWidgetPaywall';
import { MOCK_ARTICLES, MOCK_WEATHER, MOCK_TRAFFIC, MOCK_EVENTS } from '../constants';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

import { useWeather } from '../src/hooks/useWeather';
import { useArticles } from '../src/hooks/useArticles';
import { useDailySummary } from '../src/hooks/useDailySummary';
import { useEvents } from '../src/hooks/useEvents';
import { useWasteSchedule } from '../src/hooks/useWasteSchedule';
import { useAuth } from '../src/context/AuthContext';
import { AppSection } from '../types';

import { getHoliday, getNameDays } from '../src/utils/calendarUtils';

const Dashboard: React.FC<{ onNavigate?: (section: AppSection) => void }> = ({ onNavigate }) => {
  const { user, isPremium, userLocation } = useAuth();
  const { weather, loading: weatherLoading, error: weatherError } = useWeather();
  const { articles, loading: articlesLoading, error: articlesError } = useArticles({ limit: 10 });
  const { summary, loading: summaryLoading, error: summaryError, lastUpdated } = useDailySummary();
  const { events, loading: eventsLoading, error: eventsError } = useEvents(1);
  const wasteEvents = useWasteSchedule(userLocation);

  const weatherData = weather || MOCK_WEATHER; // Fallback to mock

  const today = new Date();
  const holiday = getHoliday(today);
  const nameDays = getNameDays(today);

  // Select 2 articles with source diversity
  const diverseArticles = (() => {
    if (!articles || articles.length === 0) return MOCK_ARTICLES.slice(0, 2);

    // Group by source
    const bySource = new Map<string, typeof articles>();
    articles.forEach(article => {
      const source = article.source;
      if (!bySource.has(source)) {
        bySource.set(source, []);
      }
      bySource.get(source)!.push(article);
    });

    // Get top 1 from each source, then take first 2
    const diverse: typeof articles = [];
    for (const [, sourceArticles] of bySource) {
      if (diverse.length >= 2) break;
      diverse.push(sourceArticles[0]);
    }

    // If we don't have 2 yet, fill with remaining articles
    if (diverse.length < 2) {
      for (const article of articles) {
        if (!diverse.includes(article)) {
          diverse.push(article);
          if (diverse.length >= 2) break;
        }
      }
    }

    return diverse;
  })();

  const upcomingEvent = events && events.length > 0 ? events[0] : null;

  // Format time ago
  const formatTimeAgo = (date: Date | null) => {
    if (!date) return 'niedawno';
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    if (diffMins < 1) return 'przed chwilą';
    if (diffMins < 60) return `${diffMins} min temu`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h temu`;
    return 'wczoraj';
  };

  const handleNavigate = (section: AppSection) => {
    if (onNavigate) {
      onNavigate(section);
    }
  };

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
      {/* Header Info */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-violet-400">
            {user ? `Witaj, ${user.full_name.split(' ')[0]}! 👋` : 'Witaj, mieszkańcu! 👋'}
          </h2>
          <p className="text-slate-400">Centrum Dowodzenia RybnoLive gotowe do działania.</p>
        </div>
        <div className="flex items-center gap-4 text-slate-300/80">
          <div className="text-right hidden md:block">
            <p className="text-2xl font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-violet-400">
              {today.toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'long' })}
            </p>
            {holiday && (
              <p className="text-sm font-medium text-blue-400 mt-0.5">
                🎉 {holiday}
              </p>
            )}
            {nameDays && (
              <p className="text-xs text-slate-500 mt-0.5">
                Imieniny: {nameDays}
              </p>
            )}
          </div>
          <div className="w-12 h-12 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-2xl shadow-inner">
            📅
          </div>
        </div>
      </header>

      {/* AI Daily Summary - Neural Hub */}
      <section className="relative overflow-hidden rounded-3xl p-1 bg-gradient-to-br from-blue-500/20 via-slate-900/50 to-purple-500/20 shadow-2xl">
        <div className="bg-slate-950/90 rounded-[22px] p-8 h-full relative overflow-hidden backdrop-blur-3xl">

          {/* Subtle Grid Background */}
          <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 contrast-150 brightness-100 mix-blend-overlay"></div>
          <div className="absolute inset-0 bg-grid-slate-800/[0.1] bg-[center] [mask-image:linear-gradient(to_bottom,white,transparent)]"></div>

          <div className="relative z-10 flex flex-col md:flex-row gap-8 items-start">

            {/* AI Avatar / Status */}
            <div className="hidden md:flex flex-col items-center gap-3 shrink-0">
              <div className="relative w-20 h-20 flex items-center justify-center rounded-2xl bg-slate-900 border border-slate-800 shadow-inner">
                <span className="text-4xl animate-pulse-slow filter drop-shadow-[0_0_10px_rgba(59,130,246,0.5)]">🤖</span>

                {/* Status Indicator */}
                <div className={`absolute -top-1 -right-1 w-4 h-4 rounded-full border-2 border-slate-950 ${summaryLoading ? 'bg-amber-500 animate-ping' : 'bg-emerald-500'}`}></div>
              </div>
              <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest">v2.1.0</span>
            </div>

            <div className="flex-1 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="bg-blue-500 text-white px-3 py-1 rounded-md text-xs font-bold uppercase tracking-wider shadow-lg shadow-blue-500/20">
                    Neural Briefing
                  </span>
                  <span className="text-xs text-slate-400 font-mono">
                    {summaryLoading ? 'ANALIZOWANIE DANYCH...' : lastUpdated ? `ZAKTUALIZOWANO: ${formatTimeAgo(lastUpdated).toUpperCase()}` : ''}
                  </span>
                </div>
              </div>

              {summaryLoading ? (
                <div className="space-y-4 animate-pulse opacity-50 max-w-2xl">
                  <div className="h-6 bg-slate-800 rounded w-3/4"></div>
                  <div className="h-4 bg-slate-800 rounded w-full"></div>
                  <div className="h-4 bg-slate-800 rounded w-5/6"></div>
                </div>
              ) : summary ? (
                <div className="space-y-5">
                  <h3 className="text-2xl md:text-3xl font-bold text-white leading-tight">
                    {summary.headline}
                  </h3>

                  <div className="text-slate-300 text-lg leading-relaxed font-light border-l-2 border-blue-500/30 pl-4">
                    {summary.highlights && (
                      typeof summary.highlights === 'string' ? (
                        <p dangerouslySetInnerHTML={{ __html: summary.highlights.replace(/\*\*(.*?)\*\*/g, '<strong class="text-white font-semibold relative inline-block">$1<span class="absolute bottom-0 left-0 w-full h-[1px] bg-blue-500/50"></span></strong>') }} />
                      ) : (
                        <div className="flex flex-col gap-3">
                          {summary.highlights.slice(0, 3).map((highlight, index) => (
                            <div key={index} className="flex gap-3 items-start group">
                              <span className="text-blue-500 mt-1.5 text-xs">●</span>
                              <p className="group-hover:text-slate-200 transition-colors">{highlight}</p>
                            </div>
                          ))}
                        </div>
                      )
                    )}
                  </div>

                  <div className="pt-2">
                    <button
                      onClick={() => handleNavigate('news')}
                      className="group flex items-center gap-2 text-sm font-bold text-blue-400 hover:text-blue-300 transition-colors"
                    >
                      <span>Czytaj pełny raport</span>
                      <span className="group-hover:translate-x-1 transition-transform">→</span>
                    </button>
                  </div>
                </div>
              ) : (
                <div className="text-slate-500 italic p-4 bg-slate-900/50 rounded-xl border border-dashed border-slate-800">
                  "System oczekuje na dane wejściowe. Proszę czekać..."
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* News Feed */}
        <div className="lg:col-span-2 space-y-6">
          <div className="flex items-center justify-between px-1">
            <h4 className="text-xl font-bold text-white flex items-center gap-2">
              <span className="w-2 h-6 bg-blue-500 rounded-full"></span>
              Najnowsze Wiadomości
            </h4>
            <div className="flex items-center gap-3">
              {articlesLoading && <span className="text-xs animate-spin text-blue-500">⏳</span>}
              <button
                onClick={() => handleNavigate('news')}
                className="text-slate-400 text-sm font-medium hover:text-white transition-colors"
              >
                Zobacz wszystkie
              </button>
            </div>
          </div>

          <div className="grid gap-4">
            {/* 2 Latest Articles with Source Diversity */}
            {diverseArticles.map(article => (
              <a
                key={article.id}
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="group relative bg-slate-900 rounded-2xl p-5 border border-slate-800 hover:border-blue-500/50 transition-all hover:shadow-lg hover:shadow-blue-900/10 flex flex-col md:flex-row gap-6 overflow-hidden"
              >
                {/* Hover Glow Effect */}
                <div className="absolute inset-0 bg-gradient-to-r from-blue-600/5 to-purple-600/5 opacity-0 group-hover:opacity-100 transition-opacity"></div>

                {article.imageUrl && (
                  <div className="w-full md:w-32 h-48 md:h-32 rounded-xl overflow-hidden shrink-0 bg-slate-800 relative z-10">
                    <img
                      src={article.imageUrl}
                      alt={article.title}
                      className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = 'none';
                      }}
                    />
                  </div>
                )}

                <div className="flex-1 min-w-0 relative z-10 flex flex-col">
                  <div className="flex items-center gap-3 mb-2">
                    <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${article.source.toLowerCase().includes('facebook')
                      ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                      : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                      }`}>
                      {article.source}
                    </span>
                    <span className="text-xs text-slate-500 font-mono">{article.timestamp}</span>
                  </div>

                  <h5 className="font-bold text-lg text-slate-100 group-hover:text-blue-400 transition-colors leading-tight mb-2">
                    {article.title}
                  </h5>

                  <p className="text-sm text-slate-400 line-clamp-2 md:line-clamp-2 leading-relaxed">
                    {article.summary}
                  </p>
                </div>
              </a>
            ))}

            {/* 1 Upcoming Event */}
            {upcomingEvent && (
              <div className="relative bg-slate-900 rounded-2xl p-5 border border-purple-500/20 overflow-hidden">
                <div className="absolute top-0 right-0 p-4 opacity-10">
                  <span className="text-6xl">📅</span>
                </div>

                <div className="flex items-center gap-2 mb-3 relative z-10">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-purple-300 bg-purple-500/20 px-2 py-0.5 rounded border border-purple-500/20">Wydarzenie</span>
                  <span className="text-xs text-purple-400 font-bold">• {upcomingEvent.category}</span>
                </div>

                <div className="flex gap-4 relative z-10">
                  <div className="bg-purple-500 rounded-xl px-4 py-2 flex flex-col items-center justify-center shrink-0 shadow-lg shadow-purple-900/50">
                    <span className="text-xs font-bold text-purple-100 uppercase">{new Date(upcomingEvent.date).toLocaleDateString('pl-PL', { month: 'short' })}</span>
                    <span className="text-2xl font-black text-white">{new Date(upcomingEvent.date).getDate()}</span>
                  </div>

                  <div>
                    <h5 className="font-bold text-slate-100 leading-snug mb-1">{upcomingEvent.title}</h5>
                    <div className="flex items-center gap-2 text-slate-400 text-sm">
                      <span>📍 {upcomingEvent.location}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Sidebar Widgets */}
        <div className="space-y-8">
          {/* REGON Search Widget */}
          <div className="h-[400px]">
            <RegonSearchWidget />
          </div>

          {/* Weather Widget */}
          <div className="glass-panel rounded-3xl p-6">
            <div className="flex items-center justify-between mb-6">
              <h4 className="font-bold text-slate-100">Pogoda i Woda</h4>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">Rybno</span>
                {weatherLoading && <span className="text-xs animate-spin">🔄</span>}
                {weatherError && <span className="text-xs text-red-500" title={weatherError}>⚠️</span>}
              </div>
            </div>
            <div className="flex items-center justify-between mb-8">
              <div>
                <p className="text-4xl font-black text-transparent bg-clip-text bg-gradient-to-br from-white to-slate-400 text-center">{weatherData.temp}°C</p>
                <p className="text-slate-400 font-medium capitalize">{weatherData.condition}</p>
              </div>
              <div className="text-5xl drop-shadow-lg">
                {weatherData.icon ? (
                  <img
                    src={`http://openweathermap.org/img/wn/${weatherData.icon}@2x.png`}
                    alt={weatherData.condition}
                    className="w-16 h-16 object-contain"
                    onError={(e) => {
                      // Fallback if image fails to load
                      (e.target as HTMLImageElement).style.display = 'none';
                      (e.target as HTMLImageElement).nextElementSibling?.classList.remove('hidden');
                    }}
                  />
                ) : null}
                <span className={`${weatherData.icon ? 'hidden' : ''}`}>☀️</span>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-blue-500/10 p-3 rounded-2xl border border-blue-500/20">
                <p className="text-[10px] text-blue-400 font-bold uppercase">Wilgotność</p>
                <p className="font-bold text-blue-200">{weatherData.humidity}%</p>
              </div>
              <div className="bg-emerald-500/10 p-3 rounded-2xl border border-emerald-500/20">
                <p className="text-[10px] text-emerald-400 font-bold uppercase">Wiatr</p>
                <p className="font-bold text-emerald-200">{weatherData.windSpeed} km/h</p>
              </div>
            </div>
          </div>

          {/* Waste Collection Widget - Premium & Business only */}
          {isPremium ? (
            <WasteWidget events={wasteEvents} town={userLocation} />
          ) : user ? (
            <WasteWidgetPaywall />
          ) : null}

          {/* Traffic Widget */}
          <TrafficWidget />

          {/* Cinema Widget */}
          <CinemaWidget />

          {/* GUS Snippet */}
          {/* Bus Tracker Widget */}
          <BusTrackerWidget />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
