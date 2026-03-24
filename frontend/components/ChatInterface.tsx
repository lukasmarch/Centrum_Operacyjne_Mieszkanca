import React, { useRef, useEffect, useState } from 'react';
import { Send, Mic } from 'lucide-react';
import { useChat } from '../src/hooks/useChat';
import ChatMessage from './ChatMessage';
import ChatLimitPrompt from './ChatLimitPrompt';

interface ChatInterfaceProps {
  initialQuery?: string;
  onNavigate?: (section: string) => void;
  selectedAgent: string | null;
  activeAgentColor?: string;
  headerContent?: React.ReactNode;
  onInitialQuerySent?: () => void;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({
  initialQuery,
  onNavigate,
  selectedAgent,
  activeAgentColor = 'from-blue-600 to-violet-600',
  headerContent,
  onInitialQuerySent,
}) => {
  const [input, setInput] = useState('');
  const { messages, isLoading, sendMessage, limitReached, limitInfo } = useChat({
    agentName: selectedAgent || undefined,
  });
  const bottomRef = useRef<HTMLDivElement>(null);
  const lastSentQuery = useRef('');

  useEffect(() => {
    if (initialQuery && initialQuery !== lastSentQuery.current) {
      lastSentQuery.current = initialQuery;
      sendMessage(initialQuery);
      onInitialQuerySent?.();
    }
  }, [initialQuery]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim() || isLoading) return;
    sendMessage(input.trim());
    setInput('');
  };

  return (
    <>
      {/* ── HEADER + MESSAGES — naturalna strona, bez wewnętrznego scrolla ── */}
      {headerContent}

      <div className="max-w-7xl mx-auto w-full px-4 md:px-8 pb-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center w-full py-16 text-center">
            <p className="text-neutral-600 text-sm max-w-xs leading-relaxed">
              Zadaj pytanie o gminę Rybno — wiadomości, urzędy, statystyki lub wydarzenia.
            </p>
          </div>
        )}
        {messages.map(msg => (
          <ChatMessage key={msg.id} message={msg} />
        ))}
        {limitReached && limitInfo && (
          <ChatLimitPrompt limitInfo={limitInfo} onNavigate={onNavigate} />
        )}
        {/* Dodatkowy spacer żeby treść nie chowała się za fixed input */}
        <div ref={bottomRef} className="h-20" />
      </div>

      {/* ── FIXED INPUT BAR — przyklejony powyżej BottomTabBar ── */}
      <div
        className="fixed bottom-16 left-0 right-0 z-40 px-4 pb-4 pt-6"
        style={{
          background: 'linear-gradient(to top, rgba(5,8,15,1) 50%, rgba(5,8,15,0) 100%)',
        }}
      >
        {/* Dopasowanie szerokości do max-w-7xl */}
        <div className="max-w-7xl mx-auto">
          <div
            className="flex items-center gap-2 rounded-full px-4 py-2.5"
            style={{
              background: 'rgba(255,255,255,0.05)',
              border: 'none',
              outline: 'none',
            }}
          >
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSend()}
              placeholder={limitReached ? 'Limit dzienny wyczerpany...' : 'Zapytaj o cokolwiek...'}
              disabled={isLoading || limitReached}
              className="flex-1 bg-transparent text-neutral-100 placeholder-neutral-600 focus:outline-none text-sm disabled:opacity-50"
            />

            <button
              type="button"
              className="shrink-0 text-neutral-600 hover:text-neutral-400 transition-colors"
              aria-label="Mikrofon"
            >
              <Mic size={16} />
            </button>

            <button
              onClick={handleSend}
              disabled={isLoading || !input.trim() || limitReached}
              aria-label="Wyślij"
              className={`shrink-0 w-8 h-8 rounded-full bg-gradient-to-br ${activeAgentColor} flex items-center justify-center disabled:opacity-30 disabled:cursor-not-allowed transition-all shadow-md hover:shadow-lg hover:scale-105`}
            >
              <Send size={13} className="text-white translate-x-px" />
            </button>
          </div>
        </div>
      </div>
    </>
  );
};

export default ChatInterface;
