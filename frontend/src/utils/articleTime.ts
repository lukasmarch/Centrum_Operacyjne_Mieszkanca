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

    if (start && !(end ? end < now : start < now)) {
        if (end && start <= now && now <= end) return `trwa teraz, do ${hm(end)}`;

        const days = dayDiff(start, now);
        const word = DAY_WORDS[days];
        if (word) return `${word} ${hm(start)}`;
        return start.toLocaleDateString('pl-PL', { day: 'numeric', month: 'long' });
    }

    const published = parseUtc(article.publishedAt);
    if (!published) return '';

    const diffH = Math.floor((now.getTime() - published.getTime()) / 3_600_000);
    if (diffH < 1) return 'przed chwilą';
    if (diffH < 24) return `${diffH}h temu`;
    return `${Math.floor(diffH / 24)}d temu`;
}
