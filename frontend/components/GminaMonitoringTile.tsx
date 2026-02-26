import React, { useState, useEffect, useCallback } from 'react';
import { Activity, MapPin, AlertTriangle, Clock } from 'lucide-react';
import { CATEGORY_CONFIG, STATUS_CONFIG } from '../src/services/reportsApi';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

interface Report {
    id: number;
    title: string;
    description: string;
    category: string;
    ai_severity: string;
    status: string;
    address: string;
    location_name: string;
    created_at: string;
    upvotes: number;
}

const GminaMonitoringTile: React.FC = () => {
    const [reports, setReports] = useState<Report[]>([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);

    const fetchReports = useCallback(async () => {
        try {
            const res = await fetch(`${API_URL}/reports?limit=3&sort=newest`);
            if (res.ok) {
                const data = await res.json();
                setReports(data.reports || []);
                setTotal(data.total || 0);
            }
        } catch {
            // silent
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchReports();
        const interval = setInterval(fetchReports, 5 * 60 * 1000);
        return () => clearInterval(interval);
    }, [fetchReports]);

    const formatTimeAgo = (dateStr: string) => {
        const diff = Date.now() - new Date(dateStr).getTime();
        const mins = Math.floor(diff / 60000);
        if (mins < 60) return `${mins} min temu`;
        const hrs = Math.floor(mins / 60);
        if (hrs < 24) return `${hrs}h temu`;
        const days = Math.floor(hrs / 24);
        return `${days}d temu`;
    };

    const getSeverityDot = (severity: string) => {
        switch (severity) {
            case 'critical': return 'bg-red-500';
            case 'high': return 'bg-orange-500';
            case 'medium': return 'bg-yellow-500';
            default: return 'bg-emerald-500';
        }
    };

    const getStatusBadge = (status: string) => {
        const config = STATUS_CONFIG[status];
        if (!config) return null;
        return (
            <span
                className="text-[8px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-md"
                style={{ color: config.color, backgroundColor: `${config.color}15`, border: `1px solid ${config.color}30` }}
            >
                {config.label}
            </span>
        );
    };

    const activeCount = reports.filter(r => r.status !== 'resolved' && r.status !== 'rejected').length;

    return (
        <div className="h-full flex flex-col p-5 relative overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <Activity size={14} className="text-blue-400" />
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Zgłoszenia24</span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-[9px] font-bold text-slate-500">{total} łącznie</span>
                    <div className={`w-2 h-2 rounded-full ${activeCount > 0 ? 'bg-amber-400 animate-pulse' : 'bg-emerald-400'}`} />
                </div>
            </div>

            {/* Reports list */}
            {loading ? (
                <div className="space-y-3 flex-1 animate-pulse">
                    {[1, 2, 3].map(i => (
                        <div key={i} className="h-14 bg-slate-800/50 rounded-xl" />
                    ))}
                </div>
            ) : reports.length > 0 ? (
                <div className="space-y-2 flex-1">
                    {reports.map(report => {
                        const catConfig = CATEGORY_CONFIG[report.category];
                        return (
                            <div key={report.id} className="flex gap-3 items-start p-2.5 rounded-xl bg-slate-800/30 border border-white/5 hover:bg-slate-800/50 transition-colors cursor-default">
                                {/* Severity dot + category emoji */}
                                <div className="flex flex-col items-center gap-1 pt-0.5 shrink-0">
                                    <div className={`w-2 h-2 rounded-full ${getSeverityDot(report.ai_severity)}`} />
                                    <span className="text-xs">{catConfig?.emoji || '📋'}</span>
                                </div>

                                {/* Content */}
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-0.5">
                                        <p className="text-[11px] font-semibold text-slate-200 truncate">{report.title}</p>
                                        {getStatusBadge(report.status)}
                                    </div>
                                    <div className="flex items-center gap-2 text-[9px] text-slate-500">
                                        {report.location_name && (
                                            <span className="flex items-center gap-0.5 truncate">
                                                <MapPin size={7} className="shrink-0" />
                                                {report.location_name}
                                            </span>
                                        )}
                                        <span className="flex items-center gap-0.5 shrink-0">
                                            <Clock size={7} />
                                            {formatTimeAgo(report.created_at)}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            ) : (
                <p className="text-xs text-slate-500 italic flex-1 flex items-center">Brak aktywnych zgłoszeń</p>
            )}

            {/* Footer */}
            <div className="flex items-center justify-between pt-2 mt-auto border-t border-white/5">
                <div className="flex items-center gap-1.5">
                    <AlertTriangle size={10} className="text-amber-400" />
                    <span className="text-[9px] font-bold text-slate-500">
                        {activeCount} aktywn{activeCount === 1 ? 'e' : 'ych'}
                    </span>
                </div>
                <span className="text-[9px] text-blue-400 font-semibold cursor-pointer hover:text-blue-300 transition-colors">
                    Zobacz wszystkie →
                </span>
            </div>
        </div>
    );
};

export default GminaMonitoringTile;
