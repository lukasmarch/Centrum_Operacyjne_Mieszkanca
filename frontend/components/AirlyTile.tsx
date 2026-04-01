import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  AreaChart, Area, BarChart, Bar,
  ResponsiveContainer, Tooltip, XAxis
} from 'recharts';

const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000/api';

/* ═══════════════════════════════════════════════════════════════
   TYPES & CONSTANTS
═══════════════════════════════════════════════════════════════ */
interface AirQualityData {
  pm25: number; pm10: number; caqi: number; caqi_level: string;
  temperature: number; humidity: number; pressure: number; fetched_at: string;
}
interface HistoryItem { pm25: number; pm10: number; caqi: number; fetched_at: string; }

const LEVEL_META: Record<string, { label: string; color: string; bg: string; advice: string; emoji: string }> = {
  VERY_LOW: { label: 'Bardzo Dobra', color: '#34d399', bg: 'rgba(52,211,153,0.10)', advice: 'Idealna pogoda na spacer! Oddychaj głęboko.', emoji: '🌿' },
  LOW:      { label: 'Dobra',        color: '#4ade80', bg: 'rgba(74,222,128,0.10)', advice: 'Możesz spędzać czas na zewnątrz bez obaw.',   emoji: '✅' },
  MEDIUM:   { label: 'Umiarkowana', color: '#fbbf24', bg: 'rgba(251,191,36,0.10)',  advice: 'Osoby wrażliwe powinny ograniczyć wysiłek.',  emoji: '⚠️' },
  HIGH:     { label: 'Zła',         color: '#fb923c', bg: 'rgba(251,146,60,0.10)',  advice: 'Lepiej zostań w domu i zamknij okna.',         emoji: '🏠' },
  VERY_HIGH:{ label: 'Bardzo Zła',  color: '#f87171', bg: 'rgba(248,113,113,0.10)', advice: 'Unikaj wychodzenia na zewnątrz!',              emoji: '🚨' },
  EXTREME:  { label: 'Ekstremalna', color: '#c084fc', bg: 'rgba(192,132,252,0.10)', advice: 'Zagrożenie zdrowia! Bezwzględnie zostań w domu.',emoji: '☠️'},
};
const getLvl = (l: string) => LEVEL_META[l] ?? { label: 'Brak danych', color: '#737373', bg: 'rgba(115,115,115,0.06)', advice: 'Monitorujemy jakość powietrza.', emoji: '📊' };

/* ── Rich mock data (always shown when API fails) ─────────────── */
const MOCK_AIR: AirQualityData = {
  pm25: 11.4, pm10: 18.2, caqi: 28, caqi_level: 'LOW',
  temperature: 12.1, humidity: 63, pressure: 1013, fetched_at: new Date().toISOString(),
};

function buildMockHistory(): HistoryItem[] {
  return Array.from({ length: 18 }, (_, i) => {
    const base = 28 + (Math.random() - 0.5) * 30;
    const caqi = Math.max(5, Math.min(100, Math.round(base)));
    return {
      pm25: +(caqi * 0.35 + (Math.random() - 0.5) * 5).toFixed(1),
      pm10: +(caqi * 0.65 + (Math.random() - 0.5) * 8).toFixed(1),
      caqi,
      fetched_at: new Date(Date.now() - (18 - i) * 4 * 60 * 60 * 1000).toISOString(),
    };
  });
}

function fmtDate(iso: string) {
  const d = new Date(iso);
  return `${d.getDate()}.${String(d.getMonth()+1).padStart(2,'0')} ${d.getHours()}h`;
}
function fmtHour(iso: string) {
  const d = new Date(iso);
  return `${d.getHours()}h`;
}

