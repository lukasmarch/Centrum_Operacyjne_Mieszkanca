import React, { useRef, useEffect, useState } from 'react';
import { Send, RotateCcw } from 'lucide-react';
import { useChat } from '../src/hooks/useChat';
import ChatMessage from './ChatMessage';
import ChatLimitPrompt from './ChatLimitPrompt';

interface ChatInterfaceProps {
  initialQuery?: string;
  onNavigate?: (section: string) => void;
}

const AGENT_OPTIONS = [
  { id: null, label: 'Auto', icon: '🤖' },
  { id: 'redaktor', label: 'Redaktor', icon: '📰' },
  { id: 'urzednik', label: 'Urzędnik', icon: '🏛️' },
  { id: 'straznik', label: 'Strażnik', icon: '🛡️' },
  { id: 'przewodnik', label: 'Przewodnik', icon: '🗺️' },
  { id: 'gus_analityk', label: 'GUS', icon: '📊' },
];

const ChatInterface: React.FC<ChatInterfaceProps> = ({ initialQuery, onNavigate }) => {
  const [input, setInput] = useState('');
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const { messages, isLoading, sendMessage, clearMessages, limitReached, limitInfo } = useChat({
    agentName: selectedAgent || undefined,
  });
  const bottomRef = useRef<HTMLDivElement>(null);
  const sentInitial = useRef(false);

  useEffect(() => {
    if (initialQuery && !sentInitial.current) {
      sentInitial.current = true;
      sendMessage(initialQuery);
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
    <div className="flex flex-col h-[calc(100dvh-200px)] min-h-[460px]">
      {/* Agent selector */}
      <div className="flex gap-2 mb-4 overflow-x-auto pb-1 scrollbar-hide">
        {AGENT_OPTIONS.map(agent => (
          <button
            key={String(agent.id)}
            onClick={() => setSelectedAgent(agent.id)}
            className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full border transition-all shrink-0 ${
              selectedAgent === agent.id
                ? 'bg-blue-600 border-blue-500 text-white'
                : 'bg-gray-900/60 border-white/5 text-neutral-400 hover:border-blue-500/40 hover:text-blue-400'
            }`}
          >
            <span>{agent.icon}</span>
            {agent.label}
          </button>
        ))}
        {messages.length > 0 && (
          <button
            onClick={clearMessages}
            className="ml-auto flex items-center gap-1.5 text-xs text-neutral-500 hover:text-red-400 px-3 py-1.5 rounded-full border border-white/5 hover:border-red-500/30 transition-all shrink-0"
          >
            <RotateCcw size={12} />
            Wyczyść
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center py-12">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-600 to-violet-600 flex items-center justify-center text-3xl mb-4 shadow-xl shadow-blue-500/20">
              🤖
            </div>
            <p className="text-neutral-400 text-sm max-w-xs">
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
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="mt-4 flex gap-3">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSend()}
          placeholder={limitReached ? 'Limit dzienny wyczerpany...' : 'Zadaj pytanie...'}
          disabled={isLoading || limitReached}
          className="flex-1 bg-gray-950/80 border border-gray-700/50/60 rounded-2xl px-5 py-3 text-neutral-100 placeholder-neutral-600 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 transition-all text-sm disabled:opacity-50"
        />
        <button
          onClick={handleSend}
          disabled={isLoading || !input.trim() || limitReached}
          className="shrink-0 bg-gradient-to-br from-blue-600 to-violet-600 hover:from-blue-500 hover:to-violet-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-2xl px-5 py-3 font-medium transition-all shadow-lg shadow-blue-900/30 flex items-center gap-2 text-sm"
        >
          <Send size={15} />
          <span className="hidden sm:inline">Wyślij</span>
        </button>
      </div>
    </div>
  );
};

export default ChatInterface;
