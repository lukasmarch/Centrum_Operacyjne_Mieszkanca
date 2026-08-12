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
import React, { useState } from 'react';
import { BellRing, X } from 'lucide-react';
import { usePushNotifications } from '../src/hooks/usePushNotifications';

const DISMISS_KEY = 'rl_push_prompt_dismissed_at';

// Znacznik w adresie z linków kampanijnych (post, komentarz, opis Reelsa)
const CAMPAIGN_PARAM = 'alerty';

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
  const [busy, setBusy] = useState(false);
  const [justEnabled, setJustEnabled] = useState(false);

  const hide =
    (campaignOnly && !cameFromCampaign()) ||
    dismissed ||
    !isSupported ||
    isSubscribed ||
    status === 'denied' ||
    status === 'loading';

  if (justEnabled) {
    return (
      <div className="flex items-center gap-2.5 p-3 rounded-2xl bg-emerald-950/30 border border-emerald-800/30 text-sm text-emerald-300">
        <BellRing size={15} className="flex-shrink-0" />
        Gotowe — o kolejnej awarii w gminie Rybno dowiesz się od razu.
      </div>
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
    const ok = await subscribe(['alerty']);
    setBusy(false);
    if (ok) setJustEnabled(true);
  };

  const calm = tone === 'calm';

  return (
    <div
      className={`relative flex flex-col sm:flex-row sm:items-center gap-3 p-4 rounded-2xl border ${
        calm
          ? 'bg-[#0d1117] border-white/10'
          : 'bg-gradient-to-r from-red-950/40 to-white/[0.02] border-red-500/20'
      }`}
    >
      <div className="flex items-start gap-3 flex-1 pr-6">
        <BellRing size={18} className={`flex-shrink-0 mt-0.5 ${calm ? 'text-blue-400' : 'text-red-400'}`} />
        <div>
          <p className="text-sm font-bold text-neutral-100">
            O następnej awarii dowiedz się bez wchodzenia na stronę
          </p>
          <p className="text-xs text-neutral-400 mt-0.5">
            Powiadomimy o wyłączeniach prądu, braku wody, pożarach i wypadkach
            w gminie Rybno. Za darmo, bez konta — i nic poza tym.
          </p>
        </div>
      </div>

      <button
        onClick={enable}
        disabled={busy}
        className={`flex-shrink-0 min-h-[44px] px-4 py-2 rounded-xl text-xs font-bold text-white transition-colors disabled:opacity-50 ${
          calm ? 'bg-blue-600 hover:bg-blue-500' : 'bg-red-600 hover:bg-red-500'
        }`}
      >
        {busy ? 'Włączam…' : 'Włącz alerty'}
      </button>

      <button
        onClick={close}
        aria-label="Zamknij"
        className="absolute top-2.5 right-2.5 p-1 rounded-lg text-neutral-600 hover:text-neutral-300 hover:bg-white/5 transition-colors"
      >
        <X size={14} />
      </button>
    </div>
  );
};

export default AlertPushPrompt;
