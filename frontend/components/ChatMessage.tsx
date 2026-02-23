import React from 'react';
import { ChatMessageData } from '../src/hooks/useChat';
import SourceChip from './SourceChip';

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

  return (
    <div className="flex gap-3 items-start">
      <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-600 to-violet-600 flex items-center justify-center text-sm shrink-0 mt-0.5">
        {message.agent_name ? (AGENT_ICONS[message.agent_name] || '🤖') : '🤖'}
      </div>
      <div className="flex-1 min-w-0">
        {message.agent_name && (
          <p className="text-[10px] text-slate-500 mb-1 uppercase tracking-widest font-bold">
            {message.agent_name.replace('_', '-')}.ai
          </p>
        )}
        <div className="bg-slate-800/60 border border-white/5 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-slate-200 leading-relaxed">
          {message.content ? (
            <>
              {message.content}
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
