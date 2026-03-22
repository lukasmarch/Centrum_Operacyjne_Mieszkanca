import React from 'react';
import { Wind, Droplets, Cloud } from 'lucide-react';
import { useWeather } from '../src/hooks/useWeather';
import { MOCK_WEATHER } from '../constants';

const getWeatherIcon = (condition: string) => {
  const c = condition.toLowerCase();
  if (c.includes('rain') || c.includes('deszcz') || c.includes('drizzle')) return '🌧️';
  if (c.includes('snow') || c.includes('śnieg')) return '❄️';
  if (c.includes('storm') || c.includes('burza')) return '⛈️';
  if (c.includes('fog') || c.includes('mgła')) return '🌫️';
  if (c.includes('cloud') || c.includes('chmur') || c.includes('overcast')) return '☁️';
  return '☀️';
};

const WeatherTile: React.FC = () => {
  const { weather, loading } = useWeather();
  const data = weather || MOCK_WEATHER;

  return (
    <div className="h-full flex flex-col p-5 relative overflow-hidden">

      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <Cloud size={14} className="text-blue-400" />
        <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider">Pogoda</p>
      </div>

      {/* Main: temp + icon */}
      <div className="flex-1 flex items-center justify-between">
        <div>
          <p className="text-5xl font-black text-white leading-none tracking-tight">
            {loading ? '–' : `${data.temp}°C`}
          </p>
          <p className="text-sm text-neutral-400 capitalize mt-2">{data.condition}</p>
        </div>

        {/* Big blue icon box (matching screenshot) */}
        {data.icon ? (
          <div className="w-16 h-16 rounded-2xl bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-600/30 shrink-0">
            <img
              src={`https://openweathermap.org/img/wn/${data.icon}@2x.png`}
              alt={data.condition}
              className="w-12 h-12 object-contain"
              onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
            />
          </div>
        ) : (
          <div className="w-16 h-16 rounded-2xl bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-600/30 shrink-0 text-3xl">
            {getWeatherIcon(data.condition)}
          </div>
        )}
      </div>

      {/* Stats row in rounded boxes */}
      <div className="flex gap-3 mt-auto pt-4">
        <div className="flex-1 bg-gray-900/60 rounded-xl px-3 py-2.5 border border-white/5">
          <p className="text-[8px] font-bold text-neutral-500 uppercase tracking-wider mb-0.5">Wilgotność</p>
          <div className="flex items-center gap-1.5">
            <Droplets size={12} className="text-blue-400" />
            <span className="text-sm font-bold text-white">{data.humidity}%</span>
          </div>
        </div>
        <div className="flex-1 bg-gray-900/60 rounded-xl px-3 py-2.5 border border-white/5">
          <p className="text-[8px] font-bold text-neutral-500 uppercase tracking-wider mb-0.5">Wiatr</p>
          <div className="flex items-center gap-1.5">
            <Wind size={12} className="text-emerald-400" />
            <span className="text-sm font-bold text-white">{data.windSpeed} km/h</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WeatherTile;
