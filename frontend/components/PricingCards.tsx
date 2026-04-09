import React, { useState } from 'react';
import { CheckCircle, Zap, Crown, BarChart2 } from 'lucide-react';
import { cn } from '../lib/utils';

type Frequency = 'monthly' | 'yearly';

interface Plan {
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

const PLANS: Plan[] = [
  {
    id: 'free',
    name: 'Dla Każdego',
    icon: Zap,
    info: 'Podstawowy dostęp do informacji lokalnych',
    tierKey: 'free',
    price: { monthly: 0, yearly: 0 },
    features: [
      { text: 'Wiadomości i artykuły lokalne' },
      { text: 'Pogoda i jakość powietrza' },
      { text: 'Harmonogram wywozu śmieci' },
      { text: 'Zgłoszenia 24h ze zdjęciem' },
      { text: 'Newsletter tygodniowy' },
      { text: '5 pytań AI dziennie' },
      { text: 'Podstawowe dane GUS (8 wskaźników)' },
    ],
    btnText: 'Aktualny plan',
  },
  {
    id: 'premium',
    name: 'Premium',
    icon: Crown,
    info: 'Dla świadomych mieszkańców gminy',
    tierKey: 'premium',
    highlighted: true,
    price: { monthly: 9.99, yearly: 84 },
    features: [
      { text: 'Wszystko z planu Free' },
      { text: 'Nieograniczone pytania AI' },
      { text: 'Newsletter dzienny (pon–pt)', tooltip: 'Poranny briefing o 6:30' },
      { text: 'Alerty push w czasie rzeczywistym', tooltip: 'Pożary, wypadki, awarie, smog' },
      { text: 'Proaktywny Asystent AI', tooltip: 'Powiadomienia bez pytania: jutro wywóz śmieci, mróz na drogach, nowe ogłoszenie BIP' },
      { text: '37 wskaźników GUS', tooltip: '7 kategorii: demografia, rynek pracy, finanse gminy, mieszkalnictwo, edukacja, zdrowie + dane powiatu działdowskiego' },
      { text: 'Personalizacja dashboardu' },
      { text: 'Brak reklam' },
    ],
    btnText: 'Wybierz Premium',
  },
  {
    id: 'pro',
    name: 'Pro',
    icon: BarChart2,
    info: 'Dla entuzjastów danych lokalnych',
    tierKey: 'business',
    price: { monthly: 19.99, yearly: 169 },
    features: [
      { text: 'Wszystko z planu Premium' },
      { text: '53 wskaźniki GUS', tooltip: 'Kompletne dane statystyczne dla rejonu Rybno (gmina + powiat działdowski)' },
      { text: 'Raporty PDF na żądanie', tooltip: 'AI generuje podsumowanie danych gminy' },
      { text: 'Eksport danych GUS (CSV)' },
      { text: 'Historia pytań AI bez limitu' },
      { text: 'Wcześniejszy dostęp do nowych funkcji' },
    ],
    btnText: 'Wybierz Pro',
  },
];

interface PricingCardsProps {
  currentTier: string;
  onSelect?: (tierId: string) => void;
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
                  -30%
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
                {isCurrent ? (
                  <div className="w-full py-2.5 rounded-xl text-center text-sm font-semibold text-neutral-500 border border-white/8">
                    Aktualny plan
                  </div>
                ) : (
                  <button
                    onClick={() => onSelect?.(plan.tierKey)}
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

      <p className="text-center text-xs text-neutral-600">
        Płatności bezpieczne · Anuluj w dowolnym momencie · Faktury VAT dostępne
      </p>
    </div>
  );
};

export default PricingCards;
