import React, { useEffect, useRef, useState } from 'react';
import { Share2, Download, Newspaper, CalendarDays, AlertTriangle, Thermometer, Wind } from 'lucide-react';
import html2canvas from 'html2canvas';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

interface WeeklyStats {
  period: string;
  articles_count: number;
  top_categories: { category: string; count: number }[];
  reports_count: number;
  events_count: number;
  weather: { temp_avg: number | null; temp_min: number | null; temp_max: number | null };
  air_quality: { caqi_avg: number | null; pm25_avg: number | null };
}

const CAQI_LABEL = (caqi: number) => {
  if (caqi <= 25) return { text: 'Bardzo dobra', color: '#34d399' };
  if (caqi <= 50) return { text: 'Dobra',        color: '#4ade80' };
  if (caqi <= 75) return { text: 'Umiarkowana',  color: '#facc15' };
  if (caqi <= 100) return { text: 'Zła',         color: '#fb923c' };
  return              { text: 'Bardzo zła',      color: '#f87171' };
};

export const ShareCard: React.FC = () => {
  const [stats, setStats] = useState<WeeklyStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/stats/weekly-summary`)
      .then(r => r.json())
      .then(data => { setStats(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const handleDownload = async () => {
    if (!cardRef.current || !stats) return;
    setDownloading(true);
    try {
      const canvas = await html2canvas(cardRef.current, {
        backgroundColor: '#0d1117',
        scale: 2,
        useCORS: true,
        logging: false,
      });
      const link = document.createElement('a');
      link.download = `gmina-rybno-${stats.period.replace(/\s/g, '')}.png`;
      link.href = canvas.toDataURL('image/png');
      link.click();
    } finally {
      setDownloading(false);
    }
  };

  const handleShare = async () => {
    if (!stats) return;
    const text =
      `📊 Gmina Rybno w liczbach (${stats.period}):\n` +
      `📰 ${stats.articles_count} artykułów\n` +
      `📅 ${stats.events_count} wydarzeń\n` +
      `🚨 ${stats.reports_count} zgłoszeń\n` +
      `🌡️ Temperatura śr. ${stats.weather.temp_avg ?? '—'}°C\n` +
      `🔗 https://rybno.pl`;

    if (navigator.share) {
      await navigator.share({ title: 'Gmina w Liczbach — Rybno', text }).catch(() => {});
    } else {
      await navigator.clipboard.writeText(text).catch(() => {});
    }
  };

  if (loading) {
    return (
      <div className="rounded-2xl bg-slate-900/60 border border-slate-700/40 p-6 flex items-center justify-center h-48">
        <div className="w-6 h-6 rounded-full border-2 border-blue-500/30 border-t-blue-500 animate-spin" />
      </div>
    );
  }
  if (!stats) return null;

  const air = stats.air_quality.caqi_avg != null ? CAQI_LABEL(stats.air_quality.caqi_avg) : null;

  return (
    <div className="rounded-2xl overflow-hidden border border-slate-700/40">
      {/* ── Capturable card area ──────────────────────────────── */}
      <div
        ref={cardRef}
        style={{ background: 'linear-gradient(135deg,#0d1117 0%,#0f172a 100%)' }}
        className="p-5"
      >
        {/* Header */}
        <div className="flex items-start justify-between mb-5">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-blue-400 mb-0.5">
              Centrum Operacyjne Rybna
            </p>
            <p className="text-base font-bold text-white">Gmina w Liczbach</p>
            <p className="text-xs text-neutral-500 mt-0.5">{stats.period}</p>
          </div>
          <div className="w-8 h-8 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center">
            <span className="text-base">📊</span>
          </div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-2 mb-4">
          <StatBox value={stats.articles_count} label="artykułów" accent="#60a5fa" />
          <StatBox value={stats.events_count}   label="wydarzeń"  accent="#a78bfa" />
          <StatBox value={stats.reports_count}  label="zgłoszeń"  accent="#fbbf24" />
        </div>

        {/* Weather + Air */}
        <div className="grid grid-cols-2 gap-2 mb-4">
          <div style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)' }} className="rounded-xl px-3 py-2.5">
            <p className="text-[10px] text-neutral-500 mb-1 flex items-center gap-1">
              <Thermometer size={10} className="text-orange-400" /> Temperatura śr.
            </p>
            <p className="text-sm font-bold text-white">
              {stats.weather.temp_avg != null ? `${stats.weather.temp_avg}°C` : '—'}
            </p>
            {stats.weather.temp_min != null && stats.weather.temp_max != null && (
              <p className="text-[10px] text-neutral-600 mt-0.5">
                min {stats.weather.temp_min}° / max {stats.weather.temp_max}°
              </p>
            )}
          </div>
          <div style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)' }} className="rounded-xl px-3 py-2.5">
            <p className="text-[10px] text-neutral-500 mb-1 flex items-center gap-1">
              <Wind size={10} className="text-emerald-400" /> Jakość powietrza
            </p>
            {air ? (
              <p className="text-sm font-bold" style={{ color: air.color }}>{air.text}</p>
            ) : (
              <p className="text-sm text-neutral-600">—</p>
            )}
            {stats.air_quality.pm25_avg != null && (
              <p className="text-[10px] text-neutral-600 mt-0.5">PM2.5 śr. {stats.air_quality.pm25_avg} µg/m³</p>
            )}
          </div>
        </div>

        {/* Top categories */}
        {stats.top_categories.length > 0 && (
          <div>
            <p className="text-[10px] text-neutral-600 uppercase tracking-wider mb-2">Top kategorie</p>
            <div className="flex flex-wrap gap-1.5">
              {stats.top_categories.map((c, i) => (
                <span
                  key={i}
                  style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)' }}
                  className="text-[11px] font-semibold px-2.5 py-1 rounded-full text-neutral-300"
                >
                  {c.category} <span className="text-neutral-500">{c.count}</span>
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Footer brand */}
        <p className="text-[10px] text-neutral-700 mt-4 text-right">rybno.pl</p>
      </div>

      {/* ── Action buttons (outside captured area) ───────────── */}
      <div className="flex gap-2 px-5 py-3 bg-slate-900/80 border-t border-slate-700/40">
        <button
          onClick={handleDownload}
          disabled={downloading}
          className="flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-xl bg-slate-800 text-neutral-300 hover:bg-slate-700 transition-colors disabled:opacity-50"
        >
          <Download size={13} />
          {downloading ? 'Generowanie...' : 'Pobierz PNG'}
        </button>
        <button
          onClick={handleShare}
          className="flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-xl bg-blue-500/15 text-blue-400 hover:bg-blue-500/25 transition-colors"
        >
          <Share2 size={13} />
          Udostępnij
        </button>
      </div>
    </div>
  );
};

const StatBox: React.FC<{ value: number; label: string; accent: string }> = ({ value, label, accent }) => (
  <div
    style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)' }}
    className="rounded-xl px-3 py-3 text-center"
  >
    <p className="text-2xl font-black leading-none" style={{ color: accent }}>{value}</p>
    <p className="text-[10px] text-neutral-500 mt-1">{label}</p>
  </div>
);

export default ShareCard;
