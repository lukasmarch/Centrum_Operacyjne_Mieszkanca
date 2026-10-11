import React from 'react';
import { clockLabel } from '../src/utils/articleTime';

interface StaleDataNoticeProps {
    fetchedAt: Date | null;
}

/**
 * „Nie udało się odświeżyć” nad listą, która ZOSTAJE na ekranie.
 *
 * Do 11.10.2026 chwilowy brak zasięgu kasował feed i kalendarz, a w ich
 * miejsce stawał czerwony „Błąd: …” (audyt F-035). Stara treść z wiekiem
 * jest lepsza niż pusty ekran — pod warunkiem, że wiek jest powiedziany.
 */
const StaleDataNotice: React.FC<StaleDataNoticeProps> = ({ fetchedAt }) => {
    const at = fetchedAt ? clockLabel(fetchedAt) : null;
    return (
        <p role="status" className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-200">
            Nie udało się odświeżyć{at ? ` — pokazujemy stan z ${at}` : ''}. Spróbujemy ponownie za kilka minut.
        </p>
    );
};

export default StaleDataNotice;
