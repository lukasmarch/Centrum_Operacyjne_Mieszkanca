
import { ActiveBus, Direction, DirectionStatus, TimetableEntry } from '../../types';
import { STOPS, TIMETABLE_RYB_DZA, TIMETABLE_DZA_RYB } from '../../constants';

function parseTime(timeStr: string, baseDate: Date): Date {
    const [h, m] = timeStr.split(':').map(Number);
    const d = new Date(baseDate);
    d.setHours(h, m, 0, 0);
    return d;
}

export function getDirectionStatus(direction: Direction, now: Date): DirectionStatus {
    const timetable = direction === 'RYBNO_DZIALDOWO' ? TIMETABLE_RYB_DZA : TIMETABLE_DZA_RYB;

    // 1. Check if any trip is currently active
    for (const entry of timetable) {
        const stopIds = Object.keys(entry.stops);
        const start = parseTime(entry.stops[stopIds[0]], now);
        const end = parseTime(entry.stops[stopIds[stopIds.length - 1]], now);

        if (now >= start && now <= end) {
            for (let i = 0; i < stopIds.length - 1; i++) {
                const s1Id = stopIds[i];
                const s2Id = stopIds[i + 1];
                const t1 = parseTime(entry.stops[s1Id], now);
                const t2 = parseTime(entry.stops[s2Id], now);

                if (now >= t1 && now <= t2) {
                    const totalDuration = t2.getTime() - t1.getTime();
                    const elapsed = now.getTime() - t1.getTime();
                    const progress = totalDuration > 0 ? elapsed / totalDuration : 1;
                    const timeLeft = Math.ceil((t2.getTime() - now.getTime()) / (1000 * 60));

                    return {
                        direction,
                        isActive: true,
                        activeBus: {
                            direction,
                            currentStopId: s1Id,
                            nextStopId: s2Id,
                            progress,
                            timeLeftMinutes: timeLeft,
                            lastUpdate: now
                        }
                    };
                }
            }
        }
    }

    // 2. If not active, find the next departure for this direction
    let nextDep: DirectionStatus['nextDeparture'] = undefined;
    let minDiff = Infinity;

    for (const entry of timetable) {
        const stopIds = Object.keys(entry.stops);
        const startTimeStr = entry.stops[stopIds[0]];
        const start = parseTime(startTimeStr, now);
        const diff = start.getTime() - now.getTime();

        // Looking for the earliest departure in the future
        if (diff > 0 && diff < minDiff) {
            minDiff = diff;
            nextDep = {
                time: startTimeStr,
                inMinutes: Math.ceil(diff / (1000 * 60)),
                from: STOPS.find(s => s.id === stopIds[0])?.name || ''
            };
        }
    }

    // If no future trips today, maybe look at the first trip of "tomorrow" (conceptually) or just return null
    return {
        direction,
        isActive: false,
        nextDeparture: nextDep
    };
}

export function getCoordinatesForBus(bus: ActiveBus) {
    const stop1 = STOPS.find(s => s.id === bus.currentStopId);
    const stop2 = STOPS.find(s => s.id === bus.nextStopId);
    if (!stop1 || !stop2) return null;

    // Linear interpolation between stops
    return {
        lat: stop1.lat + (stop2.lat - stop1.lat) * bus.progress,
        lng: stop1.lng + (stop2.lng - stop1.lng) * bus.progress
    };
}
