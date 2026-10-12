import React, { useState } from 'react';
import { Check, Zap, Crown, Store, HelpCircle } from 'lucide-react';
import { Chip, Tag } from './simple/tv';
import { cn } from '../lib/utils';

export type Frequency = 'monthly' | 'yearly';

export interface Plan {
  id: string;
  name: string;
  icon: React.ElementType;
  info: string;
  price: { monthly: number; yearly: number };
  features: { text: string; tooltip?: string }[];
  btnText: string;
  highlighted?: boolean;
  tierKey: string;
}

// Eksportowane — strona podsumowania zamówienia (CheckoutPage) korzysta z tych samych cen
export const PLANS: Plan[] = [
  {
    id: 'free',
    name: 'Dla Każdego',
    icon: Zap,
    info: 'Podstawowy dostęp do informacji lokalnych',
    tierKey: 'free',
    price: { monthly: 0, yearly: 0 },
    features: [
      { text: 'Wiadomości i artykuły lokalne' },
      { text: 'Alerty push o awariach i zagrożeniach', tooltip: 'Pożary, wypadki, awarie prądu i wody, smog — bezpieczeństwo zawsze za darmo' },
      { text: 'Pogoda i jakość powietrza' },
      // „24 miejscowości" było nieprawdą w obie strony: miejscowości jest 22, sołectw 20,
      // a 24 to pozycje w wyborze harmonogramu (Rybno dzieli się na R1 i R2, osobno domki
      // letniskowe). Ta sama pomyłka poszła kiedyś na fanpage — piszemy „cała gmina".
      { text: 'Harmonogram wywozu śmieci — cała gmina, bez konta', tooltip: 'Wybierasz miejscowość na stronie i widzisz pełny rok: zmieszane, bio, papier, szkło, metale, popiół i wielkogabarytowe. Konto nie jest potrzebne' },
      { text: 'Rozkład autobusu Rybno–Działdowo na żywo', tooltip: 'Przystanki, mapa i pozycja kursu w trasie' },
      { text: 'Zgłoszenia 24 ze zdjęciem' },
      // Do 19.08.2026 obiecywaliśmy tu „wystarczy adres e-mail, konto nie jest
      // potrzebne". Endpoint nadal to przyjmuje, ale strona główna prowadzi zapis
      // przez rejestrację i nie ma już w serwisie formularza na sam adres — obietnica,
      // której nie da się nigdzie spełnić, jest gorsza niż brak obietnicy.
      // Tygodniowy jest darmowy; CODZIENNY briefing zaczyna się dopiero od Premium
      // (`newsletter_job.send_daily_newsletter` filtruje po tierze).
      { text: 'Newsletter tygodniowy — za darmo', tooltip: 'W sobotę rano jeden mail: co się działo w gminie i co przed nami. Dostajesz go z każdym kontem, także darmowym. Codzienny poranny briefing jest w planie Premium' },
      { text: '5 pytań AI dziennie' },
      // Liczba policzona na kodzie: `get_gmina_variables_for_tier('free')` = 8.
      // Rejestr `gus_variables.py` ma 9 pozycji, ale jedna nie ma danych dla gminy.
      { text: 'Podstawowe dane GUS (8 wskaźników)' },
    ],
    btnText: 'Aktualny plan',
  },
  {
    id: 'premium',
    name: 'Premium',
    icon: Crown,
    info: 'Portal sam Cię uprzedzi — mniej niż 2 kawy miesięcznie',
    tierKey: 'premium',
    highlighted: true,
    price: { monthly: 9.99, yearly: 84 },
    features: [
      // Bez „nowego ogłoszenia BIP" — takiego powiadomienia nigdy nie wysyłał żaden job.
      // `proactive_alerts_job` (18:00) ma dokładnie dwie ścieżki: wywóz jutro i mróz tej nocy.
      { text: 'Proaktywny Asystent AI — nie pytasz, portal sam Cię uprzedzi', tooltip: 'Wieczorem o 18:00: jutro wywóz odpadów, mróz na drogach tej nocy' },
      { text: 'Nieograniczone pytania AI' },
      // Godzina musi zgadzać się ze schedulerem (`newsletter_daily`, pon–pt 7:15):
      // cennik mówił 6:30, a mail wychodzi 7:15. Tygodniowy zostaje NA DODATEK,
      // nie zamiast — i trzeba to powiedzieć, bo inaczej wygląda na zamianę.
      { text: 'Newsletter dzienny (pon–pt)', tooltip: 'Poranny briefing o 7:15 — skrót dnia, pogoda, awarie i wywóz odpadów. Newsletter tygodniowy dostajesz dalej' },
      { text: '37 wskaźników GUS dla gminy', tooltip: 'Demografia, rynek pracy, finanse gminy, mieszkalnictwo, edukacja, zdrowie — każdy z porównaniem do powiatu działdowskiego' },
      // Harmonogram jest jawny dla wszystkich, więc Premium nie sprzedaje DOSTĘPU do niego.
      // Różnicą jest przypomnienie: `proactive_alerts_job` o 18:00 wysyła push dzień PRZED
      // wywozem, dopasowany do rejonu (`waste_policy`). Do 21.08.2026 stało tu „rano" —
      // job chodził o 6:50, czyli po przejeździe śmieciarki.
      { text: 'Przypomnienie o wywozie wieczorem dzień wcześniej', tooltip: 'Harmonogram widzą wszyscy — Premium dostaje o 18:00 powiadomienie o jutrzejszym wywozie dla swojego rejonu, więc pojemnik wystawiasz na czas' },
      // „Personalizacja dashboardu" wypadła razem z panelem bento (11.08.2026):
      // obietnica w cenniku musi opisywać to, co plan naprawdę daje.
      //
      // Reklamy widzi wyłącznie plan darmowy — bramkę mają `AdBoard` (strona główna),
      // `NewsFeed` (ogłoszenia firm) i newsletter (`_marketing_consent` + brak promo
      // w briefingu dziennym). Trzy powierzchnie, jedna obietnica.
      { text: 'Brak reklam — ani na stronie, ani w mailu' },
      { text: 'Wszystko z planu Dla Każdego' },
    ],
    btnText: 'Wybierz Premium',
  },
  {
    id: 'firma',
    name: 'Firma lokalna',
    icon: Store,
    info: 'Dla firm z gminy — widoczność u mieszkańców (B2B)',
    tierKey: 'business',
    price: { monthly: 49, yearly: 490 },
    features: [
      { text: 'Wyróżniona wizytówka w katalogu firm', tooltip: 'Logo, opis, godziny otwarcia, telefon, link — na górze katalogu' },
      { text: 'Oznaczenie „Polecane w Rybnie"' },
      // Dwie różne miary od 12.08.2026 (`add_business_impressions`): `impressions_count`
      // = karta pojawiła się na ekranie, `views_count` = ktoś kliknął telefon lub www.
      // Samo „wyświetlenia" znaczyło co innego przed tym rozdzieleniem.
      { text: 'Statystyki: ile osób zobaczyło wizytówkę i ile kliknęło kontakt' },
      { text: 'Komplet 53 wskaźników GUS dla gminy', tooltip: 'Pełne dane statystyczne gminy Rybno z porównaniem do powiatu działdowskiego' },
      { text: 'Analizy lokalnego rynku od agenta AI', tooltip: 'GUS-Analityk odpowiada na pytania o demografię, rynek pracy i finanse gminy' },
      { text: 'Wszystko z planu Premium' },
      { text: 'Wcześniejszy dostęp do nowych funkcji' },
    ],
    btnText: 'Wybierz Firma lokalna',
  },
];

