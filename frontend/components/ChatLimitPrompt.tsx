import React from 'react';
import { AlertTriangle, Zap, Infinity } from 'lucide-react';
import { LimitInfo } from '../src/hooks/useChat';

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

  return (
    <div className="mx-auto max-w-xl w-full mt-2">
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

        {/* Plan cards */}
        <div className="grid grid-cols-2 gap-3">
          {/* Premium card */}
          <div className="bg-gradient-to-br from-indigo-600/20 to-purple-600/20 border border-indigo-500/30 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <Zap size={14} className="text-indigo-400" />
              <span className="text-xs font-bold text-indigo-300 uppercase tracking-wide">Premium</span>
            </div>
            <p className="text-2xl font-bold text-neutral-100 mb-0.5">50</p>
            <p className="text-xs text-neutral-400 mb-3">pytań / dzień</p>
            <p className="text-xs font-semibold text-indigo-300">19 zł / mies.</p>
          </div>

          {/* Business card */}
          <div className="bg-gradient-to-br from-amber-600/20 to-orange-600/20 border border-amber-500/30 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <Infinity size={14} className="text-amber-400" />
              <span className="text-xs font-bold text-amber-300 uppercase tracking-wide">Business</span>
            </div>
            <p className="text-2xl font-bold text-neutral-100 mb-0.5">∞</p>
            <p className="text-xs text-neutral-400 mb-3">bez limitu</p>
            <p className="text-xs font-semibold text-amber-300">99 zł / mies.</p>
          </div>
        </div>

        {/* CTA */}
        <button
          onClick={() => onNavigate?.('premium')}
          className="mt-4 w-full py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-sm font-semibold transition-all shadow-lg shadow-indigo-900/30"
        >
          Wybierz plan i pisz dalej →
        </button>
      </div>
    </div>
  );
};

export default ChatLimitPrompt;
