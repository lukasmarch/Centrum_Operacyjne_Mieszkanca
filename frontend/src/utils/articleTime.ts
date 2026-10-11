/**
 * Kiedy jest to, o czym mówi wpis — jedno miejsce na tę odpowiedź.
 *
 * 25.08.2026 kafel „Ostatnio w gminie" opisał wyłączenie prądu trwające tego
 * dnia od 9:30 jako „3d temu", bo licznik patrzył wyłącznie na datę OGŁOSZENIA
 * (Energa zapowiedziała je 21.08). Dla zapowiedzi liczy się termin, nie wiek
 * ogłoszenia — dokładnie ta sama reguła, którą backend stosuje w rankingu
 * (`feed_policy._reference_time`) i w materiale dla modelu (`time_label`).
 *
 * Trzy kopie licznika (`useArticles`, `NewsFeed`, `NewsTile`) miały przy okazji
 * wspólny błąd strefy: `new Date("2026-08-24T10:45:00")` bez „Z" przeglądarka
 * czyta jako czas LOKALNY, więc wpisy wychodziły o dwie godziny świeższe.
 * Ta sama pułapka co w `AlertOfTheDay.parseUtc` i `useDailySummary.parseUtc`.
 */

/** Naiwny UTC z backendu → Date. */
export const parseUtc = (raw?: string | null): Date | null => {
    if (!raw) return null;
    const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(raw);
    const parsed = new Date(hasZone ? raw : `${raw}Z`);
    return isNaN(parsed.getTime()) ? null : parsed;
};

const hm = (d: Date) => d.toLocaleTimeString('pl-PL', { hour: 'numeric', minute: '2-digit' });

const startOfDay = (d: Date) => {
    const copy = new Date(d);
    copy.setHours(0, 0, 0, 0);
    return copy;
};

/** Ile dni dzieli dwie chwile, licząc po kalendarzu, nie po 24 godzinach. */
const dayDiff = (a: Date, b: Date) =>
    Math.round((startOfDay(a).getTime() - startOfDay(b).getTime()) / 86_400_000);

/**
 * Chwila pomiaru/odczytu: „14:05”, „wczoraj 22:01”, „9 paź 06:03”.
 * Sama godzina przy nieświeżych danych kłamie — „ostatni odczyt z 22:01”
 * rano czyta się jak dzisiejszy wieczór, a był wczorajszy.
 */
export function clockLabel(at: Date, now: Date = new Date()): string {
    const days = dayDiff(now, at);
    if (days === 0) return hm(at);
    if (days === 1) return `wczoraj ${hm(at)}`;
    return `${at.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' }).replace('.', '')} ${hm(at)}`;
}

const DAY_WORDS: Record<number, string> = { '-1': 'wczoraj', 0: 'dziś', 1: 'jutro', 2: 'pojutrze' };

/**
 * Wpis BEZ godziny — w bazie stoi jako lokalna północ.
 *
 * Ta sama reguła, co `eventTime.ts::isAllDay` i `time_span.is_all_day`
 * w backendzie. Kafle wiadomości miały własną, niezależną kopię licznika
 * i jako jedyne jej nie dostały — z dwoma skutkami naraz (24.09.2026):
 *  - „Iłowo-Osada przyjmuje wnioski" pokazywało „jutro 0:00", czyli zmyśloną
 *    godzinę, której źródło nigdy nie podało;
 *  - „Podróż do Japonii 24 września" pokazywało „1d temu" W DNIU wydarzenia,
 *    bo start (dzisiejsza północ) już minął i licznik wracał do wieku publikacji.
 *
 * Podany koniec przeczy całodniowości — źródło znało ramy godzinowe.
 */
const isMidnight = (d: Date) => d.getHours() === 0 && d.getMinutes() === 0;

const isAllDayStart = (start: Date, end: Date | null): boolean =>
    isMidnight(start) && (!end || isMidnight(end));

