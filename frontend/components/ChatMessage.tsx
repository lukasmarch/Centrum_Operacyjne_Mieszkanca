import React, { useState } from 'react';
import {
  Bot, BarChart3, Newspaper, Landmark, ShieldAlert, Map, CalendarDays,
  Check, ThumbsUp, ThumbsDown, CornerDownRight,
} from 'lucide-react';
import { ChatMessageData, ChartConfig, sendChatFeedback } from '../src/hooks/useChat';
import { useAuth } from '../src/context/AuthContext';
import SourceChip from './SourceChip';
import TrendChart from './gus/charts/TrendChart';

interface ChatMessageProps {
  message: ChatMessageData;
  /** Klik w chip pytania pomocniczego — wysyła je jako nową wiadomość */
  onFollowUp?: (question: string) => void;
  /** Chipy pytań pomocniczych pokazujemy tylko przy ostatniej odpowiedzi */
  showFollowups?: boolean;
}

// Agent images – must match frontend/public/agents/
const AGENT_IMAGES: Record<string, string> = {
  redaktor: '/agents/redaktor.png',
  urzednik: '/agents/urzednik.jpeg',
  straznik: '/agents/straznik.jpeg',
  przewodnik: '/agents/przewodnik.png',
  organizator: '/agents/organizator.jpeg',
};

const AGENT_COLORS: Record<string, string> = {
  redaktor: 'from-sky-500 to-blue-700',
  urzednik: 'from-amber-500 to-orange-700',
  straznik: 'from-red-500 to-rose-700',
  przewodnik: 'from-emerald-500 to-teal-700',
  organizator: 'from-purple-500 to-fuchsia-700',
  gus_analityk: 'from-cyan-500 to-blue-700',
};

const AGENT_ICONS: Record<string, React.ReactNode> = {
  redaktor: <Newspaper size={14} />,
  urzednik: <Landmark size={14} />,
  straznik: <ShieldAlert size={14} />,
  przewodnik: <Map size={14} />,
  organizator: <CalendarDays size={14} />,
  gus_analityk: <BarChart3 size={14} />,
};

// ── Markdown renderer ──────────────────────────────────────────────────────

function renderMarkdown(text: string): React.ReactNode {
  const paragraphs = text.split(/\n\n+/);
  return paragraphs.map((para, pi) => {
    const lines = para.split('\n');
    const nodes: React.ReactNode[] = [];
    let listItems: React.ReactNode[] = [];

    const flushList = () => {
      if (listItems.length > 0) {
        nodes.push(
          <ul key={`ul-${pi}-${nodes.length}`} className="list-disc list-inside space-y-0.5 my-1">
            {listItems}
          </ul>
        );
        listItems = [];
      }
    };

    lines.forEach((line, li) => {
      const headingMatch = line.match(/^(#{1,4})\s+(.+)/);
      const listMatch = line.match(/^[-•*]\s+(.+)/);
      const numberedMatch = line.match(/^\d+\.\s+(.+)/);

      if (headingMatch) {
        flushList();
        nodes.push(
          <p key={`h-${pi}-${li}`} className="font-bold text-neutral-100 mt-2 mb-0.5">
            {inlineMarkdown(headingMatch[2])}
          </p>
        );
      } else if (listMatch) {
        listItems.push(
          <li key={`li-${pi}-${li}`} className="text-neutral-200">
            {inlineMarkdown(listMatch[1])}
          </li>
        );
      } else if (numberedMatch) {
        listItems.push(
          <li key={`li-${pi}-${li}`} className="text-neutral-200">
            {inlineMarkdown(numberedMatch[1])}
          </li>
        );
      } else if (line.trim()) {
        flushList();
        nodes.push(<span key={`t-${pi}-${li}`}>{inlineMarkdown(line)}</span>);
        if (li < lines.length - 1) nodes.push(<br key={`br-${pi}-${li}`} />);
      }
    });

    flushList();
    if (nodes.length === 0) return null;
    return (
      <p key={`p-${pi}`} className="mb-2 last:mb-0">
        {nodes}
      </p>
    );
  });
}

function inlineMarkdown(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|\[[^\]]+\]\(https?:\/\/[^)]+\))/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={i} className="font-semibold text-white">
          {part.slice(2, -2)}
        </strong>
      );
    }
    const linkMatch = part.match(/^\[([^\]]+)\]\((https?:\/\/[^)]+)\)$/);
    if (linkMatch) {
      return (
        <a
          key={i}
          href={linkMatch[2]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-400 underline hover:text-blue-300 transition-colors"
        >
          {linkMatch[1]}
        </a>
      );
    }
    return part;
  });
}

