/**
 * GUS Statistics API Service
 * Handles all GUS BDL (Bank Danych Lokalnych) data fetching
 *
 * Database-First Architecture:
 * - All data comes from local PostgreSQL database
 * - Zero live API calls to bdl.stat.gov.pl
 * - Data refreshed quarterly by backend scheduler
 *
 * Tier-based access:
 * - Free: 9 core KPI variables (overview only)
 * - Premium: 57 variables across 10 categories
 * - Business: All 88 variables + advanced features
 */

import {
  GUSOverviewResponse,
  GUSSectionResponse,
  GUSVariableDetailResponse,
  GUSCategoriesResponse,
  GUSVariablesListResponse,
  GUSFreshnessResponse,
  UserTier,
} from '../../types';
import { getAccessToken } from './authApi';

const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000/api') + '/stats';

/**
 * Make authenticated API request to GUS endpoints
 */
const gusFetch = async (
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> => {
  const token = getAccessToken();

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }

  return fetch(`${API_BASE_URL}${endpoint}`, { ...options, headers });
};

/**
 * Get Free tier KPI overview (9 core variables)
 *
 * No authentication required - accessible to all users
 *
 * Returns:
 * - 9 KPI variables (population, unemployment, businesses, etc.)
 * - Current values with year-over-year trends
 * - User's tier level
 * - Last data refresh timestamp
 */
export const getOverview = async (): Promise<GUSOverviewResponse> => {
  const response = await gusFetch('/overview');

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch overview' }));
    throw new Error(error.detail || 'Failed to fetch GUS overview');
  }

  return response.json();
};

/**
 * Get full section data (Premium tier required)
 *
 * Sections: demografia, rynek_pracy, przedsiebiorczosc, finanse_gminy,
 *           mieszkalnictwo, edukacja, transport, bezpieczenstwo, zdrowie, turystyka
 *
 * Returns:
 * - All variables in section with current values
 * - Historical trends (10+ years)
 * - Comparisons with other gminy
 * - National/voivodeship averages
 *
 * @param sectionKey - Section identifier (e.g., 'demografia', 'rynek_pracy')
 */
export const getSection = async (sectionKey: string): Promise<GUSSectionResponse> => {
  const response = await gusFetch(`/section/${sectionKey}`);

  if (!response.ok) {
    if (response.status === 403) {
      throw new Error('Premium tier required for section data');
    }
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch section' }));
    throw new Error(error.detail || `Failed to fetch section: ${sectionKey}`);
  }

  return response.json();
};

/**
 * Get detailed variable data with full history
 *
 * Returns:
 * - Current value with metadata
 * - Full historical trend (all available years)
 * - Ranking among all gminy in powiat
 * - National comparison (percentage of national average)
 *
 * Access level depends on variable tier:
 * - Free variables: accessible to all
 * - Premium variables: Premium+ tier required
 * - Business variables: Business tier required
 *
 * @param varKey - Variable key (e.g., 'population_total', 'unemployment_rate')
 */
export const getVariableDetail = async (varKey: string): Promise<GUSVariableDetailResponse> => {
  const response = await gusFetch(`/variable/${varKey}/detail`);

  if (!response.ok) {
    if (response.status === 403) {
      throw new Error('Insufficient tier access for this variable');
    }
    if (response.status === 404) {
      throw new Error(`Variable not found: ${varKey}`);
    }
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch variable' }));
    throw new Error(error.detail || `Failed to fetch variable: ${varKey}`);
  }

  return response.json();
};

/**
 * Get list of all categories
 *
 * Returns 10 main categories with:
 * - Category name and description
 * - Number of variables in category
 * - Required tier level for access
 *
 * No authentication required
 */
export const getCategories = async (): Promise<GUSCategoriesResponse> => {
  const response = await gusFetch('/categories');

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch categories' }));
    throw new Error(error.detail || 'Failed to fetch categories');
  }

  return response.json();
};

/**
 * Get list of variables filtered by user's tier
 *
 * Returns:
 * - All variables accessible to user's tier
 * - Variable metadata (name, unit, category, tier, level)
 * - Tier statistics (counts per tier)
 *
 * If authenticated: returns variables for user's tier
 * If not authenticated: returns only Free tier variables
 *
 * @param tier - Optional: filter by specific tier (free/premium/business)
 */
export const getVariablesList = async (tier?: UserTier): Promise<GUSVariablesListResponse> => {
  const endpoint = tier ? `/variables/list?tier=${tier}` : '/variables/list';
  const response = await gusFetch(endpoint);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch variables' }));
    throw new Error(error.detail || 'Failed to fetch variables list');
  }

  return response.json();
};

/**
 * Get data freshness tracking
 *
 * Returns:
 * - Last refresh timestamp per category
 * - Next scheduled refresh date
 * - Number of variables tracked per category
 *
 * Useful for displaying "Last updated" info to users
 *
 * No authentication required
 */
export const getFreshness = async (): Promise<GUSFreshnessResponse> => {
  const response = await gusFetch('/freshness');

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch freshness' }));
    throw new Error(error.detail || 'Failed to fetch data freshness');
  }

  return response.json();
};

/**
 * Check if user has access to specific variable
 *
 * Helper function to validate tier access before making API calls
 *
 * @param varKey - Variable key to check
 * @param userTier - User's tier level
 * @returns boolean indicating access permission
 */
export const checkVariableAccess = async (
  varKey: string,
  userTier: UserTier
): Promise<boolean> => {
  try {
    const variables = await getVariablesList(userTier);
    return variables.variables.some(v => v.key === varKey);
  } catch {
    return false;
  }
};

/**
 * Get variable metadata by key
 *
 * Helper function to fetch variable metadata without full data
 *
 * @param varKey - Variable key
 * @returns Variable metadata or null if not found
 */
export const getVariableMetadata = async (varKey: string) => {
  try {
    const variables = await getVariablesList();
    return variables.variables.find(v => v.key === varKey) || null;
  } catch {
    return null;
  }
};
