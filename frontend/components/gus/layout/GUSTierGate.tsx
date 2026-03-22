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
 * - Blur/lock visual effect
 */

import React from 'react';
import { Lock, TrendingUp, BarChart3, Brain, FileDown, Zap } from 'lucide-react';
import { UserTier } from '../../../types';

interface GUSTierGateProps {
  requiredTier: 'premium' | 'business';
  currentTier?: UserTier;
  context?: 'overview' | 'section' | 'variable' | 'insights';
  className?: string;
}

const GUSTierGate: React.FC<GUSTierGateProps> = ({
  requiredTier,
  currentTier = 'free',
  context = 'overview',
  className = '',
}) => {
  // Tier-specific content
  const getTierContent = () => {
    if (requiredTier === 'premium') {
      return {
        badge: 'Premium',
        badgeColor: 'from-indigo-500 to-purple-500',
        title: 'Odblokuj pełną analizę statystyczną',
        description: 'Uzyskaj dostęp do 57 wskaźników GUS, szczegółowych trendów historycznych i porównań między gminami',
        price: '19 PLN/mies.',
        features: [
          { icon: <BarChart3 size={18} />, text: '57 wskaźników GUS (vs 9 w Free)' },
          { icon: <TrendingUp size={18} />, text: '10 kategorii tematycznych z pełnymi danymi' },
          { icon: <Zap size={18} />, text: 'Trendy historyczne (10-30 lat)' },
          { icon: <BarChart3 size={18} />, text: 'Porównania między gminami w powiecie' },
        ],
        buttonText: 'Przejdź na Premium',
        buttonColor: 'bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700',
      };
    } else {
      // Business tier
      return {
        badge: 'Business',
        badgeColor: 'from-amber-500 to-orange-500',
        title: 'Zaawansowane analizy AI + eksport danych',
        description: 'Pełny dostęp do 88 wskaźników, AI insights generowane przez GPT-4, eksport do Excel/CSV',
        price: '99 PLN/mies.',
        features: [
          { icon: <Brain size={18} />, text: 'AI Insights - automatyczne analizy trendów' },
          { icon: <FileDown size={18} />, text: 'Eksport danych do Excel/CSV' },
          { icon: <BarChart3 size={18} />, text: 'Wszystkie 88 wskaźników GUS' },
          { icon: <Zap size={18} />, text: 'API access dla integracji' },
        ],
        buttonText: 'Przejdź na Business',
        buttonColor: 'bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-700 hover:to-orange-700',
      };
    }
  };

  const content = getTierContent();

  // Context-specific additional text
  const getContextText = () => {
    switch (context) {
      case 'overview':
        return 'Widzisz tylko 9 podstawowych wskaźników. Przejdź na Premium, aby odblokować pełne dashboardy dla 10 kategorii.';
      case 'section':
        return 'Ta sekcja wymaga dostępu Premium. Odblokuj szczegółowe dane demograficzne, rynek pracy, finanse gminy i więcej.';
      case 'variable':
        return 'Ten wskaźnik jest dostępny tylko dla użytkowników Premium. Uzyskaj dostęp do pełnej historii i porównań.';
      case 'insights':
        return 'AI Insights są dostępne tylko w planie Business. Otrzymuj automatyczne analizy trendów i predykcje.';
      default:
        return null;
    }
  };

  return (
    <div className={`relative bg-gray-950/50 backdrop-blur-sm rounded-xl border border-gray-700/50 p-8 ${className}`}>
      {/* Lock icon overlay */}
      <div className="absolute top-4 right-4">
        <div className={`p-3 rounded-full bg-gradient-to-br ${content.badgeColor} shadow-lg shadow-purple-500/20`}>
          <Lock className="text-white" size={24} />
        </div>
      </div>

      {/* Badge */}
      <div className="inline-block mb-4">
        <span
          className={`px-4 py-1.5 rounded-full text-white text-sm font-bold bg-gradient-to-r ${content.badgeColor} shadow-md`}
        >
          {content.badge}
        </span>
      </div>

      {/* Title and description */}
      <h3 className="text-2xl font-bold text-neutral-100 mb-2">
        {content.title}
      </h3>
      <p className="text-neutral-400 mb-4">
        {content.description}
      </p>

      {/* Context-specific text */}
      {getContextText() && (
        <div className="mb-6 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
          <p className="text-sm text-blue-300">
            💡 <strong>Wskazówka:</strong> {getContextText()}
          </p>
        </div>
      )}

      {/* Features list */}
      <div className="mb-6 grid grid-cols-1 md:grid-cols-2 gap-3">
        {content.features.map((feature, index) => (
          <div key={index} className="flex items-center gap-3 text-neutral-300">
            <div className={`p-2 rounded-lg bg-gradient-to-br ${content.badgeColor} bg-opacity-10`}>
              {feature.icon}
            </div>
            <span className="text-sm font-medium">{feature.text}</span>
          </div>
        ))}
      </div>

      {/* Pricing and CTA */}
      <div className="flex items-center justify-between pt-6 border-t border-gray-700/50/50">
        <div>
          <p className="text-sm text-neutral-500 mb-1">Cena</p>
          <p className="text-3xl font-bold text-neutral-100">{content.price}</p>
        </div>
        <button
          className={`px-8 py-3 rounded-lg text-white font-bold shadow-lg transition-all transform hover:scale-105 ${content.buttonColor}`}
          onClick={() => {
            // TODO: Navigate to upgrade page
            console.log(`Upgrade to ${requiredTier}`);
          }}
        >
          {content.buttonText}
        </button>
      </div>

      {/* Current tier info (if logged in) */}
      {currentTier !== 'free' && (
        <div className="mt-4 p-3 bg-gray-900 rounded-lg text-sm text-neutral-400 text-center">
          Twój obecny plan: <strong className="text-neutral-200 capitalize">{currentTier}</strong>
        </div>
      )}
    </div>
  );
};

export default GUSTierGate;
