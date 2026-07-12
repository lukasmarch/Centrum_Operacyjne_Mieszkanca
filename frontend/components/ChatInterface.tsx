import React, { useRef, useEffect, useState } from 'react';
import { Send, Sparkles, CornerDownRight } from 'lucide-react';
import { useChat } from '../src/hooks/useChat';
import { useVoiceInput } from '../src/hooks/useVoiceInput';
import { VoiceMicButton } from './VoiceMicButton';
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
  const speech = useVoiceInput((text) => setInput(text));
  const { messages, isLoading, sendMessage, limitReached, limitInfo } = useChat({
    agentName: selectedAgent || undefined,
  });
  const bottomRef = useRef<HTMLDivElement>(null);
  const lastSentQuery = useRef('');

  // Pytanie dnia + sugestie — obniżają próg wejścia w pustym czacie
  const [questionOfDay, setQuestionOfDay] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);

  useEffect(() => {
    fetch('/api/chat/suggestions')
      .then(r => r.json())
      .then(data => {
        if (data.question_of_day) setQuestionOfDay(data.question_of_day);
        if (data.suggestions?.length) setSuggestions(data.suggestions);
      })
      .catch(() => {});
  }, []);

  // Chipy pytań pomocniczych tylko przy ostatniej odpowiedzi
  const lastAssistantId = [...messages].reverse().find(m => m.role === 'assistant')?.id;

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
          <div className="flex flex-col items-center justify-center w-full py-10 gap-5">
            <p className="text-neutral-600 text-sm max-w-xs leading-relaxed text-center">
              Zadaj pytanie o gminę Rybno — wiadomości, urzędy, statystyki lub wydarzenia.
            </p>

            {/* Pytanie dnia */}
            {questionOfDay && !limitReached && (
              <button
                onClick={() => sendMessage(questionOfDay)}
                className="w-full max-w-md text-left rounded-2xl px-5 py-4 transition-all
                  bg-gradient-to-r from-blue-500/15 to-violet-500/10
                  border border-blue-500/25 hover:border-blue-400/45 hover:from-blue-500/20"
              >
                <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-blue-400 mb-1.5">
                  <Sparkles size={11} /> Pytanie dnia
                </p>
                <p className="text-sm text-neutral-200 leading-snug">{questionOfDay}</p>
              </button>
            )}

            {/* Przykładowe pytania */}
            {suggestions.length > 0 && !limitReached && (
              <div className="flex flex-wrap justify-center gap-2 max-w-lg">
                {suggestions.slice(0, 4).map((s, i) => (
                  <button
                    key={i}
                    onClick={() => sendMessage(s)}
                    className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full
                      bg-white/[0.04] border border-white/10 text-neutral-400
                      hover:bg-white/[0.07] hover:text-neutral-200 transition-colors text-left"
                  >
                    <CornerDownRight size={11} className="opacity-50 shrink-0" />
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
        {messages.map(msg => (
          <ChatMessage
            key={msg.id}
            message={msg}
            onFollowUp={q => !isLoading && !limitReached && sendMessage(q)}
            showFollowups={msg.id === lastAssistantId && !isLoading}
          />
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

            <VoiceMicButton
              speech={speech}
              onTranscript={(text) => setInput(text)}
              iconSize={16}
              className={`shrink-0 transition-colors ${
                speech.isListening ? 'text-red-400' : 'text-neutral-600 hover:text-neutral-400'
              }`}
            />

            <button
              onClick={handleSend}
              disabled={isLoading || !input.trim() || limitReached}
              aria-label="Wyślij"
              className={`shrink-0 w-8 h-8 rounded-full bg-gradient-to-br ${activeAgentColor} flex items-center justify-center disabled:opacity-30 disabled:cursor-not-allowed transition-all shadow-md hover:shadow-lg hover:scale-105`}
            >
              <Send size={13} className="text-white translate-x-px" />
            </button>
          </div>

          {/* Oznaczenie AI — obowiązek informacyjny z art. 50 AI Act (UE 2024/1689) */}
          <p className="text-center text-[10px] text-neutral-600 mt-2 px-4">
            Rozmawiasz z asystentem AI — odpowiedzi są generowane automatycznie
            i mogą zawierać błędy. Nie stanowią porady prawnej ani urzędowej.
          </p>
        </div>
      </div>
    </>
  );
};

export default ChatInterface;
