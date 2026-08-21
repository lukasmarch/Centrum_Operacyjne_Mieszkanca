/**
 * Kiedy wydarzenie jest względem TERAZ — jedno miejsce na tę odpowiedź.
 *
 * 21.08.2026 o 10:25 kafel „Dziś w gminie" zapraszał na posiedzenie komisji,
 * które skończyło się o 9:00, a kafel „W ten weekend" pokazywał to samo
 * posiedzenie zamiast niedzielnego wyścigu MTB. Obie karty porównywały DZIEŃ,
 * nigdy godzinę — wydarzenie z rana było „dzisiejsze" do północy.
 *
 * Zegar zostaje po stronie przeglądarki, nie w API: strona bywa otwarta
 * godzinami, a `useEvents` odświeża dane co 5 minut, więc status policzony
 * na serwerze zestarzałby się w karcie.
 */
import { Event } from '../../types';

/** Ile trwa wydarzenie, które nie podało końca. */
const DEFAULT_DURATION_H = 2;

export type EventPhase =
    | 'past'      // już po wszystkim
    | 'ongoing'   // trwa w tej chwili
    | 'today'     // dziś, jeszcze przed nami
    | 'upcoming'; // kolejnego dnia lub później

export interface TimedEvent extends Event {
    /** Koniec wydarzenia, gdy źródło go podało (ISO). */
    endDate?: string;
}

/**
 * Moment, w którym wydarzenie przestaje być aktualne.
 *
 * Trzy przypadki, bo trzy różne rodzaje wpisu:
 *  - podany koniec — wierzymy źródłu;
 *  - całodniowe (00:00, bez godziny) — trwa do końca dnia, bo „Wielkie Otwarcie
 *    e-KAMIX 22 sierpnia" nie kończy się o północy z 21 na 22;
 *  - z godziną — domyślnie dwie godziny. Bez tego posiedzenie o 9:00 znikałoby
 *    z karty o 9:01, a mieszkaniec ma prawo wiedzieć, że właśnie trwa.
 *    Ten sam pomysł, co `weather_alert.validity_or_default` w backendzie:
 *    brak deklarowanego końca nie znaczy ani „wiecznie", ani „natychmiast".
 */
export function endOf(event: TimedEvent): Date {
    const start = new Date(event.date);
    if (event.endDate) return new Date(event.endDate);

    const allDay = start.getHours() === 0 && start.getMinutes() === 0;
    if (allDay) {
        const end = new Date(start);
        end.setHours(23, 59, 59, 999);
        return end;
    }
    return new Date(start.getTime() + DEFAULT_DURATION_H * 3600_000);
}

/** Wpis bez godziny — w bazie 00:00. „Otwarcie sklepu 22 sierpnia", nie o północy. */
export function isAllDay(event: TimedEvent): boolean {
    const start = new Date(event.date);
    return !event.endDate && start.getHours() === 0 && start.getMinutes() === 0;
}

export function phaseOf(event: TimedEvent, now: Date = new Date()): EventPhase {
    const start = new Date(event.date);
    if (endOf(event) < now) return 'past';

    // Całodniowe nigdy nie jest „ongoing": źródło nie podało godziny, więc
    // „teraz: Wielkie Otwarcie e-KAMIX, do 23:59" byłoby zmyśleniem precyzji,
    // której nie mamy. Zostaje wpisem na dziś — i tak jest prawdziwe cały dzień.
    if (isAllDay(event)) {
        return start.toDateString() === now.toDateString() ? 'today' : 'upcoming';
    }

    if (start <= now) return 'ongoing';
    return start.toDateString() === now.toDateString() ? 'today' : 'upcoming';
}

/** Wydarzenia jeszcze aktualne, najbliższe pierwsze. */
export function upcomingFirst(
    events: TimedEvent[] | null,
    now: Date = new Date(),
): TimedEvent[] {
    return (events ?? [])
        .filter(event => phaseOf(event, now) !== 'past')
        .sort((a, b) => +new Date(a.date) - +new Date(b.date));
}

/**
 * Najbliższy weekend jako przedział [start, koniec).
 *
 * Zaczyna się w PIĄTEK PO POŁUDNIU, nie o północy: kafel liczył piątek od 00:00,
 * więc w piątek rano „W ten weekend" powtarzał to samo, co „Dziś w gminie",
 * i wygrywała poranna komisja zamiast niedzielnego wyścigu. Piątkowy wieczór
 * zostaje w weekendzie — koncert o 19:00 to weekend, narada o 9:00 nie.
 *
 * Gdy weekend już trwa, początkiem jest TERAZ — w sobotę wieczorem nie
 * zapraszamy na sobotni poranek.
 */
export const WEEKEND_STARTS_AT_HOUR = 16;

export function weekendRange(now: Date = new Date()): { from: Date; to: Date } {
    const day = now.getDay(); // 0 = niedziela, 5 = piątek, 6 = sobota
    const friday = new Date(now);
    friday.setHours(WEEKEND_STARTS_AT_HOUR, 0, 0, 0);

    if (day === 6) friday.setDate(friday.getDate() - 1);        // sobota
    else if (day === 0) friday.setDate(friday.getDate() - 2);   // niedziela
    else friday.setDate(friday.getDate() + ((5 - day + 7) % 7)); // pon.–pt.

    const to = new Date(friday);
    to.setDate(friday.getDate() + (friday.getDay() === 5 ? 3 : 2));
    to.setHours(0, 0, 0, 0);

    return { from: now > friday ? now : friday, to };
}

export function isInWeekend(event: TimedEvent, now: Date = new Date()): boolean {
    const { from, to } = weekendRange(now);
    const start = new Date(event.date);
    // Wydarzenie, które właśnie trwa, należy do weekendu tak samo jak to,
    // które dopiero się zacznie — liczy się koniec, nie początek.
    return endOf(event) >= from && start < to;
}

/** „, 9:00" albo pusto dla całodniowych — godzina „0:00" niczego nie mówi. */
export function timeSuffix(event: TimedEvent): string {
    const start = new Date(event.date);
    if (start.getHours() === 0 && start.getMinutes() === 0) return '';
    return `, ${start.toLocaleTimeString('pl-PL', { hour: 'numeric', minute: '2-digit' })}`;
}

/** „sobota 22.08" — dzień, w którym mieszkaniec ma się stawić. */
export function dayLabel(event: TimedEvent): string {
    return new Date(event.date).toLocaleDateString('pl-PL', {
        weekday: 'long',
        day: 'numeric',
        month: 'numeric',
    });
}
