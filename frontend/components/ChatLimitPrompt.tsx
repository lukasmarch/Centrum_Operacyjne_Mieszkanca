import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { LimitInfo } from '../src/hooks/useChat';
import PricingCards from './PricingCards';

interface ChatLimitPromptProps {
  limitInfo: LimitInfo;
  onNavigate?: (section: string) => void;
}

const ChatLimitPrompt: React.FC<ChatLimitPromptProps> = ({ limitInfo, onNavigate }) => {
  const isAnonymous = limitInfo.tier === 'anonymous';

  const formatResetTime = (resetAt: string) => {
    if (!resetAt) return 'o północy';
    try {
      const d = new Date(resetAt);
      return `o ${d.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' })} (${d.toLocaleDateString('pl-PL')})`;
    } catch {
      return 'o północy';
    }
  };

  const handlePlanSelect = (tierId: string) => {
    if (isAnonymous) {
      onNavigate?.('login');
    } else {
      onNavigate?.('premium');
    }
  };

  return (
    <div className="mx-auto max-w-3xl w-full mt-2">
      <div className="bg-gray-900/60 border border-amber-500/30 rounded-2xl p-5 backdrop-blur-sm">
        {/* Header */}
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 rounded-xl bg-amber-500/15 border border-amber-500/20">
            <AlertTriangle size={18} className="text-amber-400" />
          </div>
          <div>
            <p className="text-sm font-semibold text-neutral-100">
              Limit {limitInfo.limit} {limitInfo.limit === 1 ? 'pytania' : 'pytań'} wyczerpany
            </p>
            <p className="text-xs text-neutral-500">
              Limit odnowi się {formatResetTime(limitInfo.reset_at)}
            </p>
          </div>
        </div>

        {/* Anonymous login hint */}
        {isAnonymous && (
          <div className="mb-4 p-3 bg-blue-500/10 border border-blue-500/20 rounded-xl">
            <p className="text-xs text-blue-300">
              Zaloguj się i zyskaj <strong>5 pytań dziennie za darmo</strong> — bez żadnych kosztów.
            </p>
            <button
              onClick={() => onNavigate?.('login')}
              className="mt-2 text-xs font-medium text-blue-400 hover:text-blue-300 underline underline-offset-2 transition-colors"
            >
              Zaloguj się →
            </button>
          </div>
        )}

        {/* Pricing cards */}
        <PricingCards
          currentTier={isAnonymous ? 'anonymous' : 'free'}
          onSelect={handlePlanSelect}
        />
      </div>
    </div>
  );
};

export default ChatLimitPrompt;
