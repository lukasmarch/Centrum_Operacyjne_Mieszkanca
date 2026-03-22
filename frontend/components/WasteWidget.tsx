import React from 'react';
import { Trash2, Leaf, Container, FileText, Wine, Truck, Monitor } from 'lucide-react';
import { WasteEvent } from '../types';

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

const WasteWidget: React.FC<WasteWidgetProps> = ({ events, town }) => {
    // Take top 4 events to show in the widget
    const upcomingEvents = events.slice(0, 4);

    return (
        <div className="glass-panel rounded-3xl border border-white/10 overflow-hidden">
            <div className="p-5 border-b border-white/10 flex justify-between items-center bg-white/5 backdrop-blur-md">
                <div>
                    <h2 className="font-bold text-neutral-100 text-lg flex items-center gap-2">
                        <Truck className="text-emerald-400" size={22} />
                        Harmonogram Odbioru
                    </h2>
                    <p className="text-sm text-neutral-400 mt-1">
                        Najbliższe wywozy dla miejscowości: <span className="font-semibold text-neutral-200">{town}</span>
                    </p>
                </div>
                <button className="text-xs font-medium text-emerald-400 hover:text-emerald-300 bg-emerald-500/10 px-3 py-1.5 rounded-full border border-emerald-500/20 transition-colors">
                    Pełny harmonogram
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
    );
};

export default WasteWidget;
