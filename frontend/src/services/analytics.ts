/**
 * Pomiar tego, co dzieje się na stronie.
 *
 * Po co, skoro serwer ma log dostępu: front to SPA bez react-routera — nawigacja
 * idzie przez `history.pushState` w `App.tsx`, więc Caddy widzi WYŁĄCZNIE pierwsze
 * żądanie HTML. Bez tego pliku nie wiadomo, na którą sekcję ktoś wszedł, ile ich
 * obejrzał ani gdzie się zatrzymał.
 *
 * Trzy zasady, które trzeba znać przed zmianą:
 *
 *  1. **Nic tu nie może wywalić strony.** Każda funkcja jest owinięta w `try`,
 *     a błąd wysyłki jest połykany. Pomiar jest dodatkiem, nie funkcją serwisu.
 *  2. **`rl_sid` żyje w `sessionStorage`, nie w ciasteczku.** Ginie z zamknięciem
 *     karty, nie łączy wizyt między dniami i nie profiluje nikogo — dlatego
 *     pomiar nie wymaga banera zgody. Nie przenosić tego do `localStorage`.
 *  3. **`rl_acq` w `localStorage` przechowuje TYLKO źródło pierwszej wizyty**
 *     (utm, adres wejścia, host odsyłający, czas). Musi przeżyć dłużej niż
 *     sesja, bo między obejrzeniem rolki a założeniem konta mijają dni.
 *     Oba klucze są wymienione w polityce cookies.
 *
 * Wysyłka idzie `navigator.sendBeacon` przy chowaniu karty — to jedyny sposób,
 * żeby zdarzenie dotarło, gdy ktoś zamyka przeglądarkę. `fetch` w tym momencie
 * jest przerywany.
 */

const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000/api';

const SID_KEY = 'rl_sid';
const ACQ_KEY = 'rl_acq';
const FLUSH_AFTER_MS = 5000;
const MAX_QUEUE = 20;

export type SiteEventName =
  | 'view'
  | 'register_open'
  | 'push_prompt'
  | 'push_granted'
  | 'push_denied'
  | 'assistant_question'
  | 'session_stamp_click'
  | 'paywall_hit';

export interface Acquisition {
  session_id?: string;
  utm_campaign?: string;
  landing?: string;
  first_seen?: string;
}

interface QueuedEvent {
  event: SiteEventName;
  session_id?: string;
  section?: string;
  path?: string;
  referrer?: string;
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  meta?: Record<string, unknown>;
}

let queue: QueuedEvent[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;
let listenersBound = false;

/** Uuid wizyty. `crypto.randomUUID` nie istnieje w starszych Safari — stąd zapas. */
const newId = (): string => {
  try {
    if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  } catch { /* pusto */ }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
};

export const sessionId = (): string | undefined => {
  try {
    let id = sessionStorage.getItem(SID_KEY);
    if (!id) {
      id = newId();
      sessionStorage.setItem(SID_KEY, id);
    }
    return id;
  } catch {
    // Tryb prywatny albo zablokowana pamięć — zdarzenia lecą bez identyfikatora
    // wizyty. Zestawienia po sekcjach nadal działają, ścieżka jednej osoby nie.
    return undefined;
  }
};

const utmFromUrl = () => {
  const p = new URLSearchParams(window.location.search);
  const pick = (k: string) => p.get(k)?.slice(0, 100) || undefined;
  return {
    utm_source: pick('utm_source'),
    utm_medium: pick('utm_medium'),
    utm_campaign: pick('utm_campaign'),
    utm_content: pick('utm_content'),
  };
};

/**
 * Zapamiętaj źródło PIERWSZEJ wizyty. Wołane raz, przy starcie aplikacji.
 *
 * ⚠️ Musi zadziałać ZANIM `syncUrl` w `App.tsx` przepisze adres — ta funkcja
 * zostawia w pasku samą ścieżkę i gubi `?utm_...` dla wszystkich sekcji poza
 * zamówieniem. Po pierwszej nawigacji parametrów już nie ma skąd wziąć.
 *
 * Nie nadpisuje istniejącego wpisu: liczy się pierwsze zetknięcie z serwisem,
 * nie ostatnie.
 */
export const captureAcquisition = (): void => {
  try {
    if (localStorage.getItem(ACQ_KEY)) return;
    const utm = utmFromUrl();
    const referrer = document.referrer
      ? (() => { try { return new URL(document.referrer).hostname; } catch { return undefined; } })()
      : undefined;

    // Wejście bez żadnego śladu pochodzenia nie niesie informacji — nie zaśmiecamy
    // pamięci przeglądarki pustym wpisem, żeby prawdziwe źródło mogło się jeszcze
    // zapisać przy kolejnej wizycie z oznaczonego linku.
    if (!utm.utm_source && !utm.utm_campaign && !referrer) return;

    localStorage.setItem(ACQ_KEY, JSON.stringify({
      ...utm,
      referrer,
      landing: window.location.pathname.slice(0, 200),
      first_seen: new Date().toISOString(),
    }));
  } catch { /* pomiar nie przewraca strony */ }
};

/** Źródło pierwszej wizyty w kształcie, jakiego oczekuje `POST /auth/register`. */
export const getAcquisition = (): Acquisition | undefined => {
  try {
    const raw = localStorage.getItem(ACQ_KEY);
    if (!raw) return undefined;
    const a = JSON.parse(raw);
    return {
      session_id: sessionId(),
      utm_campaign: a.utm_campaign,
      landing: a.landing,
      first_seen: a.first_seen,
    };
  } catch {
    return undefined;
  }
};

const send = (): void => {
  if (!queue.length) return;
  const body = JSON.stringify({ events: queue });
  queue = [];
  try {
    const url = `${API_URL}/events`;
    // `sendBeacon` przechodzi, gdy karta jest zamykana; `fetch` w tym momencie nie.
    if (navigator.sendBeacon) {
      navigator.sendBeacon(url, new Blob([body], { type: 'application/json' }));
    } else {
      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        keepalive: true,
      }).catch(() => { /* pomiar nie przewraca strony */ });
    }
  } catch { /* pomiar nie przewraca strony */ }
};

const bindListeners = (): void => {
  if (listenersBound) return;
  listenersBound = true;
  // `visibilitychange` łapie przełączenie karty i wygaszenie ekranu na telefonie,
  // `pagehide` — zamknięcie i cofnięcie. Razem pokrywają wyjście ze strony.
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') send();
  });
  window.addEventListener('pagehide', send);
};

/** Zapisz zdarzenie. Wysyłka jest zbiorcza i odroczona — patrz `send()`. */
export const track = (event: SiteEventName, props: Partial<QueuedEvent> = {}): void => {
  try {
    bindListeners();
    queue.push({
      event,
      session_id: sessionId(),
      path: window.location.pathname.slice(0, 200),
      referrer: document.referrer || undefined,
      ...utmFromUrl(),
      ...props,
    });

    if (queue.length >= MAX_QUEUE) {
      send();
      return;
    }
    if (flushTimer) clearTimeout(flushTimer);
    flushTimer = setTimeout(send, FLUSH_AFTER_MS);
  } catch { /* pomiar nie przewraca strony */ }
};