/* ═══════════════════════════════════════════════════════
   SVG DONUT GAUGE (large, premium)
═══════════════════════════════════════════════════════ */
const DonutGauge: React.FC<{ value: number; maxValue?: number; color: string; label: string; sublabel: string }> = ({
  value, maxValue = 100, color, label, sublabel
}) => {
  const r = 52, cx = 68, cy = 68;
  const circ = 2 * Math.PI * r;
  const pct = Math.min(value / maxValue, 1);
  const filled = circ * pct;
  const empty = circ - filled;

  return (
    <div className="relative flex items-center justify-center" style={{ width: 136, height: 136 }}>
      <svg width="136" height="136" viewBox="0 0 136 136" style={{ transform: 'rotate(-90deg)' }}>
        {/* Outer glow ring */}
        <circle cx={cx} cy={cy} r={r + 6} fill="none" stroke={color} strokeWidth="1" strokeOpacity="0.08" />
        {/* Background track */}
        <circle cx={cx} cy={cy} r={r} fill="none"
          stroke="rgba(255,255,255,0.06)" strokeWidth="10" strokeDasharray={`${circ}`} />
        {/* Filled arc */}
        <circle cx={cx} cy={cy} r={r} fill="none"
          stroke="url(#gaugeGrad)" strokeWidth="10"
          strokeDasharray={`${filled} ${empty}`}
          strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 8px ${color})`, transition: 'stroke-dasharray 1.2s ease' }}
        />
        <defs>
          <linearGradient id="gaugeGrad" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="136" y2="136">
            <stop offset="0%" stopColor={color} stopOpacity="0.7" />
            <stop offset="100%" stopColor={color} stopOpacity="1" />
          </linearGradient>
        </defs>
        {/* Tick marks */}
        {Array.from({ length: 10 }, (_, i) => {
          const angle = (i / 10) * 2 * Math.PI;
          const inner = r - 7, outer = r - 3;
          const x1 = cx + inner * Math.cos(angle), y1 = cy + inner * Math.sin(angle);
          const x2 = cx + outer * Math.cos(angle), y2 = cy + outer * Math.sin(angle);
          return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="rgba(255,255,255,0.15)" strokeWidth="1" />;
        })}
      </svg>
      {/* Center content */}
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-0.5">
        <span className="text-3xl font-black leading-none text-white">{Math.round(value)}</span>
        <span className="text-[9px] font-bold uppercase tracking-widest text-neutral-500">{label}</span>
        <span className="text-[11px] font-bold mt-0.5" style={{ color }}>{sublabel}</span>
      </div>
    </div>
  );
};

/* ═══════════════════════════════════════════════════════
   PM BAR
═══════════════════════════════════════════════════════ */
const PMBar: React.FC<{ label: string; value: number; norm: number; color: string; unit?: string }> = ({
  label, value, norm, color, unit = 'µg/m³'
}) => {
  const pct = Math.min((value / (norm * 2)) * 100, 100);
  const over = value > norm;
  const barColor = over ? 'linear-gradient(90deg, #f97316, #ef4444)' : `linear-gradient(90deg, ${color}, ${color}88)`;

  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full" style={{ background: over ? '#f97316' : color, boxShadow: `0 0 4px ${over ? '#f97316' : color}` }} />
          <span className="text-[10px] font-bold text-neutral-400">{label}</span>
        </div>
        <div className="flex items-baseline gap-1">
          <span className="text-sm font-black" style={{ color: over ? '#f97316' : 'white' }}>{value.toFixed(1)}</span>
          <span className="text-[8px] text-neutral-600">{unit}</span>
          <span className="text-[8px] font-bold px-1.5 py-0.5 rounded-full ml-1"
            style={{ background: over ? 'rgba(249,115,22,0.15)' : 'rgba(52,211,153,0.1)', color: over ? '#f97316' : '#34d399', border: `1px solid ${over ? '#f9731633' : '#34d39933'}` }}>
            {Math.round((value / norm) * 100)}%
          </span>
        </div>
      </div>
      <div className="h-2 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.05)' }}>
        <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${pct}%`, background: barColor }} />
      </div>
      <div className="flex justify-end mt-0.5">
        <span className="text-[7px] text-neutral-700">норма WHO: {norm} {unit}</span>
      </div>
    </div>
  );
};

/* ═══════════════════════════════════════════════════════
   LIQUID GLASS CARD
═══════════════════════════════════════════════════════ */
const GCard: React.FC<{ children: React.ReactNode; className?: string; style?: React.CSSProperties }> = ({ children, className = '', style }) => (
  <div
    className={`relative overflow-hidden rounded-2xl ${className}`}
    style={{
      background: 'rgba(255,255,255,0.04)',
      border: '1px solid rgba(255,255,255,0.09)',
      boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.07), inset 0 -1px 0 rgba(0,0,0,0.15), 0 4px 20px rgba(0,0,0,0.4)',
      backdropFilter: 'blur(16px)',
      WebkitBackdropFilter: 'blur(16px)',
      ...style,
    }}
  >
    <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/12 to-transparent pointer-events-none" />
    {children}
  </div>
);

