import React, { useRef, useEffect, useState } from 'react';
import { ArrowUp, ChevronRight, CornerDownRight } from 'lucide-react';
import { Tag } from './simple/tv';
import { useChat } from '../src/hooks/useChat';
import { useVoiceInput } from '../src/hooks/useVoiceInput';
import { VoiceMicButton } from './VoiceMicButton';
import ChatMessage from './ChatMessage';
import ChatLimitPrompt from './ChatLimitPrompt';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

interface ChatInterfaceProps {
  initialQuery?: string;
  onNavigate?: (section: string) => void;
  selectedAgent: string | null;
  headerContent?: React.ReactNode;
  onInitialQuerySent?: () => void;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({
  initialQuery,
  onNavigate,
  selectedAgent,
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
    fetch(`${API_URL}/chat/suggestions`)
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
    // Pusty czat nie przewija: inaczej wejście na stronę zjeżdżało pod główkę
    // i mieszkaniec nie widział, z kim rozmawia
    if (messages.length === 0) return;
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

      <div className="mx-auto w-full max-w-3xl space-y-6 px-4 pb-4 md:px-8">
        {messages.length === 0 && (questionOfDay || suggestions.length > 0) && !limitReached && (
          <div className="space-y-4">
            {/* Pytanie dnia */}
            {questionOfDay && (
              <section aria-label="Pytanie dnia" className="flex flex-col">
                <Tag as="h2">Pytanie dnia</Tag>
                <button
                  onClick={() => sendMessage(questionOfDay)}
                  className="flex min-h-[52px] w-full items-center justify-between gap-3 border-t-2 border-tv-blue bg-tv-panel px-4 py-3 text-left text-[16px] font-semibold leading-snug text-white transition-colors hover:bg-tv-panel2"
                >
                  {questionOfDay}
                  <ChevronRight size={18} className="shrink-0 text-tv-bluesoft" aria-hidden />
                </button>
              </section>
            )}

            {/* Przykładowe pytania */}
            {suggestions.length > 0 && (
              <section aria-label="Przykładowe pytania" className="flex flex-col">
                <Tag as="h2" tone="seam">Przykładowe pytania</Tag>
                <div className="grid grid-cols-1 gap-px border-t border-tv-seam bg-tv-seam md:grid-cols-2">
                  {suggestions.slice(0, 4).map((s, i) => (
                    <button
                      key={i}
                      onClick={() => sendMessage(s)}
                      className="flex min-h-[48px] items-center gap-2 bg-tv-panel px-4 py-2.5 text-left text-[15px] leading-snug text-tv-paper transition-colors hover:bg-tv-panel2 hover:text-white"
                    >
                      <CornerDownRight size={14} className="shrink-0 text-tv-muted" aria-hidden />
                      {s}
                    </button>
                  ))}
                </div>
              </section>
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
        <div ref={bottomRef} className="h-32" />
      </div>

      {/* ── FIXED INPUT BAR — przyklejony powyżej BottomTabBar (64 px + bezpieczny
          margines iPhone'a); na desktopie belki nie ma, więc pole leży przy krawędzi ── */}
      <div className="fixed bottom-[calc(4rem+env(safe-area-inset-bottom,0px))] left-0 right-0 z-40 border-t border-tv-seam bg-tv-ink px-4 pb-2 pt-3 lg:bottom-0 lg:pb-3">
        <div className="mx-auto max-w-3xl md:px-8">
          <form
            onSubmit={e => { e.preventDefault(); handleSend(); }}
            className="flex min-h-[60px] items-center gap-1 border-2 border-tv-seam bg-tv-panel pl-4 transition-colors focus-within:border-tv-paper"
          >
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder={limitReached ? 'Limit dzienny wyczerpany...' : 'Zapytaj o cokolwiek...'}
              aria-label="Pytanie do asystenta"
              disabled={isLoading || limitReached}
              className="min-w-0 flex-1 bg-transparent py-3 text-[17px] text-white outline-none placeholder:text-tv-muted focus-visible:outline-none disabled:opacity-60"
            />

            <VoiceMicButton
              speech={speech}
              onTranscript={(text) => setInput(text)}
              iconSize={20}
              className={`flex h-11 w-11 shrink-0 items-center justify-center transition-colors ${
                speech.isListening ? 'text-tv-red' : 'text-tv-muted hover:text-white'
              }`}
            />

            <button
              type="submit"
              disabled={isLoading || !input.trim() || limitReached}
              aria-label="Wyślij"
              className="font-cond flex min-h-[56px] w-14 shrink-0 items-center justify-center self-stretch bg-tv-blue text-white transition-colors hover:bg-[#3a63ff] disabled:cursor-not-allowed disabled:bg-tv-seam disabled:text-tv-muted lg:w-auto lg:px-6"
            >
              <ArrowUp size={18} className="lg:hidden" aria-hidden />
              <span className="hidden text-[17px] font-extrabold uppercase tracking-wide lg:inline">Wyślij</span>
            </button>
          </form>

          {/* Oznaczenie AI — obowiązek informacyjny z art. 50 AI Act (UE 2024/1689) */}
          {/* Na telefonie krócej (pełne zdanie łamało się na 3 linie i belka z polem
              zajmowała 141 px) — ale oba elementy zostają: że to AI i że to nie porada */}
          <p className="mt-1.5 px-1 text-[13px] leading-snug text-tv-muted">
            <span className="md:hidden">Asystent AI: może się mylić, to nie porada prawna ani urzędowa.</span>
            <span className="hidden md:inline">
              Rozmawiasz z asystentem AI — odpowiedzi są generowane automatycznie
              i mogą zawierać błędy. Nie stanowią porady prawnej ani urzędowej.
            </span>
          </p>
        </div>
      </div>
    </>
  );
};

export default ChatInterface;
