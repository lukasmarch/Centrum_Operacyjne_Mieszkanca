/**
 * Prośba o zgodę na powiadomienia — pokazywana PRZY AWARII, nie w ustawieniach.
 *
 * Do 27.07.2026 jedyny włącznik push siedział w Profil → Preferencje. Skutek:
 * dwie subskrypcje w całej bazie produkcyjnej, obie należące do administratora.
 * Najlepszy mechanizm alertów wysyła do zera osób, jeśli nikt nie wie, że
 * istnieje — a nikt nie wchodzi w ustawienia konta, żeby szukać powiadomień.
 *
 * Prosimy w jedynym momencie, w którym wartość jest oczywista: gdy w feedzie
 * naprawdę stoi awaria. Obietnica jest wąska (prąd, woda, pożar, wypadek
 * w gminie Rybno) i dokładnie tyle wysyła `alert_push_job` — subskrypcja idzie
 * z kategorią „alerty", więc zapis tutaj NIE zapisuje na dzienne podsumowanie.
 *
 * 24.08.2026 doszedł wybór miejscowości. Alert szedł do wszystkich, jeśli tylko
 * w komunikacie padła jakakolwiek nazwa z gminy — mieszkaniec Koszelew dostawał
 * powiadomienie o wyłączeniu na ulicy Zajeziornej w Rybnie. Wieś zapisujemy na
 * SUBSKRYPCJI, nie na koncie: pięć z sześciu zgód wydano bez rejestracji.
 * Wybór jest dobrowolny — „cała gmina" zostaje domyślną odpowiedzią, bo alert,
 * który nie dotarł, jest gorszy niż alert o sąsiedniej wsi.
 *
 * 28.07.2026 doszedł drugi punkt wejścia: `campaignOnly`. Reels kampanijny kończy
 * się obietnicą „Włącz powiadomienia. Za darmo, bez zakładania konta", a widz
 * lądował na widoku, gdzie tego włącznika NIE BYŁO — jedyny stały siedzi
 * w Profil → Preferencje, czyli za rejestracją. Linki kampanijne prowadzą więc
 * na `rybnolive.pl/?alerty`.
 *
 * 11.08.2026: ten baner wisiał na bento-Dashboardzie, który wypadł z routingu
 * razem z przebudową strony głównej — czyli `?alerty` prowadziło znów donikąd.
 * Stoi teraz na `SimpleHomePage`, i to BEZ `campaignOnly`: awaria „na teraz"
 * zdarza się kilka razy w miesiącu, a przez resztę dni jedyna prośba o zgodę
 * na push nie pokazywała się w ogóle. W dniu z awarią prosi o nią głośniej
 * `AlertOfTheDay`, więc na stronie zawsze jest dokładnie jedno takie wezwanie.
 */
import React, { useEffect, useState } from 'react';
import { track } from '../src/services/analytics';
import { Bell, BellRing, Check, X } from 'lucide-react';
import { useMyVillage } from '../src/hooks/useMyVillage';
import { Select } from './simple/tv';
import { aboutPlace, inPlace } from '../src/utils/placeLocative';
import { usePushNotifications } from '../src/hooks/usePushNotifications';


const DISMISS_KEY = 'rl_push_prompt_dismissed_at';

// Znacznik w adresie z linków kampanijnych (post, komentarz, opis Reelsa)
const CAMPAIGN_PARAM = 'alerty';

// Świeżo założone konto — stawia go RegisterPage po udanej rejestracji.
// Mail powitalny obiecuje alerty o awariach i wieczorne przypomnienie o wywozie;
// jedno i drugie jedzie pushem, więc prośba o zgodę musi paść od razu, a nie
// dopiero w dniu, w którym w feedzie stanie awaria.
const REGISTERED_KEY = 'rl_registered_at';
const REGISTERED_WINDOW_DAYS = 7;

function justRegistered(): boolean {
  try {
    const raw = localStorage.getItem(REGISTERED_KEY);
    if (!raw) return false;
    return (Date.now() - Number(raw)) / 86400000 < REGISTERED_WINDOW_DAYS;
  } catch {
    return false;
  }
}

function cameFromCampaign(): boolean {
  try {
    return new URLSearchParams(window.location.search).has(CAMPAIGN_PARAM);
  } catch {
    return false;
  }
}

// Po zamknięciu nie wracamy przez miesiąc. Baner przy każdej awarii byłby
// dokładnie tym rodzajem natręctwa, przed którym alerty mają chronić.
const DISMISS_DAYS = 30;

function wasDismissed(): boolean {
  try {
    const raw = localStorage.getItem(DISMISS_KEY);
    if (!raw) return false;
    const days = (Date.now() - Number(raw)) / 86400000;
    return days < DISMISS_DAYS;
  } catch {
    return false;
  }
}

type Props = {
  /** Pokaż wyłącznie wtedy, gdy wejście pochodzi z linku kampanijnego (`?alerty`). */
  campaignOnly?: boolean;
  /**
   * `alert` — obok trwającej awarii w feedzie (czerwień jest wtedy prawdziwa).
   * `calm` — na stronie głównej w dzień bez awarii. Ta sama obietnica, ale bez
   * czerwonej ramki: baner alarmowy w spokojny dzień czyta się jak ostrzeżenie
   * i podnosi puls, zanim mieszkaniec dojdzie do słowa „następnej".
   */
  tone?: 'alert' | 'calm';
};

