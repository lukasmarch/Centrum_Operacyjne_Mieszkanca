
import React from 'react';
import TrafficWidget from './TrafficWidget';
import { MOCK_ARTICLES, MOCK_WEATHER, MOCK_TRAFFIC, MOCK_EVENTS } from '../constants';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import { MOCK_GUS_DATA } from '../constants';
import { useWeather } from '../src/hooks/useWeather';
import { useArticles } from '../src/hooks/useArticles';

const Dashboard: React.FC = () => {
  const { weather, loading: weatherLoading, error: weatherError } = useWeather();
  const { articles, loading: articlesLoading, error: articlesError } = useArticles(3);

  const weatherData = weather || MOCK_WEATHER; // Fallback to mock
  const articlesData = articles || MOCK_ARTICLES; // Fallback to mock

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
      {/* Header Info */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold text-slate-900">Witaj, mieszkańcu! 👋</h2>
          <p className="text-slate-500">Oto najważniejsze informacje z powiatu działdowskiego na dziś.</p>
        </div>
        <div className="flex items-center gap-3 bg-white p-2 px-4 rounded-2xl shadow-sm border border-slate-100">
          <span className="text-2xl">🗓️</span>
          <div className="text-sm">
            <p className="font-semibold">{new Date().toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'long' })}</p>
            <p className="text-slate-400 text-xs">Imprezy: {MOCK_EVENTS.length} zaplanowane</p>
          </div>
        </div>
      </header>

      {/* AI Daily Summary */}
      <section className="relative overflow-hidden bg-gradient-to-br from-blue-600 to-indigo-700 rounded-3xl p-8 text-white shadow-xl">
        <div className="relative z-10 max-w-2xl">
          <div className="flex items-center gap-2 mb-4">
            <span className="bg-white/20 px-3 py-1 rounded-full text-xs font-semibold backdrop-blur-sm">🤖 Podsumowanie AI</span>
            <span className="text-xs text-blue-100">Zaktualizowano 15 min temu</span>
          </div>
          <h3 className="text-2xl font-bold mb-4 italic">"Dzień mija pod znakiem inwestycji i przygotowań do sezonu letniego..."</h3>
          <p className="text-blue-100 leading-relaxed">
            Dziś głównym tematem jest remont drogi Rybno-Działdowo (opóźnienia ok. 10 min).
            Jezioro Rybieńskie osiągnęło optymalną temperaturę do kąpieli (19.5°C).
            Warto zwrócić uwagę na ogłoszony program Dni Działdowa - bilety wkrótce w sprzedaży.
          </p>
          <button className="mt-6 bg-white text-blue-700 px-6 py-2 rounded-xl font-bold text-sm hover:bg-blue-50 transition-colors">
            Czytaj więcej szczegółów
          </button>
        </div>
        <div className="absolute right-[-10%] top-[-20%] w-64 h-64 bg-blue-400/20 rounded-full blur-3xl"></div>
        <div className="absolute right-[10%] bottom-[-20%] w-48 h-48 bg-indigo-400/20 rounded-full blur-3xl"></div>
      </section>

      {/* Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* News Feed */}
        <div className="lg:col-span-2 space-y-6">
          <div className="flex items-center justify-between">
            <h4 className="text-xl font-bold">Najnowsze Wiadomości</h4>
            <div className="flex items-center gap-2">
              {articlesLoading && <span className="text-xs animate-spin">🔄</span>}
              {articlesError && <span className="text-xs text-red-500" title={articlesError}>⚠️</span>}
              <button className="text-blue-600 text-sm font-semibold hover:underline">Wszystkie newsy →</button>
            </div>
          </div>
          <div className="space-y-4">
            {articlesData.map(article => (
              <div key={article.id} className="group bg-white rounded-2xl p-4 flex gap-4 border border-slate-100 shadow-sm hover:shadow-md transition-all cursor-pointer">
                <div className="w-24 h-24 rounded-xl overflow-hidden flex-shrink-0">
                  <img src={article.imageUrl} alt={article.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-blue-600 bg-blue-50 px-2 py-0.5 rounded">{article.source}</span>
                    <span className="text-xs text-slate-400">• {article.timestamp}</span>
                  </div>
                  <h5 className="font-bold text-slate-900 group-hover:text-blue-600 transition-colors leading-snug">{article.title}</h5>
                  <p className="text-sm text-slate-500 line-clamp-2 mt-1">{article.summary}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Sidebar Widgets */}
        <div className="space-y-8">
          {/* Weather Widget */}
          <div className="bg-white rounded-3xl p-6 shadow-sm border border-slate-100">
            <div className="flex items-center justify-between mb-6">
              <h4 className="font-bold">Pogoda i Woda</h4>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">Rybno</span>
                {weatherLoading && <span className="text-xs animate-spin">🔄</span>}
                {weatherError && <span className="text-xs text-red-500" title={weatherError}>⚠️</span>}
              </div>
            </div>
            <div className="flex items-center justify-between mb-8">
              <div>
                <p className="text-4xl font-black text-slate-900 text-center">{weatherData.temp}°C</p>
                <p className="text-slate-500 font-medium capitalize">{weatherData.condition}</p>
              </div>
              <div className="text-5xl">
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
              <div className="bg-blue-50 p-3 rounded-2xl">
                <p className="text-[10px] text-blue-400 font-bold uppercase">Wilgotność</p>
                <p className="font-bold text-blue-700">{weatherData.humidity}%</p>
              </div>
              <div className="bg-emerald-50 p-3 rounded-2xl">
                <p className="text-[10px] text-emerald-400 font-bold uppercase">Wiatr</p>
                <p className="font-bold text-emerald-700">{weatherData.windSpeed} km/h</p>
              </div>
            </div>
          </div>

          {/* Traffic Widget */}
          <TrafficWidget />

          {/* GUS Snippet */}
          <div className="bg-white rounded-3xl p-6 shadow-sm border border-slate-100 overflow-hidden">
            <h4 className="font-bold mb-2">Trend Demograficzny</h4>
            <p className="text-xs text-slate-400 mb-4">Liczba mieszkańców powiatu</p>
            <div className="h-32">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={MOCK_GUS_DATA}>
                  <Line type="monotone" dataKey="value" stroke="#2563eb" strokeWidth={3} dot={false} />
                  <Tooltip />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
