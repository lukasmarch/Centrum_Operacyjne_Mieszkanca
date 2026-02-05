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
    if (lower.includes('zmieszane')) return 'bg-gray-100 text-gray-700 border-gray-200';
    if (lower.includes('bio')) return 'bg-amber-100 text-amber-800 border-amber-200'; // Bio is often brown/green
    if (lower.includes('metale')) return 'bg-yellow-100 text-yellow-800 border-yellow-200';
    if (lower.includes('papier')) return 'bg-blue-100 text-blue-800 border-blue-200';
    if (lower.includes('szkło')) return 'bg-green-100 text-green-800 border-green-200';
    if (lower.includes('popiół')) return 'bg-slate-200 text-slate-600 border-slate-300';
    return 'bg-purple-100 text-purple-800 border-purple-200';
};

const WasteWidget: React.FC<WasteWidgetProps> = ({ events, town }) => {
    // Take top 4 events to show in the widget
    const upcomingEvents = events.slice(0, 4);

    return (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="p-5 border-b border-gray-100 flex justify-between items-center bg-gradient-to-r from-emerald-50 to-white">
                <div>
                    <h2 className="font-bold text-gray-900 text-lg flex items-center gap-2">
                        <Truck className="text-emerald-600" size={22} />
                        Harmonogram Odbioru
                    </h2>
                    <p className="text-sm text-gray-500 mt-1">
                        Najbliższe wywozy dla miejscowości: <span className="font-semibold text-gray-800">{town}</span>
                    </p>
                </div>
                <button className="text-xs font-medium text-emerald-600 hover:text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded-full border border-emerald-100 transition-colors">
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
                                <div key={idx} className={`relative rounded-lg p-3 border ${style} flex items-center justify-between transition-transform hover:-translate-y-1 duration-200`}>
                                    <div className="flex items-center gap-3 flex-1 min-w-0">
                                        <div className="opacity-70 flex-shrink-0">
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
                    <div className="text-center py-8 text-gray-400">
                        <p>Brak zaplanowanych odbiorów w najbliższym czasie.</p>
                    </div>
                )}
            </div>

            <div className="bg-gray-50 px-5 py-3 text-xs text-gray-500 flex justify-between items-center">
                <span>Dane na rok 2026</span>
                <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-green-500"></span>
                    Aktualne
                </span>
            </div>
        </div>
    );
};

export default WasteWidget;
