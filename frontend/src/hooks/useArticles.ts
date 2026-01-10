import { useState, useEffect } from 'react';
import { Article } from '../../types';

// Backend API response
interface ArticleApiResponse {
  id: number;
  source_id: number;
  source_name: string | null;
  title: string;
  summary: string | null;
  url: string;
  image_url: string | null;
  author: string | null;
  published_at: string | null;
  category: string | null;
  tags: string[] | null;
  scraped_at: string;
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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

export function useArticles(limit: number = 3) {
  const [articles, setArticles] = useState<Article[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchArticles = async () => {
      try {
        setLoading(true);
        const response = await fetch(`${API_URL}/api/articles?limit=${limit}`);

        if (!response.ok) {
          throw new Error('Nie udało się pobrać artykułów');
        }

        const data: ArticleApiResponse[] = await response.json();

        // Map backend data to frontend format
        const mappedArticles: Article[] = data.map(item => ({
          id: String(item.id),
          title: item.title,
          summary: item.summary || 'Brak opisu',
          source: item.source_name || 'Nieznane źródło',
          category: item.category || 'Wiadomości',
          timestamp: formatTimestamp(item.scraped_at),
          url: item.url,
          imageUrl: item.image_url || undefined
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
  }, [limit]);

  return { articles, loading, error };
}
