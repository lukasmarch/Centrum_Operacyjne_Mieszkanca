
import React, { useState, useEffect } from 'react';
import { getDirectionStatus } from '../src/services/busLogic';
import { DirectionStatus, ActiveBus } from '../types';
import BusMap from './BusMap';
import { STOPS, TIMETABLE_RYB_DZA, TIMETABLE_DZA_RYB } from '../constants';

const RouteTimeline: React.FC<{ activeBus: ActiveBus }> = ({ activeBus }) => {
    const timetable = activeBus.direction === 'RYBNO_DZIALDOWO' ? TIMETABLE_RYB_DZA : TIMETABLE_DZA_RYB;

    const now = activeBus.lastUpdate;
    const currentTrip = timetable.find(entry => {
        const stopIds = Object.keys(entry.stops);
        const start = new Date(now);
        const [sh, sm] = entry.stops[stopIds[0]].split(':').map(Number);
        start.setHours(sh, sm, 0, 0);
        const end = new Date(now);
        const [eh, em] = entry.stops[stopIds[stopIds.length - 1]].split(':').map(Number);
        end.setHours(eh, em, 0, 0);
        return now >= start && now <= end;
    });

    if (!currentTrip) return null;

    const stopIds = Object.keys(currentTrip.stops);
    const currentIndex = stopIds.indexOf(activeBus.currentStopId);

    return (
        <div className="mt-2 pt-4 border-t border-slate-100">
            <div className="flex justify-between items-center mb-3">
                <h4 className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">Trasa i Postęp</h4>
                <div className="flex items-center gap-1 bg-blue-50 px-2 py-0.5 rounded-full border border-blue-100">
                    <div className="w-1 h-1 rounded-full bg-blue-600 animate-pulse" />
                    <span className="text-[8px] font-bold text-blue-600 uppercase">Live</span>
                </div>
            </div>

            <div className="relative flex justify-between items-center px-4 mb-6 h-6">
                {/* Track Background */}
                <div className="absolute left-6 right-6 h-[4px] bg-slate-100 z-0 rounded-full" />

                {/* Progress Fill (Blue) */}
                <div
                    className="absolute left-6 h-[4px] bg-blue-600 z-1 rounded-full transition-all duration-1000 shadow-[0_0_8px_rgba(37,99,235,0.4)]"
                    style={{ width: `calc(${(currentIndex / (stopIds.length - 1)) * 100}% - 4px)` }}
                />

                {stopIds.map((id, index) => {
                    const stop = STOPS.find(s => s.id === id);
                    const isPassed = index < currentIndex;
                    const isCurrent = id === activeBus.currentStopId;
                    const isStart = index === 0;
                    const isEnd = index === stopIds.length - 1;

                    if (isStart || isEnd) {
                        return (
                            <div key={id} className="relative z-10 flex flex-col items-center">
                                <div
                                    className={`w-4 h-4 rounded-full border-[1.5px] transition-all duration-500 shadow-sm flex items-center justify-center ${isPassed || isCurrent || (isStart && index <= currentIndex)
                                            ? 'bg-blue-600 border-white'
                                            : 'bg-white border-blue-600'
                                        }`}
                                >
                                    <div className={`w-1 h-1 rounded-full ${isPassed || isCurrent || (isStart && index <= currentIndex) ? 'bg-white' : 'bg-blue-600'
                                        }`} />
                                </div>
                                <span className={`absolute -bottom-5 whitespace-nowrap text-[8px] font-bold uppercase tracking-tight ${isPassed || isCurrent || (isStart && index <= currentIndex) ? 'text-blue-700' : 'text-slate-400'
                                    }`}>
                                    {stop?.name.split(' ')[0]}
                                </span>
                            </div>
                        );
                    }

                    return (
                        <div key={id} className="relative z-10 flex flex-col items-center">
                            <div
                                className={`w-2 h-2 rounded-full border-[1.5px] transition-all duration-500 ${isPassed ? 'bg-blue-600 border-blue-600' :
                                        isCurrent ? 'bg-white border-blue-600 ring-2 ring-blue-100 scale-125 shadow-md' :
                                            'bg-white border-slate-200'
                                    }`}
                            />
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

const StatusCard: React.FC<{ status: DirectionStatus }> = ({ status }) => {
    const isRybDza = status.direction === 'RYBNO_DZIALDOWO';
    const bus = status.activeBus;
    const next = status.nextDeparture;

    return (
        <div className={`flex-1 p-4 rounded-2xl border transition-all duration-500 ${status.isActive ? 'bg-blue-50/40 border-blue-100 shadow-sm ring-1 ring-blue-50' : 'bg-slate-50 border-slate-100'
            }`}>
            <div className="flex justify-between items-start mb-3">
                <div className="flex flex-col gap-1">
                    <span className={`text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md w-fit ${isRybDza ? 'bg-indigo-100 text-indigo-700' : 'bg-blue-100 text-blue-700'
                        }`}>
                        {isRybDza ? '➔ DZIAŁDOWO' : '➔ RYBNO'}
                    </span>
                    <div className="flex items-center gap-1.5 mt-0.5">
                        <div className={`w-1.5 h-1.5 rounded-full ${status.isActive ? 'bg-blue-600 animate-pulse' : 'bg-slate-300'}`} />
                        <p className={`text-[10px] font-bold uppercase tracking-tight ${status.isActive ? 'text-blue-600' : 'text-slate-400'}`}>
                            {status.isActive ? 'W TRASIE' : 'OCZEKIWANIE'}
                        </p>
                    </div>
                </div>
                {status.isActive && (
                    <div className="bg-blue-600 text-white text-[11px] font-bold px-2 py-1 rounded-lg shadow-md shadow-blue-200 animate-bounce">
                        {bus?.timeLeftMinutes} min
                    </div>
                )}
            </div>

            {status.isActive && bus ? (
                <div className="mt-3">
                    <p className="text-[9px] font-bold text-slate-400 uppercase leading-none mb-1.5 tracking-wide">
                        Następny:
                    </p>
                    <p className="text-sm font-black text-blue-800 uppercase tracking-tight mb-2 truncate">
                        {STOPS.find(s => s.id === bus.nextStopId)?.name}
                    </p>
                    <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden shadow-inner relative">
                        <div
                            className="bg-blue-600 h-full rounded-full transition-all duration-1000 ease-in-out shadow-[0_0_10px_rgba(37,99,235,0.4)]"
                            style={{ width: `${bus.progress * 100}%` }}
                        />
                    </div>
                </div>
            ) : next ? (
                <div className="mt-3">
                    <p className="text-[9px] font-bold text-slate-400 uppercase tracking-wider">Następny:</p>
                    <div className="flex items-baseline gap-1.5 mt-1">
                        <span className="text-xl font-black text-slate-800 tabular-nums tracking-tighter">{next.time}</span>
                        <span className="text-[10px] font-bold text-slate-400 uppercase">za {next.inMinutes}m</span>
                    </div>
                </div>
            ) : (
                <div className="mt-4 flex items-center gap-2 text-slate-400">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    <p className="text-[10px] font-bold italic tracking-tight">Koniec kursów</p>
                </div>
            )}
        </div>
    );
};

const BusTrackerWidget: React.FC = () => {
    const [statuses, setStatuses] = useState<{ rybDza: DirectionStatus, dzaRyb: DirectionStatus } | null>(null);
    const [now, setNow] = useState(new Date());

    useEffect(() => {
        const update = () => {
            const d = new Date();
            setNow(d);
            setStatuses({
                rybDza: getDirectionStatus('RYBNO_DZIALDOWO', d),
                dzaRyb: getDirectionStatus('DZIALDOWO_RYBNO', d)
            });
        };
        update();
        // High frequency update for smooth tracking
        const interval = setInterval(update, 1000);
        return () => clearInterval(interval);
    }, []);

    if (!statuses) return (
        <div className="bg-white rounded-3xl shadow-sm p-8 flex items-center justify-center border border-slate-100 h-64">
            <div className="flex flex-col items-center gap-4">
                <div className="relative">
                    <div className="animate-spin rounded-full h-10 w-10 border-[3px] border-slate-100 border-b-blue-600"></div>
                    <div className="absolute inset-0 flex items-center justify-center">
                        <div className="w-1.5 h-1.5 bg-blue-600 rounded-full animate-pulse"></div>
                    </div>
                </div>
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest animate-pulse">Inicjalizacja...</p>
            </div>
        </div>
    );

    const activeBuses: ActiveBus[] = [];
    if (statuses.rybDza.isActive && statuses.rybDza.activeBus) activeBuses.push(statuses.rybDza.activeBus);
    if (statuses.dzaRyb.isActive && statuses.dzaRyb.activeBus) activeBuses.push(statuses.dzaRyb.activeBus);

    return (
        <div className="bg-white rounded-3xl shadow-sm p-5 flex flex-col gap-5 border border-slate-100 overflow-hidden w-full">
            <div className="flex justify-between items-start px-1">
                <div>
                    <div className="flex items-center gap-2.5 mb-1">
                        <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center shadow-md shadow-blue-100">
                            <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M18 11V7a2 2 0 00-2-2H8a2 2 0 00-2 2v4m12 0a2 2 0 012 2v3a2 2 0 01-2 2h-1a2 2 0 01-2-2v-1H7v1a2 2 0 01-2 2H4a2 2 0 01-2-2v-3a2 2 0 012-2m14 0H4M8 11h2m4 0h2" /></svg>
                        </div>
                        <h3 className="text-lg font-bold text-slate-900 leading-none">Monitoring</h3>
                    </div>
                    <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider ml-10 pl-0.5">Lokalizacja Live</p>
                </div>
                <div className="flex flex-col items-end pt-0.5">
                    <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg shadow-sm ${activeBuses.length > 0 ? 'bg-blue-600' : 'bg-slate-800'}`}>
                        <div className={`w-1.5 h-1.5 rounded-full ${activeBuses.length > 0 ? 'bg-white animate-pulse' : 'bg-blue-500'}`} />
                        <span className="text-[9px] font-bold text-white uppercase tracking-tight">
                            {activeBuses.length > 0 ? 'Aktywny' : 'Czuwanie'}
                        </span>
                    </div>
                    <span className="text-[10px] text-slate-300 mt-1.5 font-bold tabular-nums">{now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                </div>
            </div>

            <div className="px-1 overflow-visible">
                <BusMap activeBuses={activeBuses} />
            </div>

            <div className="flex flex-col sm:flex-row gap-3 px-1">
                <StatusCard status={statuses.rybDza} />
                <StatusCard status={statuses.dzaRyb} />
            </div>

            {activeBuses.length > 0 && (
                <div className="space-y-4 px-1">
                    {activeBuses.map((bus, idx) => (
                        <RouteTimeline key={idx} activeBus={bus} />
                    ))}
                </div>
            )}
        </div>
    );
};

export default BusTrackerWidget;
