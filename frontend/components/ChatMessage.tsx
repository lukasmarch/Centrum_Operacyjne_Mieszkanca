import React from 'react';
import { ChatMessageData, ChartConfig } from '../src/hooks/useChat';
import SourceChip from './SourceChip';
import TrendChart from './gus/charts/TrendChart';

interface ChatMessageProps {
  message: ChatMessageData;
}

const AGENT_ICONS: Record<string, string> = {
  redaktor: '📰',
  urzednik: '🏛️',
  gus_analityk: '📊',
  przewodnik: '🗺️',
  straznik: '🛡️',
};

function renderMarkdown(text: string): React.ReactNode {
  const paragraphs = text.split(/\n\n+/);
  return paragraphs.map((para, pi) => {
    const lines = para.split('\n');
    const nodes: React.ReactNode[] = [];
    let listItems: React.ReactNode[] = [];

    const flushList = () => {
      if (listItems.length > 0) {
        nodes.push(<ul key={`ul-${pi}-${nodes.length}`} className="list-disc list-inside space-y-0.5 my-1">{listItems}</ul>);
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
          <li key={`li-${pi}-${li}`} className="text-neutral-200">{inlineMarkdown(listMatch[1])}</li>
        );
      } else if (numberedMatch) {
        listItems.push(
          <li key={`li-${pi}-${li}`} className="text-neutral-200">{inlineMarkdown(numberedMatch[1])}</li>
        );
      } else if (line.trim()) {
        flushList();
        nodes.push(
          <span key={`t-${pi}-${li}`}>{inlineMarkdown(line)}</span>
        );
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
  // Split on **bold** and [text](url) links
  const parts = text.split(/(\*\*[^*]+\*\*|\[[^\]]+\]\(https?:\/\/[^)]+\))/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold text-white">{part.slice(2, -2)}</strong>;
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

const MiniKPI: React.FC<{ chart: ChartConfig }> = ({ chart }) => (
  <div className="bg-gray-700/50 rounded-xl p-3 flex items-center justify-between gap-4">
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

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed">
          {message.content}
        </div>
      </div>
    );
  }

  const hasCharts = message.chartData && message.chartData.length > 0 && !message.isStreaming;

  return (
    <div className="flex gap-3 items-start">
      <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-600 to-violet-600 flex items-center justify-center text-sm shrink-0 mt-0.5">
        {message.agent_name ? (AGENT_ICONS[message.agent_name] || '🤖') : '🤖'}
      </div>
      <div className="flex-1 min-w-0">
        {message.agent_name && (
          <p className="text-[10px] text-neutral-500 mb-1 uppercase tracking-widest font-bold">
            {message.agent_name.replace('_', '-')}.ai
          </p>
        )}
        <div className="bg-gray-900/60 border border-white/5 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-neutral-200 leading-relaxed">
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
              <div key={i} className="bg-gray-900/60 border border-white/5 rounded-2xl px-4 py-3 overflow-hidden">
                {chart.chart_type === 'trend' && chart.data && chart.data.length >= 2 && (
                  <TrendChart
                    data={chart.data}
                    title={chart.title}
                    height={180}
                    color="#3b82f6"
                  />
                )}
                {chart.chart_type === 'kpi' && (
                  <MiniKPI chart={chart} />
                )}
              </div>
            ))}
          </div>
        )}

        {message.sources && message.sources.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {message.sources.map((source, i) => (
              <SourceChip key={i} source={source} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;
