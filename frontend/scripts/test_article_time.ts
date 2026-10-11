/**
 * Plakietka czasu wpisu (`src/utils/articleTime.ts`) — test bez runnera.
 * Uruchomienie: TZ=Europe/Warsaw node --experimental-strip-types scripts/test_article_time.ts
 *
 * Czasy jak w API: naiwny UTC. Zakres dni z backendu (od 11.10.2026):
 * lokalna północ startu → lokalna północ PO ostatnim dniu.
 */
import { articleTimeLabel, clockLabel } from '../src/utils/articleTime.ts';
import { phaseOf } from '../src/utils/eventTime.ts';

let failed = 0;
const check = (name: string, got: string, want: string) => {
    const ok = got === want;
    if (!ok) failed++;
    console.log(`${ok ? 'OK ' : 'ŹLE'} ${name}: ${JSON.stringify(got)}${ok ? '' : ` (oczekiwano ${JSON.stringify(want)})`}`);
};

// 5–11 października (lokalnie): start 4.10 22:00 UTC, koniec 11.10 22:00 UTC
const range = { eventAt: '2026-10-04T22:00:00', eventUntil: '2026-10-11T22:00:00' };
const at = (iso: string) => new Date(iso); // ze strefą — to „teraz” testu

check('zakres, przed startem', articleTimeLabel(range, at('2026-10-02T10:00:00+02:00')), '5–11 paź');
check('zakres, w trakcie', articleTimeLabel(range, at('2026-10-08T10:00:00+02:00')), 'trwa do 11 paź');
check('zakres, przedostatni dzień', articleTimeLabel(range, at('2026-10-10T10:00:00+02:00')), 'trwa do jutra');
check('zakres, ostatni dzień', articleTimeLabel(range, at('2026-10-11T23:30:00+02:00')), 'trwa — ostatni dzień');
check('zakres przez granicę miesiąca', articleTimeLabel(
    { eventAt: '2026-09-29T22:00:00', eventUntil: '2026-10-02T22:00:00' }, at('2026-09-25T10:00:00+02:00')), '30 wrz – 2 paź');

// Jeden dzień jako północ–północ → zwykły wpis całodniowy
const oneDay = { eventAt: '2026-10-10T22:00:00', eventUntil: '2026-10-11T22:00:00' };
check('jeden dzień, tego dnia', articleTimeLabel(oneDay, at('2026-10-11T12:00:00+02:00')), 'dziś');
check('jeden dzień, dzień wcześniej', articleTimeLabel(oneDay, at('2026-10-10T12:00:00+02:00')), 'jutro');

// Bez zmian: godziny w obrębie dnia, wpis całodniowy bez końca
const hours = { eventAt: '2026-10-11T07:30:00', eventUntil: '2026-10-11T13:00:00' };
check('godziny, w trakcie', articleTimeLabel(hours, at('2026-10-11T10:00:00+02:00')), 'trwa teraz, do 15:00');
check('godziny, przed', articleTimeLabel(hours, at('2026-10-11T08:00:00+02:00')), 'dziś 9:30');
check('całodniowy bez końca', articleTimeLabel({ eventAt: '2026-10-11T22:00:00' }, at('2026-10-11T12:00:00+02:00')), 'jutro');

// Godzinowe przez kilka dni — koniec nie jest „dziś o 16:00”
check('kilka dni z godzinami', articleTimeLabel(
    { eventAt: '2026-10-09T06:00:00', eventUntil: '2026-10-13T14:00:00' }, at('2026-10-11T12:00:00+02:00')), 'trwa do 13 paź 16:00');

// Godzina bez końca: trwa DEFAULT_DURATION_H (3 h) — ta sama reguła co kalendarz i backend (F-004)
const noEnd = { eventAt: '2026-10-11T07:00:00', publishedAt: '2026-10-08T10:00:00' }; // 9:00 lokalnie
check('bez końca, przed startem', articleTimeLabel(noEnd, at('2026-10-11T08:00:00+02:00')), 'dziś 9:00');
check('bez końca, godzinę po starcie — trwa, bez zmyślonego końca',
    articleTimeLabel(noEnd, at('2026-10-11T10:00:00+02:00')), 'trwa od 9:00');
check('bez końca, 3 h po starcie — wiek ogłoszenia',
    articleTimeLabel(noEnd, at('2026-10-11T12:05:00+02:00')), '3d temu');
const calEvent = { id: '1', title: 't', date: '2026-10-11T07:00:00Z', location: '', category: '' };
check('kalendarz: ten sam wpis godzinę po starcie trwa',
    phaseOf(calEvent, at('2026-10-11T10:00:00+02:00')), 'ongoing');
check('kalendarz: 3 h po starcie — po wszystkim',
    phaseOf(calEvent, at('2026-10-11T12:05:00+02:00')), 'past');

// Chwila odczytu niesie dzień, gdy nie jest dzisiejsza
const now = at('2026-10-11T08:00:00+02:00');
check('odczyt dziś', clockLabel(at('2026-10-11T06:03:00+02:00'), now), '6:03');
check('odczyt wczoraj', clockLabel(at('2026-10-10T22:01:00+02:00'), now), 'wczoraj 22:01');
check('odczyt starszy', clockLabel(at('2026-10-09T06:03:00+02:00'), now), '9 paź 6:03');

if (failed) {
    console.log(`\n${failed} błędnych`);
    process.exit(1);
}
console.log('\nwszystko zielone');