// ── Mini KPI chart ─────────────────────────────────────────────────────────

const MiniKPI: React.FC<{ chart: ChartConfig }> = ({ chart }) => (
  <div className="bg-neutral-800/60 rounded-xl p-3 flex items-center justify-between gap-4">
    <div className="min-w-0">
      <p className="text-xs text-neutral-400 mb-1 truncate">{chart.title}</p>
      <p className="text-2xl font-bold text-white leading-none">
        {chart.current_value?.toLocaleString('pl-PL') ?? '—'}
      </p>
      {chart.trend_pct !== null && chart.trend_pct !== undefined && (
        <p className={`text-xs mt-1 ${chart.trend_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
          {chart.trend_pct >= 0 ? '▲' : '▼'} {Math.abs(chart.trend_pct)}% r/r
        </p>
      )}
    </div>
    {chart.national_value !== undefined && (
      <div className="text-right shrink-0">
        <p className="text-xs text-neutral-500">Śr. krajowa</p>
        <p className="text-sm text-neutral-300">{chart.national_value?.toLocaleString('pl-PL')}</p>
        <p className="text-xs text-neutral-500">{chart.year}</p>
      </div>
    )}
  </div>
);

// ── Avatar helpers ─────────────────────────────────────────────────────────

const UserAvatar: React.FC<{ avatarUrl?: string; fullName?: string }> = ({ avatarUrl, fullName }) => {
  if (avatarUrl) {
    return (
      <img
        src={avatarUrl}
        alt="Ty"
        className="w-8 h-8 rounded-full object-cover flex-shrink-0 border border-white/10"
      />
    );
  }
  const initials = fullName
    ? fullName.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : 'TY';
  return (
    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-600 to-violet-600 flex items-center justify-center text-white text-[11px] font-bold flex-shrink-0">
      {initials}
    </div>
  );
};

const AgentAvatar: React.FC<{ agentName?: string }> = ({ agentName }) => {
  const name = agentName || '';
  const imgSrc = AGENT_IMAGES[name];
  const color = AGENT_COLORS[name] || 'from-blue-600 to-violet-600';
  const icon = AGENT_ICONS[name] || <Bot size={14} />;

  if (imgSrc) {
    return (
      <img
        src={imgSrc}
        alt={name}
        className="w-8 h-8 rounded-full object-cover object-top flex-shrink-0 border border-white/10"
      />
    );
  }
  return (
    <div className={`w-8 h-8 rounded-full bg-gradient-to-br ${color} flex items-center justify-center text-white flex-shrink-0`}>
      {icon}
    </div>
  );
};

// ── Oceny 👍/👎 ────────────────────────────────────────────────────────────

const FeedbackButtons: React.FC<{ dbId: number }> = ({ dbId }) => {
  const [rated, setRated] = useState<1 | -1 | null>(null);

  const rate = (rating: 1 | -1) => {
    setRated(rating);
    sendChatFeedback(dbId, rating);
  };

  if (rated) {
    return (
      <p className="text-[11px] text-neutral-600 mt-1.5 pl-1">
        {rated === 1 ? 'Dziękujemy za ocenę! 🎉' : 'Dzięki — poprawimy się.'}
      </p>
    );
  }
  return (
    <div className="flex items-center gap-1.5 mt-1.5 pl-1">
      <span className="text-[11px] text-neutral-600 mr-1">Czy ta odpowiedź pomogła?</span>
      <button
        onClick={() => rate(1)}
        aria-label="Odpowiedź pomogła"
        className="p-1.5 rounded-lg text-neutral-500 hover:text-emerald-400 hover:bg-white/[0.05] transition-colors"
      >
        <ThumbsUp size={13} />
      </button>
      <button
        onClick={() => rate(-1)}
        aria-label="Odpowiedź nie pomogła"
        className="p-1.5 rounded-lg text-neutral-500 hover:text-red-400 hover:bg-white/[0.05] transition-colors"
      >
        <ThumbsDown size={13} />
      </button>
    </div>
  );
};

// ── Main component ─────────────────────────────────────────────────────────

const ChatMessage: React.FC<ChatMessageProps> = ({ message, onFollowUp, showFollowups = true }) => {
  const { user } = useAuth();

  if (message.role === 'user') {
    return (
      <div className="flex items-end justify-end gap-2">
        <div className="max-w-[78%] bg-blue-600 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm leading-relaxed shadow-md">
          {message.content}
        </div>
        <UserAvatar avatarUrl={user?.avatarUrl} fullName={user?.full_name} />
      </div>
    );
  }

  const hasCharts = message.chartData && message.chartData.length > 0 && !message.isStreaming;

  return (
    <div className="flex gap-2.5 items-end">
      <AgentAvatar agentName={message.agent_name} />

      <div className="flex-1 min-w-0">
        {message.agent_name && (
          <p className="text-[10px] text-neutral-500 mb-1 uppercase tracking-widest font-semibold pl-1">
            {message.agent_name.replace('_', '-')}.ai
          </p>
        )}

        {/* Widoczne kroki pracy agenta (wzorzec Perplexity) */}
        {message.steps && message.steps.length > 0 && (
          <div className="mb-1.5 pl-1 space-y-0.5">
            {message.steps.map((step, i) => {
              const isCurrent = message.isStreaming && !message.content && i === message.steps!.length - 1;
              return (
                <p key={i} className="flex items-center gap-1.5 text-[11px] text-neutral-500">
                  {isCurrent ? (
                    <span className="w-3 h-3 rounded-full border border-blue-400 border-t-transparent animate-spin shrink-0" />
                  ) : (
                    <Check size={12} className="text-emerald-500 shrink-0" />
                  )}
                  {step}
                </p>
              );
            })}
          </div>
        )}

        <div className="bg-neutral-900/80 border border-white/5 rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm text-neutral-200 leading-relaxed shadow-sm">
          {message.content ? (
            <>
              <div>{renderMarkdown(message.content)}</div>
              {message.isStreaming && (
                <span className="inline-block w-0.5 h-4 bg-blue-400 animate-pulse ml-0.5 align-middle" />
              )}
            </>
          ) : message.isStreaming ? (
            <span className="inline-flex gap-1 items-center py-0.5">
              <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:0ms]" />
              <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:150ms]" />
              <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:300ms]" />
            </span>
          ) : null}
        </div>

        {hasCharts && (
          <div className="mt-3 space-y-3">
            {message.chartData!.map((chart, i) => (
              <div key={i} className="bg-neutral-900/80 border border-white/5 rounded-2xl px-4 py-3 overflow-hidden">
                {chart.chart_type === 'trend' && chart.data && chart.data.length >= 2 && (
                  <TrendChart data={chart.data} title={chart.title} height={180} color="#3b82f6" />
                )}
                {chart.chart_type === 'kpi' && <MiniKPI chart={chart} />}
              </div>
            ))}
          </div>
        )}

        {message.sources && message.sources.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2 pl-1">
            {message.sources.map((source, i) => (
              <SourceChip key={i} source={source} />
            ))}
          </div>
        )}

        {/* Ocena odpowiedzi — po zapisaniu wiadomości w bazie */}
        {!message.isStreaming && message.content && message.dbId && (
          <FeedbackButtons dbId={message.dbId} />
        )}

        {/* Pytania pomocnicze — chipy zachęcające do kontynuowania rozmowy */}
        {showFollowups && !message.isStreaming && message.followups && message.followups.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2.5 pl-1">
            {message.followups.map((q, i) => (
              <button
                key={i}
                onClick={() => onFollowUp?.(q)}
                className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full
                  bg-blue-500/10 border border-blue-500/25 text-blue-300
                  hover:bg-blue-500/20 hover:border-blue-400/40 transition-colors text-left"
              >
                <CornerDownRight size={11} className="opacity-60 shrink-0" />
                {q}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;
