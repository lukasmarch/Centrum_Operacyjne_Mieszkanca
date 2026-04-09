import React, { useMemo } from 'react';
import {
  BarChart, Bar, AreaChart, Area,
  ResponsiveContainer, Tooltip, XAxis
} from 'recharts';
import { useWeather } from '../src/hooks/useWeather';
import { useWeatherHistory } from '../src/hooks/useWeatherHistory';
import { useWeatherForecast } from '../src/hooks/useWeatherForecast';

/* ═══════════════════════════════════════════════════════════════
   HELPERS
═══════════════════════════════════════════════════════════════ */
const DAY_PL  = ['Niedziela','Poniedziałek','Wtorek','Środa','Czwartek','Piątek','Sobota'];
const MON_PL  = ['sty','lut','mar','kwi','maj','cze','lip','sie','wrz','paź','lis','gru'];

function todayLabel() {
  const d = new Date();
  return { day: DAY_PL[d.getDay()], date: `${d.getDate()} ${MON_PL[d.getMonth()]} ${d.getFullYear()}` };
}

function fmtTime(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return `${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function dayLength(sunrise: string | null, sunset: string | null): string {
  if (!sunrise || !sunset) return '—';
  const diff = new Date(sunset).getTime() - new Date(sunrise).getTime();
  const h = Math.floor(diff / 3_600_000);
  const m = Math.floor((diff % 3_600_000) / 60_000);
  return `${h}h ${m}m`;
}

function conditionMeta(main: string, icon: string) {
  const m = (main || '').toLowerCase();
  if (m === 'thunderstorm') return { emoji: '⛈', glow: '#a78bfa' };
  if (m === 'drizzle')      return { emoji: '🌦', glow: '#60a5fa' };
  if (m === 'rain')         return { emoji: '🌧', glow: '#60a5fa' };
  if (m === 'snow')         return { emoji: '❄️', glow: '#bae6fd' };
  if (m === 'atmosphere')   return { emoji: '🌫', glow: '#94a3b8' };
  if (m === 'clouds')       return { emoji: '⛅', glow: '#94a3b8' };
  return { emoji: '☀️', glow: '#fbbf24' };
}

function owmIconUrl(icon: string) {
  return `https://openweathermap.org/img/wn/${icon}@4x.png`;
}

/* ── Wind direction string ──────────────────────────────────── */
function windDir(deg: number | null): string {
  if (deg === null || deg === undefined) return '';
  const dirs = ['N','NE','E','SE','S','SW','W','NW'];
  return dirs[Math.round(deg / 45) % 8];
}

/* ── Liquid-glass panel ─────────────────────────────────────── */
const Panel: React.FC<{ children: React.ReactNode; className?: string; style?: React.CSSProperties }> = ({ children, className = '', style }) => (
  <div
    className={`relative overflow-hidden rounded-2xl ${className}`}
    style={{
      background: 'linear-gradient(135deg, rgba(255,255,255,0.07) 0%, rgba(255,255,255,0.02) 100%)',
      border: '1px solid rgba(255,255,255,0.10)',
      boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.12), inset 0 -1px 0 rgba(0,0,0,0.25), 0 8px 32px rgba(0,0,0,0.5)',
      backdropFilter: 'blur(20px) saturate(1.4)',
      WebkitBackdropFilter: 'blur(20px) saturate(1.4)',
      ...style,
    }}
  >
    <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent pointer-events-none" />
    <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-white/5 to-transparent pointer-events-none" />
    {children}
  </div>
);

/* ── Tooltip ─────────────────────────────────────────────────── */
const MiniTip: React.FC<any> = ({ active, payload, label, unit = '' }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="px-2 py-1 rounded-lg text-[10px] font-bold text-white"
      style={{ background: 'rgba(10,14,23,0.95)', border: '1px solid rgba(255,255,255,0.12)' }}>
      <p className="text-neutral-500">{label}</p>
      <p style={{ color: '#91c5ff' }}>{payload[0]?.value?.toFixed?.(1) ?? payload[0]?.value} {unit}</p>
    </div>
  );
};

