
import React from 'react';
import { RoadStatus, TrafficCondition } from '../types';

interface TrafficItemProps {
    road: RoadStatus;
    isLast?: boolean;
}

const TrafficItem: React.FC<TrafficItemProps> = ({ road, isLast }) => {
    const getStatusColor = (status: TrafficCondition) => {
        switch (status) {
            case TrafficCondition.FLUID: return 'text-emerald-400';
            case TrafficCondition.DIFFICULTIES: return 'text-orange-400';
            case TrafficCondition.JAM: return 'text-rose-400';
            default: return 'text-neutral-400';
        }
    };

    const getStatusIndicator = (status: TrafficCondition) => {
        switch (status) {
            case TrafficCondition.FLUID: return 'bg-emerald-500';
            case TrafficCondition.DIFFICULTIES: return 'bg-orange-500';
            case TrafficCondition.JAM: return 'bg-rose-500';
            default: return 'bg-slate-500';
        }
    };

    return (
        <div className={`py-2 ${!isLast ? 'border-b border-gray-800/50/40' : ''}`}>
            <div className="flex flex-col gap-2">
                {/* Header: Route and Time */}
                <div className="flex justify-between items-start">
                    <div className="flex items-center gap-3">
                        <div className={`w-1.5 h-10 rounded-full ${getStatusIndicator(road.status)} shadow-[0_0_12px_rgba(0,0,0,0.2)]`}></div>
                        <div>
                            <h3 className="text-white font-bold text-base tracking-tight">{road.name}</h3>
                            <div className="flex items-center gap-2 mt-0.5">
                                <span className={`text-[10px] font-black uppercase tracking-wider ${getStatusColor(road.status)}`}>
                                    {road.status}
                                </span>
                                {road.delayMinutes > 0 && (
                                    <span className="text-[10px] text-rose-400/80 font-bold bg-rose-500/5 px-2 rounded-md border border-rose-500/10">
                                        +{road.delayMinutes}m opóźnienia
                                    </span>
                                )}
                            </div>
                        </div>
                    </div>

                    <div className="text-right">
                        <div className="text-xl font-black text-white leading-none">{road.travelTime}</div>
                        <div className="text-[10px] text-neutral-500 font-bold uppercase mt-1 tracking-widest">Aktualny czas</div>
                    </div>
                </div>

                {/* Detailed Description */}
                {road.description && (
                    <div className="bg-[#1e293b]/30 rounded-2xl p-4 border border-white/[0.03] backdrop-blur-sm">
                        <p className="text-neutral-300 text-xs leading-relaxed">
                            <span className="text-blue-400/80 mr-1">●</span> {road.description}
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default TrafficItem;
