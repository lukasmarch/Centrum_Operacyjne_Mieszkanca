import React, { useState, useMemo } from 'react';
import { Trash2, Leaf, Container, FileText, Wine, Truck, Monitor, X, ChevronRight } from 'lucide-react';
import { WasteEvent } from '../types';
import { wasteData } from '../src/data/wasteSchedule';

interface WasteWidgetProps {
    events: WasteEvent[];
    town: string;
}

const getWasteIcon = (type: string) => {
    const lower = type.toLowerCase();
    if (lower.includes('zmieszane')) return <Trash2 size={20} />;
    if (lower.includes('bio')) return <Leaf size={20} />;
    if (lower.includes('metale')) return <Container size={20} />;
    if (lower.includes('papier')) return <FileText size={20} />;
    if (lower.includes('szkło')) return <Wine size={20} />;
    if (lower.includes('wielkogabarytowe')) return <Truck size={20} />;
    if (lower.includes('elektroniczny')) return <Monitor size={20} />;
    return <Trash2 size={20} />;
};

const getWasteStyles = (type: string) => {
    const lower = type.toLowerCase();
    if (lower.includes('zmieszane')) return 'bg-slate-700/30 text-neutral-300 border-slate-600/30';
    if (lower.includes('bio')) return 'bg-amber-500/10 text-amber-300 border-amber-500/20';
    if (lower.includes('metale')) return 'bg-yellow-500/10 text-yellow-300 border-yellow-500/20';
    if (lower.includes('papier')) return 'bg-blue-500/10 text-blue-300 border-blue-500/20';
    if (lower.includes('szkło')) return 'bg-green-500/10 text-green-300 border-green-500/20';
    if (lower.includes('popiół')) return 'bg-slate-500/20 text-neutral-400 border-slate-500/20';
    return 'bg-purple-500/10 text-purple-300 border-purple-500/20';
};

const getModalDotColor = (type: string) => {
    const lower = type.toLowerCase();
    if (lower.includes('zmieszane')) return 'bg-neutral-400';
    if (lower.includes('bio')) return 'bg-amber-400';
    if (lower.includes('metale')) return 'bg-yellow-400';
    if (lower.includes('papier')) return 'bg-blue-400';
    if (lower.includes('szkło')) return 'bg-green-400';
    if (lower.includes('popiół')) return 'bg-slate-400';
    return 'bg-purple-400';
};

const MONTHS_PL = ['Styczeń','Luty','Marzec','Kwiecień','Maj','Czerwiec','Lipiec','Sierpień','Wrzesień','Październik','Listopad','Grudzień'];

