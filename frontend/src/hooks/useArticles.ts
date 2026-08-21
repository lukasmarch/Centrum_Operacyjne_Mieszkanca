import { useState, useEffect } from 'react';
import { Article } from '../../types';

// Backend API response
interface ArticleApiResponse {
  id: number;
  source_id: number;
  source_name: string | null;
  source_label: string | null;
  title: string;
  display_title: string | null;
  summary: string | null;
  url: string;
  image_url: string | null;
  author: string | null;
  published_at: string | null;
  category: string | null;
  tags: string[] | null;
  scraped_at: string;
  event_at: string | null;
  event_until: string | null;
  is_pinned: boolean;
}

// Fallback musi zawierać /api — endpointy doklejają samą ścieżkę („/events").
// Bez tego `npm run dev` bez jawnej zmiennej trafiał w :8000/events → 404:
// vite.config ma envDir wskazujący ../backend, więc frontend/.env NIE jest
// wczytywany, a produkcja działa tylko dlatego, że deploy-frontend.sh podaje
// VITE_API_URL w linii poleceń.
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

/**
 * Format scraped_at timestamp to readable format
 * Example: "2026-01-08T10:53:05.577167" -> "2h temu"
 */
function formatTimestamp(scrapedAt: string): string {
  const now = new Date();
  const scraped = new Date(scrapedAt);
  const diffMs = now.getTime() - scraped.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffMinutes = Math.floor(diffMs / (1000 * 60));

  if (diffMinutes < 60) {
    return `${diffMinutes}m temu`;
  } else if (diffHours < 24) {
    return `${diffHours}h temu`;
  } else {
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d temu`;
  }
}

interface UseArticlesOptions {
  limit?: number;
  perSource?: number;
  days?: number;
}

export function useArticles(options: UseArticlesOptions = {}) {
  const { limit = 50, perSource = 5, days = 2 } = options;

  const [articles, setArticles] = useState<Article[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchArticles = async () => {
      try {
        setLoading(true);
        const response = await fetch(
          `${API_URL}/articles?limit=${limit}&per_source=${perSource}&days=${days}`
        );

        if (!response.ok) {
          throw new Error('Nie udało się pobrać artykułów');
        }

        const data: ArticleApiResponse[] = await response.json();

        // Map backend data to frontend format
        // Nagłówek AI (display_title) zamiast tytułu kopiowanego ze źródła —
        // surowy title zostaje tylko jako fallback dla nieprzetworzonych artykułów
        const mappedArticles: Article[] = data.map(item => ({
          id: String(item.id),
          title: item.display_title || item.title,
          summary: item.summary || 'Brak opisu',
          source: item.source_name || 'Nieznane źródło',
          // Nazwy prywatnych profili FB nie eksponujemy — backend zwraca wtedy null,
          // atrybucją zostaje sam link „źródło ↗"
          sourceLabel: item.source_label ?? null,
          category: item.category || 'Wiadomości',
          timestamp: formatTimestamp(item.published_at || item.scraped_at),
          rawTimestamp: item.published_at || item.scraped_at,
          url: item.url,
          imageUrl: item.image_url || undefined,
          // Alert „na teraz" wg feed_policy.is_pinned_alert — liczony w backendzie
          isPinnedAlert: item.is_pinned || false,
          eventAt: item.event_at || undefined,
          eventUntil: item.event_until || undefined,
        }));

        setArticles(mappedArticles);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Błąd pobierania artykułów');
        setArticles(null);
      } finally {
        setLoading(false);
      }
    };

    fetchArticles();

    // Refresh every 5 minutes
    const interval = setInterval(fetchArticles, 5 * 60 * 1000);

    return () => clearInterval(interval);
  }, [limit, perSource, days]);

  return { articles, loading, error };
}