interface PricingCardsProps {
  currentTier: string;
  onSelect?: (tierId: string, frequency: Frequency) => void;
}

// Kwoty po polsku: „9,99 zł”, nie „9.99 zł” — sama prezentacja, ceny w PLANS bez zmian
const zl = (value: number) => value.toLocaleString('pl-PL', { maximumFractionDigits: 2 });

export /**
 * Pozycja planu z wyjaśnieniem. Do 11.10.2026 wyjaśnienie żyło w `title` pod
 * znakiem „?” 10 px — na telefonie i z klawiatury nie istniało. Teraz przycisk
 * 44 px rozwija je pod pozycją.
 */
const FeatureText: React.FC<{ text: string; tooltip?: string }> = ({ text, tooltip }) => {
  const [open, setOpen] = useState(false);
  if (!tooltip) return <span className="text-[14px] leading-snug text-[#d7dbe8]">{text}</span>;
  return (
    <span className="min-w-0 flex-1">
      <span className="flex items-start justify-between gap-1">
        <span className="pt-0.5 text-[14px] leading-snug text-[#d7dbe8]">{text}</span>
        <button
          type="button"
          onClick={() => setOpen(v => !v)}
          aria-expanded={open}
          aria-label={open ? 'Schowaj wyjaśnienie' : `Co to znaczy: ${text}`}
          className="-mr-2 -mt-2.5 flex h-11 w-11 shrink-0 items-center justify-center text-tv-muted transition-colors hover:text-white"
        >
          <HelpCircle size={16} aria-hidden />
        </button>
      </span>
      {open && <span className="mt-1 block text-[13px] leading-snug text-tv-muted">{tooltip}</span>}
    </span>
  );
};

