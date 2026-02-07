/**
 * GUS Statistics React Hooks
 *
 * Custom hooks for fetching and managing GUS BDL (Bank Danych Lokalnych) data
 * Includes local caching (1 hour TTL) to minimize backend requests
 *
 * Available hooks:
 * - useGUSOverview: Free tier KPI dashboard (9 variables)
 * - useGUSSection: Premium tier section view (full category data)
 * - useGUSVariableDetail: Detailed variable view with full history
 * - useGUSCategories: List of all 10 categories
 * - useGUSVariablesList: Tier-based variables listing
 */

import { useState, useEffect } from 'react';
import {
  GUSOverviewResponse,
  GUSSectionResponse,
  GUSVariableDetailResponse,
  GUSCategoriesResponse,
  GUSVariablesListResponse,
  UserTier,
} from '../../types';
import {
  getOverview,
  getSection,
  getVariableDetail,
  getCategories,
  getVariablesList,
} from '../services/gusApi';

// Simple in-memory cache with 1-hour TTL
interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

const CACHE_TTL = 60 * 60 * 1000; // 1 hour
const cache = new Map<string, CacheEntry<any>>();

const getCached = <T,>(key: string): T | null => {
  const entry = cache.get(key);
  if (!entry) return null;
  if (Date.now() - entry.timestamp > CACHE_TTL) {
    cache.delete(key);
    return null;
  }
  return entry.data as T;
};

const setCache = <T,>(key: string, data: T): void => {
  cache.set(key, { data, timestamp: Date.now() });
};

/**
 * Hook: useGUSOverview
 *
 * Fetches Free tier KPI overview (9 core variables)
 * No authentication required - accessible to all users
 *
 * Returns:
 * - data: Overview data with 9 KPI variables
 * - loading: Loading state
 * - error: Error message if fetch fails
 * - refetch: Function to manually trigger refresh
 *
 * Auto-refreshes every 2 hours (data updates quarterly, so no need for frequent polling)
 */
export const useGUSOverview = () => {
  const [data, setData] = useState<GUSOverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    const cacheKey = 'gus_overview';

    // Check cache first
    const cached = getCached<GUSOverviewResponse>(cacheKey);
    if (cached) {
      setData(cached);
      setLoading(false);
      setError(null);
      return;
    }

    try {
      setLoading(true);
      const result = await getOverview();
      setData(result);
      setCache(cacheKey, result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch overview');
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();

    // Auto-refresh every 2 hours
    const interval = setInterval(fetchData, 2 * 60 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  return { data, loading, error, refetch: fetchData };
};

/**
 * Hook: useGUSSection
 *
 * Fetches full section data (Premium tier required)
 * Returns all variables in category with trends, comparisons, national averages
 *
 * @param sectionKey - Section identifier (demografia, rynek_pracy, etc.)
 *
 * Returns:
 * - data: Section data with all variables, trends, comparisons
 * - loading: Loading state
 * - error: Error message (403 if tier insufficient)
 * - refetch: Function to manually trigger refresh
 */
export const useGUSSection = (sectionKey: string | null) => {
  const [data, setData] = useState<GUSSectionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!sectionKey) {
      setData(null);
      setLoading(false);
      setError(null);
      return;
    }

    const cacheKey = `gus_section_${sectionKey}`;

    // Check cache first
    const cached = getCached<GUSSectionResponse>(cacheKey);
    if (cached) {
      setData(cached);
      setLoading(false);
      setError(null);
      return;
    }

    try {
      setLoading(true);
      const result = await getSection(sectionKey);
      setData(result);
      setCache(cacheKey, result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to fetch section: ${sectionKey}`);
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [sectionKey]);

  return { data, loading, error, refetch: fetchData };
};

/**
 * Hook: useGUSVariableDetail
 *
 * Fetches detailed variable data with full historical trend
 * Access level depends on variable tier (Free/Premium/Business)
 *
 * @param varKey - Variable key (population_total, unemployment_rate, etc.)
 *
 * Returns:
 * - data: Variable detail with current value, history, comparisons, national average
 * - loading: Loading state
 * - error: Error message (403 if tier insufficient, 404 if not found)
 * - refetch: Function to manually trigger refresh
 */
export const useGUSVariableDetail = (varKey: string | null) => {
  const [data, setData] = useState<GUSVariableDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!varKey) {
      setData(null);
      setLoading(false);
      setError(null);
      return;
    }

    const cacheKey = `gus_variable_${varKey}`;

    // Check cache first
    const cached = getCached<GUSVariableDetailResponse>(cacheKey);
    if (cached) {
      setData(cached);
      setLoading(false);
      setError(null);
      return;
    }

    try {
      setLoading(true);
      const result = await getVariableDetail(varKey);
      setData(result);
      setCache(cacheKey, result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to fetch variable: ${varKey}`);
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [varKey]);

  return { data, loading, error, refetch: fetchData };
};

/**
 * Hook: useGUSCategories
 *
 * Fetches list of all 10 GUS categories
 * No authentication required
 *
 * Returns:
 * - data: Array of categories with names, descriptions, required tiers
 * - loading: Loading state
 * - error: Error message if fetch fails
 * - refetch: Function to manually trigger refresh
 */
export const useGUSCategories = () => {
  const [data, setData] = useState<GUSCategoriesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    const cacheKey = 'gus_categories';

    // Check cache first
    const cached = getCached<GUSCategoriesResponse>(cacheKey);
    if (cached) {
      setData(cached);
      setLoading(false);
      setError(null);
      return;
    }

    try {
      setLoading(true);
      const result = await getCategories();
      setData(result);
      setCache(cacheKey, result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch categories');
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();

    // Auto-refresh every 2 hours
    const interval = setInterval(fetchData, 2 * 60 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  return { data, loading, error, refetch: fetchData };
};

/**
 * Hook: useGUSVariablesList
 *
 * Fetches list of variables filtered by user's tier
 * If authenticated: returns variables for user's tier
 * If not authenticated: returns only Free tier variables
 *
 * @param tier - Optional: filter by specific tier (free/premium/business)
 *
 * Returns:
 * - data: Array of variables with metadata, tier counts
 * - loading: Loading state
 * - error: Error message if fetch fails
 * - refetch: Function to manually trigger refresh
 */
export const useGUSVariablesList = (tier?: UserTier) => {
  const [data, setData] = useState<GUSVariablesListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    const cacheKey = tier ? `gus_variables_${tier}` : 'gus_variables_all';

    // Check cache first
    const cached = getCached<GUSVariablesListResponse>(cacheKey);
    if (cached) {
      setData(cached);
      setLoading(false);
      setError(null);
      return;
    }

    try {
      setLoading(true);
      const result = await getVariablesList(tier);
      setData(result);
      setCache(cacheKey, result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch variables list');
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();

    // Auto-refresh every 2 hours
    const interval = setInterval(fetchData, 2 * 60 * 60 * 1000);
    return () => clearInterval(interval);
  }, [tier]);

  return { data, loading, error, refetch: fetchData };
};