/**
 * Zakres DNI („od 5 do 11 października”) — backend zapisuje go od 11.10.2026
 * (`time_span`, audyt F-002) jako lokalną północ startu i północ PO ostatnim
 * dniu. Plakietka pokazywała wtedy „trwa teraz, do 0:00” — godzinę, której
 * źródło nie podało, i koniec, który brzmiał jak „dziś o północy”.
 */
const lastDayOf = (end: Date) => new Date(end.getTime() - 1);

const shortDay = (d: Date) => d.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' }).replace('.', '');

/** „5–11 paź” albo „30 wrz – 2 paź” */
const dayRange = (start: Date, last: Date): string =>
    start.getMonth() === last.getMonth()
        ? `${start.getDate()}–${shortDay(last)}`
        : `${shortDay(start)} – ${shortDay(last)}`;

/** Koniec trwającego zdarzenia: godzina, gdy kończy się dziś, inaczej dzień */
function untilLabel(end: Date, allDay: boolean, now: Date): string {
    if (allDay) {
        const days = dayDiff(lastDayOf(end), now);
        if (days <= 0) return 'trwa — ostatni dzień';
        if (days === 1) return 'trwa do jutra';
        return `trwa do ${shortDay(lastDayOf(end))}`;
    }
    if (dayDiff(end, now) === 0) return `trwa teraz, do ${hm(end)}`;
    return `trwa do ${shortDay(end)} ${hm(end)}`;
}

export interface ArticleTimes {
    publishedAt?: string | null;
    eventAt?: string | null;
    eventUntil?: string | null;
}

/**
 * Etykieta czasu do plakietki przy nagłówku — krótka, bo dzieli wiersz
 * z nazwą kategorii.
 *
 * Zdarzenie z terminem opisujemy terminem („dziś 9:30", „trwa teraz"),
 * zwykłą wiadomość — wiekiem („2h temu"). Zdarzenie, które się skończyło,
 * wraca do wieku: „wczoraj 17:28" sugerowałoby, że coś jeszcze przed nami.
 */
export function articleTimeLabel(article: ArticleTimes, now: Date = new Date()): string {
    const start = parseUtc(article.eventAt);
    const end = parseUtc(article.eventUntil);
    const allDay = start ? isAllDayStart(start, end) : false;

    // Wpis całodniowy jest aktualny do KOŃCA swojego dnia, nie od północy do
    // północy z minutą — inaczej wydarzenie „na dziś" liczy się jako minione
    // przez cały dzień, w którym się odbywa.
    const afterEvent = start
        ? (end ? end < now : (allDay ? dayDiff(start, now) < 0 : start < now))
        : true;

    if (start && !afterEvent) {
        // Jeden dzień zapisany jako północ–północ to zwykły wpis całodniowy („dziś”)
        const multiDay = !!end && allDay && dayDiff(lastDayOf(end), start) >= 1;
        if (end && start <= now && now <= end && (multiDay || !allDay)) {
            return untilLabel(end, allDay, now);
        }

        // Przed startem — cały zakres, bo „5 października” gubi, że to
        // nie jednodniowe wydarzenie
        if (multiDay && end) return dayRange(start, lastDayOf(end));

        const days = dayDiff(start, now);
        const word = DAY_WORDS[days];
        // Bez godziny, gdy źródło jej nie podało: „jutro 0:00" to precyzja,
        // której nie mamy — ta sama zasada, co „(cały dzień)" w backendzie,
        // tylko krócej, bo plakietka dzieli wiersz z nazwą kategorii.
        if (word) return allDay ? word : `${word} ${hm(start)}`;
        return start.toLocaleDateString('pl-PL', { day: 'numeric', month: 'long' });
    }

    const published = parseUtc(article.publishedAt);
    if (!published) return '';

    const diffH = Math.floor((now.getTime() - published.getTime()) / 3_600_000);
    if (diffH < 1) return 'przed chwilą';
    if (diffH < 24) return `${diffH}h temu`;
    return `${Math.floor(diffH / 24)}d temu`;
}
