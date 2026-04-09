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

import React, { useState } from 'react';
import { Lock, TrendingUp, BarChart3, Brain, FileDown, Zap, ArrowRight } from 'lucide-react';
import { UserTier } from '../../../types';

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
        badgeColor: 'from-indigo-500 to-purple-500',
        title: 'Odblokuj pełną analizę statystyczną',
        description: 'Uzyskaj dostęp do 37 wskaźników GUS dla rejonu Rybno, szczegółowych trendów historycznych i porównań między gminami',
        features: [
          { icon: <BarChart3 size={18} />, text: '37 wskaźników GUS (vs 8 w Free)' },
          { icon: <TrendingUp size={18} />, text: '7 kategorii tematycznych z danymi' },
          { icon: <Zap size={18} />, text: 'Trendy historyczne (10-30 lat)' },
          { icon: <BarChart3 size={18} />, text: 'Porównania między gminami w powiecie' },
        ],
        buttonText: 'Zobacz plany subskrypcji',
        buttonColor: 'bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700',
      };
    } else {
      // Pro tier
      return {
        badge: 'Pro',
        badgeColor: 'from-amber-500 to-orange-500',
        title: 'Zaawansowane analizy AI + eksport danych',
        description: 'Pełny dostęp do 53 wskaźników GUS dla rejonu Rybno + AI insights + eksport do CSV',
        features: [
          { icon: <Brain size={18} />, text: 'AI Insights - automatyczne analizy trendów' },
          { icon: <FileDown size={18} />, text: 'Eksport danych do CSV' },
          { icon: <BarChart3 size={18} />, text: 'Wszystkie 53 wskaźniki GUS dla rejonu Rybno' },
          { icon: <Zap size={18} />, text: 'Historia pytań AI bez limitu' },
        ],
        buttonText: 'Zobacz plany subskrypcji',
        buttonColor: 'bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-700 hover:to-orange-700',
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

  return (
    <div className={`relative bg-gray-950/50 backdrop-blur-sm rounded-xl border border-gray-700/50 p-8 ${className}`}>
      {/* Lock icon overlay */}
      <div className="absolute top-4 right-4">
        <div className={`p-3 rounded-full bg-gradient-to-br ${content.badgeColor} shadow-lg shadow-purple-500/20`}>
          <Lock className="text-white" size={24} />
        </div>
      </div>

      {/* Tab switcher */}
      <div className="inline-flex items-center gap-1 mb-4 p-1 bg-gray-800/60 rounded-full border border-gray-700/50">
        <button
          onClick={() => setActiveTab('premium')}
          className={`px-4 py-1.5 rounded-full text-sm font-bold transition-all duration-200 ${
            activeTab === 'premium'
              ? 'bg-gradient-to-r from-indigo-500 to-purple-500 text-white shadow-md'
              : 'text-neutral-400 hover:text-neutral-200'
          }`}
        >
          Premium
        </button>
        <button
          onClick={() => setActiveTab('business')}
          className={`px-4 py-1.5 rounded-full text-sm font-bold transition-all duration-200 ${
            activeTab === 'business'
              ? 'bg-gradient-to-r from-amber-500 to-orange-500 text-white shadow-md'
              : 'text-neutral-400 hover:text-neutral-200'
          }`}
        >
          Pro
        </button>
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

      {/* CTA */}
      <div className="pt-6 border-t border-gray-700/50">
        <a
          href="?tab=subscription"
          onClick={(e) => {
            e.preventDefault();
            // Navigate to profile subscription tab
            window.dispatchEvent(new CustomEvent('navigate-to-subscription'));
          }}
          className={`inline-flex items-center gap-2 px-8 py-3 rounded-lg text-white font-bold shadow-lg transition-all transform hover:scale-105 ${content.buttonColor}`}
        >
          {content.buttonText}
          <ArrowRight size={18} />
        </a>
      </div>
    </div>
  );
};

export default GUSTierGate;