const AlertPushPrompt: React.FC<Props> = ({ campaignOnly = false, tone = 'alert' }) => {
  const { status, isSubscribed, isSupported, subscribe } = usePushNotifications();
  const [dismissed, setDismissed] = useState(wasDismissed);
  const [fresh] = useState(justRegistered);
  const [busy, setBusy] = useState(false);
  const [justEnabled, setJustEnabled] = useState(false);
  // Lista miejscowości pochodzi z backendu (`alert_policy.GMINA_RYBNO_PLACES`),
  // nie z `AVAILABLE_LOCATIONS` — tamto to 24 pozycje harmonogramu odpadów
  // („Rybno R1", „Domki letniskowe"), a nie nazwy wsi. Domyślnie wieś wybrana
  // na pulpicie (albo z konta) — czytelnik nie odpowiada na to samo pytanie dwa razy
  const { village, places } = useMyVillage();
  const [place, setPlace] = useState(village ?? '');
  useEffect(() => { if (village) setPlace(p => p || village); }, [village]);

  const hide =
    (campaignOnly && !cameFromCampaign() && !fresh) ||
    dismissed ||
    !isSupported ||
    isSubscribed ||
    status === 'denied' ||
    status === 'loading';

  // Prośba faktycznie trafiła na ekran. Bez tego licznika zgody nie mają się do
  // czego odnieść: nie wiadomo, czy push ma zero zgód dlatego, że ludzie odmawiają,
  // czy dlatego, że pytania nigdy nie zobaczyli.
  // ⚠️ W efekcie, nie w ciele komponentu — w ciele strzelałoby przy KAŻDYM renderze.
  useEffect(() => {
    if (!hide && !justEnabled) track('push_prompt');
  }, [hide, justEnabled]);

  if (justEnabled) {
    return (
      <p className="flex items-center gap-2 border-b border-tv-seam py-2.5 text-[15px] text-tv-muted">
        <Check size={17} className="shrink-0 text-tv-green" aria-hidden />
        Gotowe — o kolejnej awarii {place ? `w miejscowości ${place}` : 'w gminie Rybno'} dowiesz się od razu.
      </p>
    );
  }

  if (hide) return null;

  const close = () => {
    try {
      localStorage.setItem(DISMISS_KEY, String(Date.now()));
    } catch {
      /* tryb prywatny — baner wróci przy następnej wizycie, trudno */
    }
    setDismissed(true);
  };

  const enable = async () => {
    setBusy(true);
    // Sama kategoria „alerty": obiecujemy awarie, więc nie dopisujemy nikogo
    // przy okazji do porannego podsumowania ani do alertów smogowych.
    const ok = await subscribe(['alerty'], place || undefined);
    setBusy(false);
    if (ok) setJustEnabled(true);
  };

  // Ten sam układ co `VillagePushCta` na pulpicie: panel, żółty dzwonek, chabrowy
  // przycisk. Czerwień (dawny wariant `alert`) jest zarezerwowana dla samej awarii
  // — prośba o zgodę nie jest awarią, nawet gdy stoi obok niej.
  void tone;
  return (
    <section aria-label="Powiadomienia o awariach" className="relative bg-tv-panel p-4 pr-12 lg:flex lg:items-center lg:gap-6 lg:pr-14">
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-2 text-[17px] font-bold leading-snug text-white">
          <BellRing size={18} className="shrink-0 text-tv-yellow" aria-hidden />
          Dowiedz się o awarii {place ? inPlace(place) : 'w gminie Rybno'}, zanim wejdziesz na stronę
        </p>
        <p className="mt-1 text-[15px] leading-snug text-tv-muted">
          Prąd, woda, pożar, wypadek — nic poza tym. Za darmo, bez konta.
          {fresh && ' Tym samym kanałem przypomnimy wieczorem o jutrzejszym wywozie odpadów.'}
        </p>
      </div>

      <div className="mt-3 flex shrink-0 flex-col gap-2 sm:flex-row lg:mt-0">
        {/* Wieś znana (pulpit albo konto) — jeden przycisk, jak `VillagePushCta`.
            Wybór pokazujemy tylko wtedy, gdy wsi jeszcze nie ma */}
        {!village && places.length > 0 && (
          <Select
            value={place}
            onChange={(e) => setPlace(e.target.value)}
            aria-label="Miejscowość, której mają dotyczyć alerty"
          >
            <option value="">cała gmina</option>
            {places.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </Select>
        )}
        <button
          onClick={enable}
          disabled={busy}
          className="font-cond flex min-h-[52px] items-center justify-center gap-2 whitespace-nowrap bg-tv-blue px-5 text-[17px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff] disabled:opacity-60"
        >
          <Bell size={18} aria-hidden />
          {busy ? 'Włączam…' : place ? `Powiadamiaj ${aboutPlace(place)}` : 'Włącz powiadomienia'}
        </button>
      </div>

      <button
        onClick={close}
        aria-label="Nie teraz — schowaj na miesiąc"
        className="absolute right-0 top-0 flex h-11 w-11 items-center justify-center text-tv-muted hover:text-white"
      >
        <X size={18} aria-hidden />
      </button>
    </section>
  );
};

export default AlertPushPrompt;
