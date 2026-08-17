import React, { useState } from 'react';
import { CheckCircle, Zap, Crown, Store } from 'lucide-react';
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
      { text: 'Newsletter tygodniowy — za darmo', tooltip: 'W sobotę rano jeden mail: co się działo w gminie i co przed nami. Wystarczy adres e-mail, konto nie jest potrzebne' },
      { text: '5 pytań AI dziennie' },
      { text: 'Podstawowe dane GUS (9 wskaźników)' },
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
      { text: 'Proaktywny Asystent AI — nie pytasz, portal sam Cię uprzedzi', tooltip: 'Powiadomienia bez pytania: jutro wywóz odpadów, mróz na drogach, nowe ogłoszenie BIP' },
      { text: 'Nieograniczone pytania AI' },
      // Godzina musi zgadzać się ze schedulerem (`newsletter_daily`, pon–pt 7:15),
      // bo to obietnica sprzedażowa: cennik mówił 6:30, a mail wychodzi 7:15
      { text: 'Newsletter dzienny (pon–pt)', tooltip: 'Poranny briefing o 7:15 — po nocnym zbiorze wiadomości. Newsletter tygodniowy dostajesz dalej' },
      { text: '57 wskaźników GUS', tooltip: 'Demografia, rynek pracy, finanse gminy, mieszkalnictwo, edukacja, zdrowie + dane powiatu działdowskiego' },
      // „Personalizacja dashboardu" wypadła razem z bento-panelem (11.08.2026):
      // obietnica w cenniku musi opisywać to, co plan naprawdę daje.
      //
      // 12.08.2026: harmonogram odpadów jest jawny dla wszystkich, więc Premium nie może
      // już sprzedawać DOSTĘPU do niego. Różnicą jest przypomnienie — `proactive_alerts_job`
      // (6:50) wysyła push dzień PRZED wywozem, dopasowany po `User.location`; kto ma
      // newsletter dzienny, dostaje to samo mailem zamiast pusha, żeby nie dublować.
      { text: 'Przypomnienie o wywozie dzień wcześniej', tooltip: 'Harmonogram widzą wszyscy — Premium dostaje rano powiadomienie o jutrzejszym wywozie dla swojej miejscowości, więc nie trzeba pamiętać o sprawdzaniu' },
      { text: 'Brak reklam w feedzie' },
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
      { text: 'Statystyki wyświetleń wizytówki' },
      { text: 'Komplet 88 wskaźników GUS', tooltip: 'Pełne dane statystyczne: gmina Rybno + powiat działdowski' },
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

