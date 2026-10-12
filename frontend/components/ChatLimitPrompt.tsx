import React from 'react';
import { LimitInfo } from '../src/hooks/useChat';
import PricingCards from './PricingCards';
import { RowLink, Tag } from './simple/tv';

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
    // Żółć = „stan, o którym trzeba wiedzieć” — plakietka nad pasem, bez ikony w kafelku
    <section aria-label="Limit pytań" className="mt-2 flex w-full flex-col">
      <Tag as="h2" tone="yellow">
        Limit {limitInfo.limit} {limitInfo.limit === 1 ? 'pytania' : 'pytań'} wyczerpany
      </Tag>
      <div className="border-t-2 border-tv-yellow bg-tv-panel p-4 md:p-5">
        <p className="text-[15px] text-tv-muted">
          Limit odnowi się {formatResetTime(limitInfo.reset_at)}
        </p>

        {/* Anonymous login hint */}
        {isAnonymous && (
          <div className="mt-3 border-t border-tv-seam pt-3">
            <p className="text-[15px] leading-snug text-[#d7dbe8]">
              Zaloguj się i zyskaj <strong className="text-white">5 pytań dziennie za darmo</strong> — bez żadnych kosztów.
            </p>
            <RowLink onClick={() => onNavigate?.('login')}>Zaloguj się</RowLink>
          </div>
        )}

        {/* Pricing cards */}
        <div className="mt-4">
          <PricingCards
            currentTier={isAnonymous ? 'anonymous' : 'free'}
            onSelect={handlePlanSelect}
          />
        </div>
      </div>
    </section>
  );
};

export default ChatLimitPrompt;