const PricingCards: React.FC<PricingCardsProps> = ({ currentTier, onSelect }) => {
  const [frequency, setFrequency] = useState<Frequency>('monthly');

  return (
    <div className="space-y-5">
      {/* Okres rozliczenia — dwa filtry jak w reszcie podstron, aktywny = papier.
          Obrys szwem, bo w profilu przełącznik stoi na panelu w kolorze filtra */}
      <div role="group" aria-label="Okres rozliczenia" className="inline-flex flex-wrap gap-px border border-tv-seam bg-tv-seam">
        {(['monthly', 'yearly'] as Frequency[]).map((freq) => (
          <Chip key={freq} active={frequency === freq} onClick={() => setFrequency(freq)}>
            {freq === 'monthly' ? 'Miesięcznie' : 'Rocznie'}
            {freq === 'yearly' && (
              <span className={`tabular text-[13px] font-extrabold normal-case ${frequency === freq ? 'opacity-70' : 'text-tv-muted'}`}>
                do -30%
              </span>
            )}
          </Chip>
        ))}
      </div>

      {/* Plany w siatce na szwie. Wyróżniony = górna krawędź 2 px chabru
          i plakietka, bez gradientu, poświaty i powiększenia */}
      <div className="grid grid-cols-1 gap-px bg-tv-seam md:grid-cols-3">
        {PLANS.map((plan) => {
          const Icon = plan.icon;
          const price = plan.price[frequency];
          const isCurrent = plan.tierKey === currentTier;
          const savingPct = plan.price.monthly > 0
            ? Math.round(((plan.price.monthly * 12 - plan.price.yearly) / (plan.price.monthly * 12)) * 100)
            : 0;

          return (
            <div
              key={plan.id}
              className={cn(
                'flex flex-col border-t-2 bg-tv-panel',
                plan.highlighted ? 'border-tv-blue' : 'border-tv-seam'
              )}
            >
              {/* Header */}
              <div className="border-b border-tv-seam p-5">
                <div className="flex min-h-[26px] flex-wrap items-center gap-1.5">
                  {plan.highlighted && <Tag tone="blue">Najpopularniejszy</Tag>}
                  {frequency === 'yearly' && savingPct > 0 && (
                    <Tag tone="paper"><span className="tabular">-{savingPct}%</span></Tag>
                  )}
                </div>
                <div className="mt-3 flex items-start gap-2.5">
                  <Icon size={20} className="mt-0.5 shrink-0 text-tv-muted" aria-hidden />
                  <div className="min-w-0">
                    <h3 className="font-cond text-[22px] font-extrabold leading-tight text-white">{plan.name}</h3>
                    <p className="mt-0.5 text-[14px] leading-snug text-tv-muted">{plan.info}</p>
                  </div>
                </div>
                <div className="mt-4 flex items-baseline gap-1">
                  <span className="font-cond tabular text-[36px] font-extrabold leading-none text-white">{price === 0 ? '0' : zl(price)} zł</span>
                  {price > 0 && (
                    <span className="text-[15px] text-tv-muted">
                      /{frequency === 'monthly' ? 'mc' : 'rok'}
                    </span>
                  )}
                </div>
                {frequency === 'yearly' && savingPct > 0 && (
                  <p className="tabular mt-1 text-[13px] text-tv-muted">
                    zamiast {zl(plan.price.monthly * 12)} zł/rok
                  </p>
                )}
              </div>

              {/* Features */}
              <ul className="flex-1 space-y-2.5 p-5">
                {plan.features.map((f, i) => (
                  <li key={i} className="flex items-start gap-2.5">
                    <Check
                      size={16}
                      strokeWidth={2.5}
                      aria-hidden
                      className={cn('mt-0.5 shrink-0', plan.highlighted ? 'text-tv-bluesoft' : 'text-tv-muted')}
                    />
                    <FeatureText text={f.text} tooltip={f.tooltip} />
                  </li>
                ))}
              </ul>

              {/* CTA */}
              <div className="border-t border-tv-seam p-4">
                {/* Plan darmowy nie jest do kupienia — nigdy nie dostaje przycisku,
                    inaczej „Aktualny plan" świeci się także u kogoś z Premium */}
                {isCurrent || plan.tierKey === 'free' ? (
                  <div className="font-cond flex min-h-[52px] w-full items-center justify-center border-2 border-tv-seam text-[16px] font-bold uppercase tracking-wide text-tv-muted">
                    {isCurrent ? 'Aktualny plan' : 'Dostępny bez opłat'}
                  </div>
                ) : (
                  <button
                    onClick={() => onSelect?.(plan.tierKey, frequency)}
                    className={cn(
                      'font-cond min-h-[52px] w-full px-4 text-[17px] font-extrabold uppercase tracking-wide transition-colors',
                      plan.highlighted
                        ? 'bg-tv-blue text-white hover:bg-[#3a63ff]'
                        : 'bg-tv-paper text-tv-ink hover:bg-white'
                    )}
                  >
                    {plan.btnText}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="space-y-1.5 text-[13px] leading-relaxed text-tv-muted">
        <p>
          Ceny brutto w PLN · Płatność z góry za wybrany okres · <strong className="text-tv-paper">bez automatycznego odnawiania</strong>
          {' '}· Dostęp aktywowany od razu po potwierdzeniu płatności
        </p>
        <p>
          Bezpieczne płatności Przelewy24 (BLIK, karta, przelew online) · Faktury dla firm: biuro@lumargo.pl
          {' '}· Plan „Firma lokalna" to usługa B2B (§ 11 Regulaminu)
        </p>
        <p>
          Szczegóły: <a href="/regulamin" className="text-tv-bluesoft underline underline-offset-2 hover:text-white">Regulamin</a>
          {' · '}
          <a href="/polityka-prywatnosci" className="text-tv-bluesoft underline underline-offset-2 hover:text-white">Polityka prywatności</a>
        </p>
      </div>
    </div>
  );
};

export default PricingCards;