/* ── UV Arc Gauge ────────────────────────────────────────────── */
const UVGauge: React.FC<{ value: number }> = ({ value }) => {
  const pct  = Math.min(value / 11, 1);
  const color = pct < 0.27 ? '#34d399' : pct < 0.55 ? '#fbbf24' : pct < 0.73 ? '#f97316' : '#ef4444';
  const r = 38, cx = 50, cy = 50;
  const circ = Math.PI * r; // semicircle
  const filled = circ * pct;
  const label  = value <= 2 ? 'Niski' : value <= 5 ? 'Umiarkowany' : value <= 7 ? 'Wysoki' : value <= 10 ? 'B. Wysoki' : 'Ekstremalny';

  // Angles: start=180° (left) end=0° (right)
  const startRad = Math.PI; // left
  const endRad   = startRad - pct * Math.PI;
  const ex = cx + r * Math.cos(endRad);
  const ey = cy + r * Math.sin(endRad);
  const sx = cx - r; const sy = cy;
  const largeArc = pct > 0.5 ? 1 : 0;

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 100 55" width="110" height="60">
        <path d={`M ${sx} ${sy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="8" strokeLinecap="round" />
        {pct > 0 && (
          <path d={`M ${sx} ${sy} A ${r} ${r} 0 ${largeArc} 1 ${ex} ${ey}`}
            fill="none" stroke={color} strokeWidth="8" strokeLinecap="round"
            style={{ filter: `drop-shadow(0 0 6px ${color})` }} />
        )}
        <circle cx={ex} cy={ey} r="4" fill="white"
          style={{ filter: `drop-shadow(0 0 4px ${color})` }} />
      </svg>
      <div className="text-center -mt-1">
        <p className="text-2xl font-black text-white leading-none">{value.toFixed(1)}/11</p>
        <p className="text-[9px] font-bold" style={{ color }}>{label}</p>
      </div>
    </div>
  );
};

/* ════════════════════════════════════════════════════════════════
   MAIN COMPONENT
════════════════════════════════════════════════════════════════ */
const WeatherTile: React.FC = () => {
  const { weather, loading } = useWeather('Rybno');
  const { history }          = useWeatherHistory('Rybno', 1);
  const { forecast }         = useWeatherForecast('Rybno');

  const { day, date } = todayLabel();
  const meta = conditionMeta(weather?.main ?? '', weather?.icon ?? '');

  /* ── Rain probability chart — from forecast hourly[0..7] ── */
  const rainData = useMemo(() => {
    const slots = forecast?.hourly?.slice(0, 8) ?? [];
    return slots.map(s => {
      const d = new Date(s.dt * 1000);
      const hStr = `${d.getHours()}h`;
      return { t: hStr, v: Math.round((s.pop ?? 0) * 100) };
    });
  }, [forecast]);

  /* ── Hourly forecast row — next 7 slots ─────────────────── */
  const hourlyRow = useMemo(() => {
    const now = Date.now() / 1000;
    const slots = forecast?.hourly ?? [];
    // Find index of slot closest to now
    let start = 0;
    for (let i = 0; i < slots.length; i++) {
      if ((slots[i].dt ?? 0) >= now - 5400) { start = i; break; }
    }
    return slots.slice(start, start + 7).map((s, i) => {
      const d = new Date(s.dt * 1000);
      return {
        label: i === 0 ? 'Teraz' : `${d.getHours()}:00`,
        temp: Math.round(s.temp),
        icon: s.icon,
        isNow: i === 0,
      };
    });
  }, [forecast]);

  /* ── Wind chart: history (>1 pts) or forecast fallback ─── */
  const windData = useMemo(() => {
    if (history.length > 1) {
      return history.slice(-12).map(h => ({
        t: `${new Date(h.fetched_at).getHours()}h`,
        v: +(h.wind_speed * 3.6).toFixed(1),
      }));
    }
    // fallback: use next 12 forecast slots (wind_speed in m/s → km/h)
    const slots = forecast?.hourly?.slice(0, 12) ?? [];
    if (slots.length > 0) {
      return slots.map(s => ({
        t: `${new Date(s.dt * 1000).getHours()}h`,
        v: +(s.wind_speed * 3.6).toFixed(1),
      }));
    }
    return [];
  }, [history, forecast]);

  /* ── Humidity sparkline from DB history ─────────────────── */
  const humData = useMemo(() => {
    if (history.length > 1) {
      return history.slice(-12).map(h => ({
        t: `${new Date(h.fetched_at).getHours()}h`,
        v: h.humidity,
      }));
    }
    return [];
  }, [history]);

  const uvi     = forecast?.uv_index ?? null;
  const sunrise = weather?.sunrise ?? null;
  const sunset  = weather?.sunset  ?? null;

  /* ── Skeleton loader ─────────────────────────────────────── */
  if (loading && !weather) {
    return (
      <div className="h-full flex flex-col p-4 gap-3">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="flex-1 rounded-2xl animate-pulse" style={{ background: 'rgba(255,255,255,0.04)' }} />
        ))}
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col gap-3 p-4 overflow-y-auto no-scrollbar relative">

      {/* Ambient glow */}
      <div className="absolute top-0 right-0 w-60 h-60 rounded-full pointer-events-none"
        style={{ background: meta.glow, filter: 'blur(100px)', opacity: 0.15 }} />

      {/* ══ TOP ROW: Main card + Highlights ════════════════════ */}
      <div className="grid grid-cols-5 gap-3" style={{ minHeight: 195 }}>

        {/* Main weather card */}
        <Panel className="col-span-3 flex flex-col p-5 relative overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-5 rounded-full" style={{ background: `linear-gradient(to bottom, ${meta.glow}, transparent)` }} />
              <div>
                <p className="text-[9px] font-bold text-neutral-500 uppercase tracking-widest">📍 Rybno</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-xs font-bold text-neutral-300">{day}</p>
              <p className="text-[10px] text-neutral-500">{date}</p>
            </div>
          </div>

          {/* Temp + icon */}
          <div className="flex items-center justify-between flex-1">
            <div>
              <p className="text-7xl font-black text-white leading-none tracking-tight">
                {weather ? `${Math.round(weather.temperature)}°C` : '—'}
              </p>
              <p className="text-sm font-semibold mt-1 capitalize" style={{ color: meta.glow }}>
                {weather?.description ?? '—'}
              </p>
              <p className="text-[11px] text-neutral-500 mt-0.5">
                {weather ? (
                  <>Odczuwalnie {Math.round(weather.feels_like)}° · Wys. {Math.round(weather.temp_max)}° / Nis. {Math.round(weather.temp_min)}°</>
                ) : ''}
              </p>
              {weather?.wind_deg !== null && (
                <p className="text-[10px] text-neutral-600 mt-0.5">
                  💨 {weather?.windKmh} km/h {windDir(weather?.wind_deg ?? null)} · ☁️ {weather?.clouds}%
                </p>
              )}
            </div>

            {/* OWM icon */}
            <div className="flex flex-col items-center shrink-0">
              {weather?.icon ? (
                <img
                  src={owmIconUrl(weather.icon)}
                  alt={weather.description}
                  className="w-28 h-28 object-contain"
                  style={{ filter: `drop-shadow(0 0 24px ${meta.glow}99)` }}
                  onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
                />
              ) : (
                <span className="text-[80px] leading-none"
                  style={{ filter: `drop-shadow(0 0 20px ${meta.glow}aa)` }}>
                  {meta.emoji}
                </span>
              )}
            </div>
          </div>
        </Panel>

        {/* Highlights column */}
        <div className="col-span-2 flex flex-col gap-2">

          {/* UV Index — real data from OWM /uvi */}
          <Panel className="flex-1 p-3 flex flex-col">
            <p className="text-[9px] font-bold text-neutral-500 uppercase tracking-widest mb-1">☀️ Indeks UV</p>
            <div className="flex-1 flex items-center justify-center">
              {uvi !== null
                ? <UVGauge value={uvi} />
                : <p className="text-xs text-neutral-600">Brak danych</p>
              }
            </div>
          </Panel>

          {/* Rain probability — real from OWM /forecast pop field */}
          <Panel className="flex-1 p-3 flex flex-col">
            <div className="flex items-center justify-between mb-2">
              <p className="text-[9px] font-bold text-neutral-500 uppercase tracking-widest">🌧 Szansa opadów</p>
              {rainData.length > 0 && rainData.every(d => d.v === 0) && (
                <p className="text-[9px] font-bold text-emerald-500">Brak opadów</p>
              )}
            </div>
            {rainData.length > 0 ? (
              <div className="flex-1" style={{ minHeight: 55 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={rainData} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
                    <XAxis dataKey="t" tick={{ fill: '#374151', fontSize: 8 }} axisLine={false} tickLine={false} />
                    <Tooltip content={<MiniTip unit="%" />} />
                    <defs>
                      <linearGradient id="rainGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.9} />
                        <stop offset="100%" stopColor="#0077b6" stopOpacity={0.4} />
                      </linearGradient>
                    </defs>
                    <Bar dataKey="v" radius={[3, 3, 0, 0]} fill="url(#rainGrad)" minPointSize={3} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-xs text-neutral-600 flex-1 flex items-center">Oczekiwanie na prognozę…</p>
            )}
          </Panel>
        </div>
      </div>

      {/* ══ HOURLY FORECAST — real from OWM /forecast ══════════ */}
      <Panel className="p-3">
        <div className="flex items-center justify-between mb-2">
          <p className="text-[9px] font-bold text-neutral-500 uppercase tracking-widest">⏱ Prognoza godzinowa</p>
          <p className="text-[9px] text-neutral-600">Dziś / Jutro</p>
        </div>
        {hourlyRow.length > 0 ? (
          <div className="flex gap-2 overflow-x-auto no-scrollbar pb-1">
            {hourlyRow.map((h, i) => (
              <div
                key={i}
                className="flex flex-col items-center gap-1 px-3 py-2 rounded-xl shrink-0 transition-all"
                style={h.isNow ? {
                  background: 'rgba(58,129,246,0.18)',
                  border: '1px solid rgba(58,129,246,0.4)',
                  boxShadow: '0 0 16px rgba(58,129,246,0.2)',
                } : {
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}
              >
                <p className="text-[9px] font-bold text-neutral-500">{h.label}</p>
                {h.icon ? (
                  <img src={owmIconUrl(h.icon)} alt="" className="w-8 h-8 object-contain" />
                ) : (
                  <span className="text-2xl leading-none">⛅</span>
                )}
                <p className="text-xs font-black text-white">{h.temp}°</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-neutral-600">Oczekiwanie na prognozę godzinową…</p>
        )}
      </Panel>

      {/* ══ WIND chart + Humidity ══════════════════════════════ */}
      <div className="grid grid-cols-3 gap-3">

        {/* Wind Status — DB history */}
        <Panel className="col-span-2 p-3 flex flex-col">
          <div className="flex items-center justify-between mb-1">
            <p className="text-[9px] font-bold text-neutral-500 uppercase tracking-widest">🌬 Status Wiatru</p>
            <div className="flex items-baseline gap-1">
              <span className="text-base font-black text-white">{weather?.windKmh ?? '—'}</span>
              <span className="text-[9px] text-neutral-500">km/h {windDir(weather?.wind_deg ?? null)}</span>
            </div>
          </div>
          {windData.length > 0 ? (
            <div className="flex-1" style={{ minHeight: 80 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={windData} margin={{ top: 4, right: 0, bottom: 0, left: -20 }}>
                  <XAxis dataKey="t" tick={{ fill: '#374151', fontSize: 7 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<MiniTip unit="km/h" />} />
                  <defs>
                    <linearGradient id="windGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#34d399" stopOpacity={0.95} />
                      <stop offset="100%" stopColor="#059669" stopOpacity={0.3} />
                    </linearGradient>
                  </defs>
                  <Bar dataKey="v" fill="url(#windGrad)" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-xs text-neutral-600 py-4">Brak danych historycznych</p>
          )}
          <p className="text-[8px] text-neutral-700 mt-1 text-right">
            {history.length > 1 ? 'historyczne 12h' : 'prognoza 36h'} · prędkość km/h
          </p>
        </Panel>

        {/* Humidity — DB history sparkline */}
        <Panel className="p-3 flex flex-col items-center justify-center gap-2">
          <p className="text-[9px] font-bold text-neutral-500 uppercase tracking-widest self-start">💧 Wilgotność</p>
          <div className="flex flex-col items-center mt-1">
            <span className="text-5xl leading-none" style={{ filter: 'drop-shadow(0 0 16px rgba(96,165,250,0.6))' }}>
              {weather && weather.humidity > 80 ? '🌧' : '💧'}
            </span>
            <p className="text-3xl font-black text-white mt-2 leading-none">
              {weather?.humidity ?? '—'}<span className="text-base text-neutral-500 font-medium">%</span>
            </p>
          </div>
          {humData.length > 0 ? (
            <div className="w-full" style={{ height: 36 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={humData} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id="humGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#60a5fa" stopOpacity={0.5} />
                      <stop offset="100%" stopColor="#60a5fa" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <Tooltip content={<MiniTip unit="%" />} />
                  <Area type="monotone" dataKey="v" stroke="#60a5fa" strokeWidth={1.5}
                    fill="url(#humGrad)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : null}
          <p className="text-[8px] font-semibold self-end" style={{ color: '#34d399' }}>
            {weather && weather.humidity < 60 ? 'Dobra' : weather && weather.humidity < 80 ? 'Umiarkowana' : 'Wysoka'}
          </p>
        </Panel>
      </div>

      {/* ══ SUNRISE / SUNSET + TOMORROW ══════════════════════════ */}
      <Panel className="p-3">
        {(() => {
          const tomorrow = new Date();
          tomorrow.setDate(tomorrow.getDate() + 1);
          const tomorrowStr = tomorrow.toISOString().slice(0, 10);
          const tSlot = forecast?.hourly?.find(s => (s.dt_txt ?? '').startsWith(tomorrowStr) && s.dt_txt.includes('12:00'));
          return (
            <div className="grid grid-cols-4 divide-x divide-white/[0.07]">
              <div className="px-3 flex flex-col gap-0.5">
                <p className="text-[9px] text-neutral-500 font-bold uppercase tracking-widest">🌅 Wschód</p>
                <p className="text-lg font-black text-white leading-tight whitespace-nowrap">
                  {sunrise ? fmtTime(sunrise) : '—'}<span className="text-[10px] text-neutral-500 font-medium ml-1">AM</span>
                </p>
              </div>
              <div className="px-3 flex flex-col gap-0.5">
                <p className="text-[9px] text-neutral-500 font-bold uppercase tracking-widest">🌇 Zachód</p>
                <p className="text-lg font-black text-white leading-tight whitespace-nowrap">
                  {sunset ? fmtTime(sunset) : '—'}<span className="text-[10px] text-neutral-500 font-medium ml-1">PM</span>
                </p>
              </div>
              <div className="px-3 flex flex-col gap-0.5">
                <p className="text-[9px] text-neutral-500 font-bold uppercase tracking-widest">Długość dnia</p>
                <p className="text-lg font-black text-white leading-tight whitespace-nowrap">{dayLength(sunrise, sunset)}</p>
              </div>
              <div className="px-3 flex items-center justify-between gap-2">
                {tSlot ? (
                  <>
                    <div>
                      <p className="text-[9px] text-neutral-500 font-bold uppercase tracking-widest">Jutro</p>
                      <div className="flex items-baseline gap-1.5 mt-0.5">
                        <p className="text-lg font-black text-white">{Math.round(tSlot.temp)}°</p>
                        <p className="text-[10px] text-neutral-500 capitalize leading-tight">{tSlot.description}</p>
                      </div>
                    </div>
                    <img src={owmIconUrl(tSlot.icon)} alt="" className="w-10 h-10 object-contain shrink-0"
                      style={{ filter: 'drop-shadow(0 0 10px rgba(167,139,250,0.5))' }} />
                  </>
                ) : (
                  <p className="text-xs text-neutral-600">Brak prognozy</p>
                )}
              </div>
            </div>
          );
        })()}
      </Panel>

    </div>
  );
};

export default WeatherTile;