/* ═══════════════════════════════════════════════════════
   TOOLTIP
═══════════════════════════════════════════════════════ */
const CTip: React.FC<any> = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="px-2 py-1 rounded-lg text-[10px] font-bold"
      style={{ background: 'rgba(10,14,23,0.96)', border: '1px solid rgba(255,255,255,0.10)', color: '#91c5ff' }}>
      <p className="text-neutral-500 text-[8px]">{label}</p>
      <p>CAQI: {payload[0].value}</p>
    </div>
  );
};

/* ═══════════════════════════════════════════════════════
   MAIN COMPONENT
═══════════════════════════════════════════════════════ */
const AirlyTile: React.FC = () => {
  const [data, setData] = useState<AirQualityData | null>(null);
  const [apiHistory, setApiHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [usingMock, setUsingMock] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [cr, hr] = await Promise.all([
        fetch(`${API_URL}/weather/air-quality/current`),
        fetch(`${API_URL}/weather/air-quality/history?days=3`),
      ]);
      let gotReal = false;
      if (cr.ok) { setData(await cr.json()); gotReal = true; }
      if (hr.ok) {
        const raw: HistoryItem[] = await hr.json();
        if (Array.isArray(raw) && raw.length > 0) { setApiHistory(raw); }
      }
      if (!gotReal) { setData(MOCK_AIR); setUsingMock(true); }
    } catch {
      setData(MOCK_AIR);
      setUsingMock(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); const id = setInterval(fetchData, 30 * 60 * 1000); return () => clearInterval(id); }, [fetchData]);

  /* Use API history if available; otherwise build convincing mock */
  const history = useMemo<HistoryItem[]>(() => {
    if (apiHistory.length > 2) {
      const step = Math.max(1, Math.floor(apiHistory.length / 18));
      const s: HistoryItem[] = [];
      for (let i = 0; i < apiHistory.length; i += step) { s.push(apiHistory[i]); if (s.length >= 18) break; }
      return s;
    }
    return buildMockHistory();
  }, [apiHistory]);

  const d = data ?? MOCK_AIR;
  const lvl = getLvl(d.caqi_level);

  const chartData = useMemo(() =>
    history.map(h => ({ t: fmtDate(h.fetched_at), v: Math.round(h.caqi), pm25: +h.pm25.toFixed(1) })),
    [history]
  );

  if (loading) {
    return (
      <div className="h-full flex flex-col p-4 gap-3">
        {[1, 2, 3].map(i => <div key={i} className="flex-1 rounded-2xl animate-pulse" style={{ background: 'rgba(255,255,255,0.04)' }} />)}
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col p-4 gap-3 overflow-y-auto no-scrollbar relative">

      {/* Ambient glow blobs */}
      <div className="absolute top-[-30px] right-[-30px] w-40 h-40 rounded-full pointer-events-none"
        style={{ background: lvl.color, filter: 'blur(80px)', opacity: 0.12 }} />
      <div className="absolute bottom-[-20px] left-[-20px] w-32 h-32 rounded-full pointer-events-none"
        style={{ background: '#3a81f6', filter: 'blur(70px)', opacity: 0.08 }} />

      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-4 rounded-full" style={{ background: `linear-gradient(to bottom, ${lvl.color}, transparent)` }} />
          <span className="text-[9px] font-bold text-neutral-500 uppercase tracking-widest">Jakość Powietrza · Rybno</span>
        </div>
        {usingMock && (
          <span className="text-[8px] px-2 py-0.5 rounded-full text-neutral-600"
            style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)' }}>
            Demo
          </span>
        )}
      </div>

      {/* ── Main: Gauge + level info ────────────────────────────── */}
      <GCard className="p-4 flex gap-4 items-center">
        <DonutGauge value={d.caqi} maxValue={100} color={lvl.color} label="CAQI" sublabel={lvl.label} />

        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-2xl">{lvl.emoji}</span>
            <div>
              <p className="text-base font-black text-white leading-tight">{lvl.label}</p>
              <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full mt-0.5"
                style={{ background: lvl.bg, border: `1px solid ${lvl.color}22` }}>
                <div className="w-1 h-1 rounded-full" style={{ background: lvl.color }} />
                <span className="text-[9px] font-bold uppercase tracking-widest" style={{ color: lvl.color }}>
                  CAQI {Math.round(d.caqi)}
                </span>
              </div>
            </div>
          </div>
          <p className="text-[10px] text-neutral-500 leading-relaxed">{lvl.advice}</p>

          {/* Quick stats */}
          <div className="flex gap-3 mt-3">
            {[
              { label: 'Temp', val: `${d.temperature?.toFixed(1)}°C`, icon: '🌡️' },
              { label: 'Ciśnienie', val: `${d.pressure?.toFixed(0)} hPa`, icon: '⏲️' },
            ].map(s => (
              <div key={s.label}>
                <p className="text-[8px] text-neutral-600 uppercase font-bold">{s.icon} {s.label}</p>
                <p className="text-xs font-black text-neutral-300">{s.val}</p>
              </div>
            ))}
          </div>
        </div>
      </GCard>

      {/* ── PM particulate bars ─────────────────────────────────── */}
      <GCard className="px-4 py-3 flex flex-col gap-3">
        <p className="text-[9px] font-bold text-neutral-500 uppercase tracking-widest">Pyły zawieszone</p>
        <PMBar label="PM 2.5" value={d.pm25} norm={25} color={lvl.color} />
        <PMBar label="PM 10"  value={d.pm10} norm={50} color="#60a5fa" />
      </GCard>

      {/* ── CAQI history area chart ─────────────────────────────── */}
      <GCard className="px-4 pt-3 pb-2 flex flex-col gap-1 flex-1">
        <div className="flex items-center justify-between mb-1">
          <p className="text-[9px] font-bold text-neutral-500 uppercase tracking-widest">Historia CAQI · 3 dni</p>
          <span className="text-[8px] text-neutral-700">{usingMock ? 'dane przykładowe' : 'dane z czujnika'}</span>
        </div>
        <div className="flex-1" style={{ minHeight: 80 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="caqiAreaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={lvl.color} stopOpacity={0.55} />
                  <stop offset="100%" stopColor={lvl.color} stopOpacity={0} />
                </linearGradient>
                <linearGradient id="pm25AreaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#60a5fa" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#60a5fa" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="t" tick={{ fill: '#374151', fontSize: 7 }} axisLine={false} tickLine={false}
                interval={Math.floor(chartData.length / 4)} />
              <Tooltip content={<CTip />} />
              <Area type="monotone" dataKey="v" name="CAQI"
                stroke={lvl.color} strokeWidth={2} fill="url(#caqiAreaGrad)"
                dot={false} activeDot={{ r: 3, fill: lvl.color }} />
              <Area type="monotone" dataKey="pm25" name="PM2.5"
                stroke="#60a5fa" strokeWidth={1} fill="url(#pm25AreaGrad)"
                dot={false} strokeDasharray="4 2" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="flex items-center gap-4 mt-0.5">
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-[2px] rounded-full" style={{ background: lvl.color }} />
            <span className="text-[7px] text-neutral-700">CAQI</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-px rounded-full" style={{ background: '#60a5fa', borderStyle: 'dashed' }} />
            <span className="text-[7px] text-neutral-700">PM 2.5</span>
          </div>
        </div>
      </GCard>

      {/* ── PM bar chart (hourly) ───────────────────────────────── */}
      <GCard className="px-4 pt-3 pb-2">
        <p className="text-[9px] font-bold text-neutral-500 uppercase tracking-widest mb-2">PM 2.5 · 72h bar</p>
        <div style={{ height: 60 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
              <XAxis dataKey="t" tick={{ fill: '#374151', fontSize: 7 }} axisLine={false} tickLine={false}
                interval={Math.floor(chartData.length / 4)} />
              <Tooltip content={<CTip />} />
              <defs>
                <linearGradient id="pm25BarGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={lvl.color} stopOpacity={0.9} />
                  <stop offset="100%" stopColor={lvl.color} stopOpacity={0.3} />
                </linearGradient>
              </defs>
              <Bar dataKey="pm25" fill="url(#pm25BarGrad)" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </GCard>

    </div>
  );
};

export default AirlyTile;