export const PricingCards: React.FC<PricingCardsProps> = ({ currentTier, onSelect }) => {
  const [frequency, setFrequency] = useState<Frequency>('monthly');

  return (
    <div className="space-y-6">
      {/* Toggle */}
      <div className="flex justify-center">
        <div className="flex items-center gap-1 bg-white/5 border border-white/10 rounded-full p-1">
          {(['monthly', 'yearly'] as Frequency[]).map((freq) => (
            <button
              key={freq}
              onClick={() => setFrequency(freq)}
              className={cn(
                'relative px-5 py-1.5 rounded-full text-sm font-medium transition-all duration-200',
                frequency === freq
                  ? 'bg-white text-black shadow'
                  : 'text-neutral-400 hover:text-white'
              )}
            >
              {freq === 'monthly' ? 'Miesięcznie' : 'Rocznie'}
              {freq === 'yearly' && (
                <span className="absolute -top-2.5 -right-1 bg-emerald-500 text-white text-[9px] font-bold px-1.5 py-0.5 rounded-full">
                  do -30%
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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
                'relative flex flex-col rounded-2xl border overflow-hidden transition-all duration-200',
                plan.highlighted
                  ? 'border-blue-500/40 bg-gradient-to-b from-blue-950/60 to-blue-900/30 shadow-lg shadow-blue-500/10 scale-[1.02]'
                  : 'border-white/8 bg-white/3 hover:border-white/15'
              )}
            >
              {/* Popular badge */}
              {plan.highlighted && (
                <div className="absolute top-3 right-3 bg-blue-500 text-white text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full">
                  Najpopularniejszy
                </div>
              )}

              {/* Yearly savings badge */}
              {frequency === 'yearly' && savingPct > 0 && (
                <div className="absolute top-3 left-3 bg-emerald-500/20 text-emerald-400 text-[10px] font-bold border border-emerald-500/30 px-2 py-0.5 rounded-full">
                  -{savingPct}%
                </div>
              )}

              {/* Header */}
              <div className={cn('p-5 border-b', plan.highlighted ? 'border-blue-500/20' : 'border-white/6')}>
                <div className="flex items-center gap-2 mb-3">
                  <div className={cn(
                    'w-8 h-8 rounded-lg flex items-center justify-center',
                    plan.highlighted ? 'bg-blue-500/30' : 'bg-white/8'
                  )}>
                    <Icon size={15} className={plan.highlighted ? 'text-blue-300' : 'text-neutral-400'} />
                  </div>
                  <div>
                    <p className="font-bold text-sm text-white">{plan.name}</p>
                    <p className="text-[11px] text-neutral-500">{plan.info}</p>
                  </div>
                </div>
                <div className="flex items-end gap-1">
                  <span className="text-3xl font-black text-white">{price === 0 ? '0' : price} zł</span>
                  {price > 0 && (
                    <span className="text-neutral-500 text-sm mb-0.5">
                      /{frequency === 'monthly' ? 'mc' : 'rok'}
                    </span>
                  )}
                </div>
                {frequency === 'yearly' && savingPct > 0 && (
                  <p className="text-xs text-neutral-500 mt-0.5">
                    zamiast {plan.price.monthly * 12} zł/rok
                  </p>
                )}
              </div>

              {/* Features */}
              <div className="flex-1 p-5 space-y-3">
                {plan.features.map((f, i) => (
                  <div key={i} className="flex items-start gap-2.5">
                    <CheckCircle
                      size={14}
                      className={cn(
                        'mt-0.5 flex-shrink-0',
                        plan.highlighted ? 'text-blue-400' : 'text-neutral-500'
                      )}
                    />
                    <span
                      className="text-xs text-neutral-300 leading-snug"
                      title={f.tooltip}
                    >
                      {f.text}
                      {f.tooltip && (
                        <span className="ml-1 text-neutral-600 cursor-help underline decoration-dashed decoration-neutral-600">
                          ?
                        </span>
                      )}
                    </span>
                  </div>
                ))}
              </div>

              {/* CTA */}
              <div className={cn('p-4 border-t', plan.highlighted ? 'border-blue-500/20' : 'border-white/6')}>
                {/* Plan darmowy nie jest do kupienia — nigdy nie dostaje przycisku,
                    inaczej „Aktualny plan" świeci się także u kogoś z Premium */}
                {isCurrent || plan.tierKey === 'free' ? (
                  <div className="w-full py-2.5 rounded-xl text-center text-sm font-semibold text-neutral-500 border border-white/8">
                    {isCurrent ? 'Aktualny plan' : 'Dostępny bez opłat'}
                  </div>
                ) : (
                  <button
                    onClick={() => onSelect?.(plan.tierKey, frequency)}
                    className={cn(
                      'w-full py-2.5 rounded-xl text-sm font-bold transition-all',
                      plan.highlighted
                        ? 'bg-blue-600 hover:bg-blue-500 text-white shadow shadow-blue-500/30'
                        : 'bg-white/8 hover:bg-white/12 text-white border border-white/10'
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

      <div className="text-center text-xs text-neutral-600 space-y-1.5">
        <p>
          Ceny brutto w PLN · Płatność z góry za wybrany okres · <strong className="text-neutral-500">bez automatycznego odnawiania</strong>
          {' '}· Dostęp aktywowany od razu po potwierdzeniu płatności
        </p>
        <p>
          Bezpieczne płatności Przelewy24 (BLIK, karta, przelew online) · Faktury dla firm: biuro@lumargo.pl
          {' '}· Plan „Firma lokalna" to usługa B2B (§ 11 Regulaminu)
        </p>
        <p>
          Szczegóły: <a href="/regulamin" className="text-neutral-500 hover:text-blue-400 underline">Regulamin</a>
          {' · '}
          <a href="/polityka-prywatnosci" className="text-neutral-500 hover:text-blue-400 underline">Polityka prywatności</a>
        </p>
      </div>
    </div>
  );
};

export default PricingCards;
