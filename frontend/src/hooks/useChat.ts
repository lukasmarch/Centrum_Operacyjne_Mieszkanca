import { useState, useCallback, useRef } from 'react';
import { getAccessToken } from '../services/authApi';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface ChatSource {
  title: string;
  url: string;
  source_name?: string;
}

export interface ChartConfig {
  chart_type: 'trend' | 'kpi';
  title: string;
  // trend
  data?: Array<{ year: number; value: number }>;
  // kpi
  current_value?: number;
  national_value?: number;
  year?: number;
  trend_pct?: number | null;
  sparkline?: Array<{ year: number; value: number }>;
}

export interface ChatMessageData {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSource[];
  agent_name?: string;
  isStreaming?: boolean;
  chartData?: ChartConfig[];
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
      const token = getAccessToken();
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
