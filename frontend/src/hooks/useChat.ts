import { useState, useCallback, useRef } from 'react';
import { getAccessToken, refreshAccessToken } from '../services/authApi';
import { track } from '../services/analytics';

/** Returns a fresh access token, refreshing if near expiry or expired. */
async function getFreshToken(): Promise<string | null> {
  const token = getAccessToken();
  if (!token) return null;
  // Decode JWT payload (no signature check — just to read expiry)
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const expiresIn = (payload.exp * 1000) - Date.now();
    // Refresh if < 5 minutes remaining
    if (expiresIn < 5 * 60 * 1000) {
      const ok = await refreshAccessToken();
      return ok ? getAccessToken() : null;
    }
  } catch {
    // Invalid token format — try refresh anyway
    const ok = await refreshAccessToken();
    return ok ? getAccessToken() : null;
  }
  return token;
}

// Fallback musi zawierać /api — endpointy doklejają samą ścieżkę („/events").
// Bez tego `npm run dev` bez jawnej zmiennej trafiał w :8000/events → 404:
// vite.config ma envDir wskazujący ../backend, więc frontend/.env NIE jest
// wczytywany, a produkcja działa tylko dlatego, że deploy-frontend.sh podaje
// VITE_API_URL w linii poleceń.
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export interface ChatSource {
  title: string;
  url: string;
  source_name?: string;
}

/**
 * Krok pracy agenta pokazywany na żywo pod pytaniem.
 *
 * Nie jest to ozdoba ładowania: `detail` niesie argumenty wywołania
 * („Rybno · 3 dni”), więc mieszkaniec widzi, CZEGO agent szuka — i poznaje
 * moment, w którym został źle zrozumiany, zanim przeczyta odpowiedź nie na
 * temat. `state` rozdziela trzy sytuacje, które dla czytającego znaczą co
 * innego: znalazłem / nie ma tego w danych / narzędzie zawiodło.
 */
export interface AgentStep {
  message: string;
  /** Nazwa narzędzia — łączy krok „w toku” z jego wynikiem */
  tool?: string;
  state?: 'running' | 'done' | 'empty' | 'error' | 'warning' | 'info';
  /** Argumenty w formie czytelnej: „Rybno · 3 dni” */
  detail?: string;
  /** Co narzędzie zastało: „prognoza Rybno: 3 dni”, „kalendarz pusty” */
  result?: string;
}

export interface ForecastDay {
  dzien: string;          // "dziś" / "jutro" / "w czwartek"
  data: string;           // DD.MM.YYYY
  temp_min_c: number;
  temp_max_c: number;
  opis: string;
  szansa_opadow_proc: number;
  opad_mm: number;
  wiatr_max_m_s?: number | null;
  icon?: string;          // kod ikony OpenWeather (np. "04d")
}

export interface ChartConfig {
  chart_type: 'trend' | 'kpi' | 'forecast';
  title: string;
  // trend
  data?: Array<{ year: number; value: number }>;
  // kpi
  current_value?: number;
  national_value?: number;
  year?: number;
  trend_pct?: number | null;
  sparkline?: Array<{ year: number; value: number }>;
  // forecast — prognoza z narzędzia `weather_forecast`
  days?: ForecastDay[];
  uv_index?: number | null;
}

export interface ChatMessageData {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSource[];
  agent_name?: string;
  isStreaming?: boolean;
  chartData?: ChartConfig[];
  /** Widoczne kroki pracy agenta — co sprawdza, czego szuka, co zastał */
  steps?: AgentStep[];
  /** Pytania pomocnicze — klikalne chipy pod odpowiedzią */
  followups?: string[];
  /** ID wiadomości w bazie — potrzebne do ocen 👍/👎 */
  dbId?: number;
}

