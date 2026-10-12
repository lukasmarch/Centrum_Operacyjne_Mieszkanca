import React from 'react';

import { AppSection } from '../../types';
import BusTrackerWidget from '../../components/BusTrackerWidget';
import { PageHead } from '../../components/simple/tv';

/**
 * Autobus Rybno–Działdowo: rozkład, mapa i pozycja kursu liczona z rozkładu
 * (bez GPS — „na żywo” było obietnicą bez pokrycia, audyt F-039).
 * Cel „rozwiń" z karty na stronie głównej — sama karta mówi tylko,
 * czy autobus jedzie i o której najbliższy.
 */
const BusPage: React.FC<{ onNavigate: (section: AppSection) => void }> = () => (
    <div className="max-w-4xl space-y-6">
        <div>
            <PageHead
                title="Autobus Rybno – Działdowo"
                sub="Rozkład jazdy, przystanki i pozycja kursu według rozkładu"
            />
        </div>

        <BusTrackerWidget />
    </div>
);

export default BusPage;
