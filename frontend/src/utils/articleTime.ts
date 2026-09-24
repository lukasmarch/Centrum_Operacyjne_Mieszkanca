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
const isAllDayStart = (start: Date, end: Date | null): boolean =>
    !end && start.getHours() === 0 && start.getMinutes() === 0;

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
        if (end && start <= now && now <= end) return `trwa teraz, do ${hm(end)}`;

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
