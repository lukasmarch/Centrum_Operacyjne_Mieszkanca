import { useMemo } from 'react';
import { wasteData } from '../data/wasteSchedule';
import { WasteEvent } from '../../types';

// `town` musi być pozycją harmonogramu (`utils/wasteTown`). Nieznana nazwa —
// także samo „Rybno”, które ma dwa rejony — daje pustą listę, nie cudzy termin.
export const useWasteSchedule = (town: string | null): WasteEvent[] => {
    return useMemo(() => {
        const schedule = town ? wasteData[town] : undefined;
        if (!schedule) {
            return [];
        }

        const today = new Date();
        today.setHours(0, 0, 0, 0);

        const events: WasteEvent[] = [];

        Object.entries(schedule).forEach(([wasteType, datesString]) => {
            if (datesString === 'Brak odbioru') return;

            const dates = datesString.split(', ');
            dates.forEach(dateStr => {
                const [day, month, year] = dateStr.split('.');
                const eventDate = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
                eventDate.setHours(0, 0, 0, 0);

                if (eventDate >= today) {
                    const diffTime = eventDate.getTime() - today.getTime();
                    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

                    events.push({
                        type: wasteType,
                        originalDateString: dateStr,
                        daysRemaining: diffDays
                    });
                }
            });
        });

        // Sort by date (closest first)
        events.sort((a, b) => a.daysRemaining - b.daysRemaining);

        return events;
    }, [town]);
};
