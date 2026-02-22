import React from 'react';
import { Wind, Droplets } from 'lucide-react';
import { useWeather } from '../src/hooks/useWeather';
import { MOCK_WEATHER } from '../constants';

const getGradient = (condition: string) => {
  const c = condition.toLowerCase();
  if (c.includes('rain') || c.includes('deszcz') || c.includes('drizzle')) return 'from-blue-900/50 to-slate-900/80';
  if (c.includes('snow') || c.includes('śnieg'))   return 'from-slate-600/40 to-blue-900/60';
  if (c.includes('cloud') || c.includes('chmur') || c.includes('overcast')) return 'from-slate-700/50 to-slate-900/70';
  if (c.includes('storm') || c.includes('burza'))  return 'from-slate-800/60 to-purple-900/50';
  return 'from-amber-900/30 to-slate-900/70'; // sunny default
};

const getEmoji = (condition: string) => {
  const c = condition.toLowerCase();
  if (c.includes('rain') || c.includes('deszcz') || c.includes('drizzle')) return '🌧️';
  if (c.includes('snow') || c.includes('śnieg'))   return '❄️';
  if (c.includes('storm') || c.includes('burza'))  return '⛈️';
  if (c.includes('cloud') || c.includes('chmur') || c.includes('overcast')) return '☁️';
  if (c.includes('fog') || c.includes('mgła'))     return '🌫️';
  return '☀️';
};

const WeatherTile: React.FC = () => {
  const { weather, loading } = useWeather();
  const data = weather || MOCK_WEATHER;

  return (
    <div className={`h-full flex flex-col p-5 relative overflow-hidden bg-gradient-to-br ${getGradient(data.condition)}`}>

      {/* Big decorative emoji */}
      <div className="absolute -top-2 -right-2 text-7xl opacity-10 select-none pointer-events-none">
        {getEmoji(data.condition)}
      </div>

      <div className="relative z-10 flex flex-col justify-between h-full">
        {/* Location label */}
        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
          Pogoda · Rybno
        </p>

        {/* Main temp */}
        <div className="my-3">
          <div className="flex items-end gap-2">
            <p className="text-5xl font-black text-white leading-none">
              {loading ? '–' : `${data.temp}°`}
            </p>
            {data.icon && (
              <img
                src={`https://openweathermap.org/img/wn/${data.icon}@2x.png`}
                alt={data.condition}
                className="w-12 h-12 object-contain"
                onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
              />
            )}
          </div>
          <p className="text-sm text-slate-400 capitalize mt-1">{data.condition}</p>
        </div>

        {/* Stats row */}
        <div className="flex gap-4 pt-3 border-t border-white/5">
          <div className="flex items-center gap-1.5 text-xs text-blue-300">
            <Droplets size={12} />
            <span>{data.humidity}%</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-emerald-300">
            <Wind size={12} />
            <span>{data.windSpeed} km/h</span>
          </div>
          {data.lakeTemp && (
            <div className="text-xs text-cyan-300">
              Jez. {data.lakeTemp}°C
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default WeatherTile;