/** Wyślij ocenę odpowiedzi agenta (👍 = 1, 👎 = -1). Fire-and-forget. */
export async function sendChatFeedback(messageId: number, rating: 1 | -1): Promise<boolean> {
  try {
    const token = getAccessToken();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(`${API_URL}/chat/feedback`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ message_id: messageId, rating }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export interface LimitInfo {
  tier: 'anonymous' | 'free' | 'premium';
  limit: number;
  used: number;
  reset_at: string;
}

interface UseChatOptions {
  agentName?: string;
}

export function useChat(options: UseChatOptions = {}) {
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [limitReached, setLimitReached] = useState(false);
  const [limitInfo, setLimitInfo] = useState<LimitInfo | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(async (text: string) => {
    // Sama liczba pytań, bez treści — ta leży w `chat_messages` i ma własną
    // retencję. Cztery sierpniowe konta zadały łącznie jedno pytanie, więc to
    // ten licznik ma pokazać, czy asystent w ogóle jest używany.
    track('assistant_question', { section: 'assistant' });
    if (!text.trim() || isLoading || limitReached) return;

    const userMsg: ChatMessageData = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
    };
    const assistantId = (Date.now() + 1).toString();
    const assistantMsg: ChatMessageData = {
      id: assistantId,
      role: 'assistant',
      content: '',
      isStreaming: true,
    };

    setMessages(prev => [...prev, userMsg, assistantMsg]);
    setIsLoading(true);

    abortRef.current = new AbortController();

    try {
      const token = await getFreshToken();
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const response = await fetch(`${API_URL}/chat/message`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          message: text,
          conversation_id: token ? conversationId : null,
          agent_name: options.agentName || null,
          stream: true,
        }),
        signal: abortRef.current.signal,
      });

      if (response.status === 429) {
        // Remove the optimistic assistant message
        setMessages(prev => prev.filter(m => m.id !== assistantId));
        try {
          const errorData = await response.json();
          const detail = errorData.detail || {};
          setLimitInfo({
            tier: detail.tier || 'free',
            limit: detail.limit || 0,
            used: detail.used || 0,
            reset_at: detail.reset_at || '',
          });
        } catch {
          setLimitInfo({ tier: 'free', limit: 0, used: 0, reset_at: '' });
        }
        setLimitReached(true);
        return;
      }

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(trimmed.slice(6));
            if (data.type === 'start') {
              setConversationId(data.conversation_id);
            } else if (data.type === 'status') {
              // Wynik narzędzia DOMYKA krok „w toku”, zamiast dopisywać drugi
              // wiersz o tym samym. Lista ma być zapisem pracy, nie logiem.
              setMessages(prev => prev.map(m => {
                if (m.id !== assistantId) return m;
                const steps = [...(m.steps || [])];
                const incoming: AgentStep = {
                  message: data.message,
                  tool: data.tool,
                  state: data.state || 'info',
                  detail: data.detail || undefined,
                };
                // Pytanie przejmuje inny agent (etap 7). `discard_text` znaczy,
                // że poprzedni agent zdążył coś napisać, zanim się wycofał —
                // najczęściej początek odmowy („Niestety nie mam…”). Odpowiedź
                // napisze teraz ktoś inny, więc bufor musi pójść do kosza:
                // inaczej mieszkaniec czyta odmowę sklejoną z odpowiedzią.
                // Backend robi dokładnie to samo przy zapisie do bazy.
                if (data.handoff) {
                  const cleared = data.discard_text ? '' : m.content;
                  return { ...m, content: cleared, steps: [...steps, incoming] };
                }
                if (data.tool && data.state && data.state !== 'running') {
                  const idx = steps.map(s => s.tool === data.tool && s.state === 'running')
                                   .lastIndexOf(true);
                  if (idx !== -1) {
                    // Etykieta „co sprawdzam” zostaje, dochodzi wynik.
                    steps[idx] = { ...steps[idx], state: incoming.state, result: incoming.message };
                    return { ...m, steps };
                  }
                }
                return { ...m, steps: [...steps, incoming] };
              }));
            } else if (data.type === 'followups') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, followups: data.questions } : m
              ));
            } else if (data.type === 'saved') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, dbId: data.message_id } : m
              ));
            } else if (data.type === 'chunk') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, content: m.content + data.content } : m
              ));
            } else if (data.type === 'sources') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, sources: data.sources } : m
              ));
            } else if (data.type === 'chart_data') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, chartData: data.charts } : m
              ));
            } else if (data.type === 'done') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, isStreaming: false, agent_name: data.agent_name } : m
              ));
            } else if (data.type === 'error') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, content: `Błąd: ${data.message}`, isStreaming: false } : m
              ));
            }
          } catch {}
        }
      }
    } catch (err: any) {
      if (err.name === 'AbortError') return;
      setMessages(prev => prev.map(m =>
        m.id === assistantId
          ? { ...m, content: 'Wystąpił błąd połączenia. Spróbuj ponownie.', isStreaming: false }
          : m
      ));
    } finally {
      setIsLoading(false);
      setMessages(prev => prev.map(m =>
        m.id === assistantId ? { ...m, isStreaming: false } : m
      ));
    }
  }, [isLoading, conversationId, options.agentName, limitReached]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setConversationId(null);
    setLimitReached(false);
    setLimitInfo(null);
    abortRef.current?.abort();
  }, []);

  return { messages, isLoading, sendMessage, clearMessages, conversationId, limitReached, limitInfo };
}