const WasteWidget: React.FC<WasteWidgetProps> = ({ events, town }) => {
    const [modalOpen, setModalOpen] = useState(false);
    const upcomingEvents = events.slice(0, 4);

    // Map town name the same way as useWasteSchedule does
    const mappedTown = town === 'Rybno' ? 'Rybno R1' : town;

    // Build full schedule grouped by month from raw wasteData
    const fullSchedule = useMemo(() => {
        const schedule = wasteData[mappedTown];
        if (!schedule) return [];

        const today = new Date();
        today.setHours(0, 0, 0, 0);

        // month key -> list of { date, type, isPast }
        const byMonth: Record<string, { date: Date; dateStr: string; type: string; isPast: boolean }[]> = {};

        Object.entries(schedule).forEach(([wasteType, datesString]) => {
            if (!datesString || datesString === 'Brak odbioru') return;
            datesString.split(', ').forEach(dateStr => {
                const [day, month, year] = dateStr.split('.');
                const d = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
                const key = `${year}-${month}`;
                if (!byMonth[key]) byMonth[key] = [];
                byMonth[key].push({ date: d, dateStr, type: wasteType, isPast: d < today });
            });
        });

        // Sort entries by month key, then sort dates within each month
        return Object.entries(byMonth)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([key, items]) => {
                const [y, m] = key.split('-');
                items.sort((a, b) => a.date.getTime() - b.date.getTime());
                return { label: `${MONTHS_PL[parseInt(m) - 1]} ${y}`, items };
            });
    }, [mappedTown]);

    return (
        <>
        <div className="overflow-hidden flex flex-col h-full">
            <div className="p-5 border-b border-white/10 flex justify-between items-center bg-white/5 backdrop-blur-md">
                <div>
                    <h2 className="font-bold text-neutral-100 text-lg flex items-center gap-2">
                        <Truck style={{ color: 'var(--chart-3)' }} size={22} />
                        Harmonogram Odbioru
                    </h2>
                    <p className="text-sm text-neutral-400 mt-1">
                        Najbliższe wywozy dla miejscowości: <span className="font-semibold text-neutral-200">{mappedTown}</span>
                    </p>
                </div>
                <button
                    onClick={() => setModalOpen(true)}
                    className="text-xs font-medium text-emerald-400 hover:text-emerald-300 bg-emerald-500/10 px-3 py-1.5 rounded-full border border-emerald-500/20 transition-colors flex items-center gap-1"
                >
                    Pełny harmonogram
                    <ChevronRight size={12} />
                </button>
            </div>

            <div className="p-5">
                {upcomingEvents.length > 0 ? (
                    <div className="grid grid-cols-1 gap-4">
                        {upcomingEvents.map((event, idx) => {
                            const style = getWasteStyles(event.type);
                            const isTomorrow = event.daysRemaining === 1;
                            const isToday = event.daysRemaining === 0;

                            return (
                                <div key={idx} className={`relative rounded-lg p-3 border ${style} flex items-center justify-between transition-transform hover:-translate-y-1 duration-200 hover:bg-white/5`}>
                                    <div className="flex items-center gap-3 flex-1 min-w-0">
                                        <div className="opacity-80 flex-shrink-0">
                                            {getWasteIcon(event.type)}
                                        </div>
                                        <div className="font-semibold text-sm leading-tight min-w-0 flex-1">
                                            {event.type}
                                        </div>
                                    </div>

                                    <div className="text-right flex-shrink-0 ml-3">
                                        <div className="text-xl font-bold tracking-tight">
                                            {event.originalDateString.slice(0, 5)}
                                        </div>
                                        <div className="text-[10px] font-medium uppercase tracking-wider opacity-80 mt-0.5 whitespace-nowrap">
                                            {isToday ? 'DZISIAJ' : isTomorrow ? 'JUTRO' : `za ${event.daysRemaining} dni`}
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                ) : (
                    <div className="text-center py-8 text-neutral-500">
                        <p>Brak zaplanowanych odbiorów w najbliższym czasie.</p>
                    </div>
                )}
            </div>

            <div className="bg-white/5 px-5 py-3 text-xs text-neutral-500 flex justify-between items-center border-t border-white/5">
                <span>Dane na rok 2026</span>
                <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                    Aktualne
                </span>
            </div>
        </div>

        {/* Full schedule modal */}
        {modalOpen && (
            <div
                className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
                onClick={() => setModalOpen(false)}
            >
                {/* Backdrop */}
                <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />

                {/* Panel */}
                <div
                    className="relative w-full sm:max-w-lg bg-[#0f1117] border border-white/10 rounded-t-3xl sm:rounded-2xl shadow-2xl flex flex-col max-h-[85vh] sm:max-h-[80vh]"
                    onClick={e => e.stopPropagation()}
                >
                    {/* Header */}
                    <div className="flex items-center justify-between px-5 pt-5 pb-4 border-b border-white/8 shrink-0">
                        <div>
                            <h3 className="font-bold text-white text-base flex items-center gap-2">
                                <Truck size={16} className="text-emerald-400" />
                                Pełny harmonogram 2026
                            </h3>
                            <p className="text-xs text-neutral-500 mt-0.5">
                                Miejscowość: <span className="text-emerald-400 font-semibold">{mappedTown}</span>
                            </p>
                        </div>
                        <button
                            onClick={() => setModalOpen(false)}
                            className="w-8 h-8 flex items-center justify-center rounded-full bg-white/5 hover:bg-white/10 text-neutral-400 hover:text-white transition-colors"
                        >
                            <X size={16} />
                        </button>
                    </div>

                    {/* Content — scrollable */}
                    <div className="overflow-y-auto flex-1 px-5 py-4 space-y-6">
                        {fullSchedule.length === 0 && (
                            <p className="text-neutral-500 text-sm text-center py-8">Brak danych dla tej miejscowości.</p>
                        )}
                        {fullSchedule.map(({ label, items }) => (
                            <div key={label}>
                                <p className="text-[10px] font-bold uppercase tracking-widest text-neutral-500 mb-2">{label}</p>
                                <div className="space-y-1.5">
                                    {items.map((item, i) => (
                                        <div
                                            key={i}
                                            className={`flex items-center gap-3 px-3 py-2 rounded-xl border transition-colors ${
                                                item.isPast
                                                    ? 'border-white/4 bg-white/[0.02] opacity-40'
                                                    : 'border-white/6 bg-white/[0.04] hover:bg-white/[0.06]'
                                            }`}
                                        >
                                            <span className={`w-2 h-2 rounded-full shrink-0 ${getModalDotColor(item.type)}`} />
                                            <span className="text-[11px] font-mono text-neutral-400 shrink-0 w-14">
                                                {item.dateStr.slice(0, 5)}
                                            </span>
                                            <span className={`text-xs font-medium truncate ${item.isPast ? 'text-neutral-500' : 'text-neutral-200'}`}>
                                                {item.type}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Footer */}
                    <div className="px-5 py-3 border-t border-white/8 shrink-0">
                        <p className="text-[10px] text-neutral-600 text-center">
                            Pozycje wyszarzone = daty już minione
                        </p>
                    </div>
                </div>
            </div>
        )}
        </>
    );
};

export default WasteWidget;
