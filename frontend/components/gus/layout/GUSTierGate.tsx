/**
 * GUSTierGate Component
 *
 * Paywall/Upsell component for tier-gated GUS features
 * Displays upgrade prompt when user tries to access premium/business content
 *
 * Used in:
 * - GUSOverview: Premium upsell after Free tier KPIs
 * - GUSSectionPage: Business upsell for AI insights
 * - GUSVariableDetail: Tier gate for restricted variables
 *
 * Features:
 * - Tier-specific messaging
 * - Feature highlights
 * - Call-to-action button
 * - Lock icon (płasko — bez rozmycia i gradientów, odświeżenie 10.2026)
 */

import React, { useState } from 'react';
import { Lock, TrendingUp, BarChart3, Brain, FileDown, Zap, ArrowRight } from 'lucide-react';
import { UserTier } from '../../../types';
import { Tag } from '../../simple/tv';

interface GUSTierGateProps {
  requiredTier: 'premium' | 'business';
  currentTier?: UserTier;
  context?: 'overview' | 'section' | 'variable' | 'insights';
  className?: string;
}

const GUSTierGate: React.FC<GUSTierGateProps> = ({
  requiredTier,
  context = 'overview',
  className = '',
}) => {
  const [activeTab, setActiveTab] = useState<'premium' | 'business'>(requiredTier);
  // Tier-specific content
  const getTierContent = () => {
    if (activeTab === 'premium') {
      return {
        badge: 'Premium',
        title: 'Odblokuj pełną analizę statystyczną',
        description: 'Uzyskaj dostęp do 37 wskaźników GUS dla rejonu Rybno, szczegółowych trendów historycznych i porównań między gminami',
        features: [
          { icon: <BarChart3 size={18} />, text: '37 wskaźników GUS (vs 8 w Free)' },
          { icon: <TrendingUp size={18} />, text: '7 kategorii tematycznych z danymi' },
          { icon: <Zap size={18} />, text: 'Trendy historyczne (10-30 lat)' },
          { icon: <BarChart3 size={18} />, text: 'Porównania między gminami w powiecie' },
        ],
        buttonText: 'Zobacz plany subskrypcji',
      };
    } else {
      // Pro tier
      return {
        badge: 'Pro',
        title: 'Zaawansowane analizy AI + eksport danych',
        description: 'Pełny dostęp do 53 wskaźników GUS dla rejonu Rybno + AI insights + eksport do CSV',
        features: [
          { icon: <Brain size={18} />, text: 'AI Insights - automatyczne analizy trendów' },
          { icon: <FileDown size={18} />, text: 'Eksport danych do CSV' },
          { icon: <BarChart3 size={18} />, text: 'Wszystkie 53 wskaźniki GUS dla rejonu Rybno' },
          { icon: <Zap size={18} />, text: 'Historia pytań AI bez limitu' },
        ],
        buttonText: 'Zobacz plany subskrypcji',
      };
    }
  };

  const content = getTierContent();

  // Context-specific additional text
  const getContextText = () => {
    switch (context) {
      case 'overview':
        return 'Widzisz tylko 8 podstawowych wskaźników. Przejdź na Premium, aby odblokować 37 wskaźników w 7 kategoriach.';
      case 'section':
        return 'Ta sekcja wymaga dostępu Premium. Odblokuj szczegółowe dane demograficzne, rynek pracy, finanse gminy i więcej.';
      case 'variable':
        return 'Ten wskaźnik jest dostępny tylko dla użytkowników Premium. Uzyskaj dostęp do pełnej historii i porównań.';
      case 'insights':
        return 'AI Insights są dostępne tylko w planie Pro. Otrzymuj automatyczne analizy trendów i predykcje.';
      default:
        return null;
    }
  };

  const tabClass = (active: boolean) =>
    `font-cond inline-flex min-h-[44px] items-center px-4 text-[15px] font-bold uppercase tracking-wide transition-colors ${
      active ? 'bg-tv-paper text-tv-ink' : 'bg-tv-panel2 text-tv-paper hover:text-white'
    }`;

  const contextText = getContextText();

  return (
    <section className={`relative border-t-2 border-tv-blue bg-tv-panel p-4 lg:p-6 ${className}`}>
      {/* Kłódka w kwadracie panelu — sama ikona, bez kolorowego kółka */}
      <div className="absolute right-4 top-4 flex h-11 w-11 items-center justify-center bg-tv-panel2" aria-hidden>
        <Lock className="text-tv-muted" size={20} />
      </div>

      {/* Tab switcher */}
      <div role="group" aria-label="Plan" className="mb-4 inline-flex gap-px bg-tv-seam">
        <button onClick={() => setActiveTab('premium')} aria-pressed={activeTab === 'premium'} className={tabClass(activeTab === 'premium')}>
          Premium
        </button>
        <button onClick={() => setActiveTab('business')} aria-pressed={activeTab === 'business'} className={tabClass(activeTab === 'business')}>
          Pro
        </button>
      </div>

      {/* Title and description */}
      <h3 className="font-cond mb-2 pr-14 text-[24px] font-extrabold leading-tight text-white lg:text-[28px]">
        {content.title}
      </h3>
      <p className="mb-4 max-w-[70ch] text-[15px] leading-relaxed text-[#d7dbe8]">
        {content.description}
      </p>

      {/* Context-specific text — żółć = kontekst */}
      {contextText && (
        <p className="mb-5 bg-tv-yellow px-4 py-3 text-[15px] leading-snug text-tv-ink">
          <strong>Wskazówka:</strong> {contextText}
        </p>
      )}

      {/* Features list */}
      <ul className="mb-5 grid grid-cols-1 gap-x-6 gap-y-2 md:grid-cols-2">
        {content.features.map((feature, index) => (
          <li key={index} className="flex items-center gap-3 text-[15px] text-tv-paper">
            <span className="shrink-0 text-tv-muted" aria-hidden>{feature.icon}</span>
            <span>{feature.text}</span>
          </li>
        ))}
      </ul>

      {/* CTA */}
      <div className="border-t border-tv-seam pt-5">
        <a
          href="?tab=subscription"
          onClick={(e) => {
            e.preventDefault();
            // Navigate to profile subscription tab
            window.dispatchEvent(new CustomEvent('navigate-to-subscription'));
          }}
          className="font-cond inline-flex min-h-[52px] items-center gap-2 bg-tv-blue px-6 text-[16px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff]"
        >
          {content.buttonText}
          <ArrowRight size={18} aria-hidden />
        </a>
      </div>
    </section>
  );
};

export default GUSTierGate;
