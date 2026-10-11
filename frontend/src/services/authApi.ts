/**
 * Auth API Service
 * Handles all authentication-related API calls
 */

import {
  User,
  AuthResponse,
  LoginCredentials,
  RegisterData,
  UserUpdateData,
} from '../../types';
import { ApiError, toApiError } from './apiError';

// Use env var with fallback to localhost (for development)
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const OFFLINE_MESSAGE = 'Brak połączenia z serwerem. Sprawdź internet i spróbuj ponownie.';

/** `fetch` rzuca TypeError („Failed to fetch”) bez sieci — po angielsku i bez sensu dla ludzi */
const postJson = async (url: string, body: unknown): Promise<Response> => {
  try {
    return await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(OFFLINE_MESSAGE, 0);
  }
};

// Token storage keys
const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

/**
 * Get stored access token
 */
export const getAccessToken = (): string | null => {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
};

/**
 * Get stored refresh token
 */
export const getRefreshToken = (): string | null => {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
};

/**
 * Store tokens in localStorage
 */
export const storeTokens = (accessToken: string, refreshToken: string): void => {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
};

/**
 * Clear stored tokens
 */
export const clearTokens = (): void => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
};

/**
 * Make authenticated API request
 */
const authFetch = async (
  url: string,
  options: RequestInit = {}
): Promise<Response> => {
  const makeRequest = (token: string | null): Promise<Response> => {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };
    if (token) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
    }
    return fetch(url, { ...options, headers });
  };

  let response = await makeRequest(getAccessToken());

  // Auto-refresh on 401 (expired access token)
  if (response.status === 401) {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      try {
        const refreshResponse = await fetch(`${API_BASE_URL}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (refreshResponse.ok) {
          const result = await refreshResponse.json();
          storeTokens(result.access_token, result.refresh_token);
          response = await makeRequest(result.access_token);
        } else {
          clearTokens();
        }
      } catch {
        clearTokens();
      }
    }
  }

  return response;
};

/**
 * Register a new user
 */
export const register = async (data: RegisterData): Promise<AuthResponse> => {
  const response = await postJson(`${API_BASE_URL}/auth/register`, data);

  if (!response.ok) {
    throw await toApiError(response, 'Nie udało się założyć konta. Spróbuj ponownie za chwilę.');
  }

  const result: AuthResponse = await response.json();
  storeTokens(result.tokens.access_token, result.tokens.refresh_token);
  return result;
};

/**
 * Login user
 */
export const login = async (credentials: LoginCredentials): Promise<AuthResponse> => {
  const response = await postJson(`${API_BASE_URL}/auth/login`, credentials);

  if (!response.ok) {
    throw await toApiError(response, 'Nie udało się zalogować. Spróbuj ponownie za chwilę.');
  }

  const result: AuthResponse = await response.json();
  storeTokens(result.tokens.access_token, result.tokens.refresh_token);
  return result;
};

/**
 * Logout user
 */
export const logout = async (): Promise<void> => {
  try {
    await authFetch(`${API_BASE_URL}/auth/logout`, { method: 'POST' });
  } finally {
    clearTokens();
  }
};

/**
 * Get current user profile
 */
export const getCurrentUser = async (): Promise<User> => {
  const response = await authFetch(`${API_BASE_URL}/users/me`);

  if (!response.ok) {
    if (response.status === 401) {
      clearTokens();
      throw new Error('Session expired');
    }
    throw new Error('Failed to get user');
  }

  return response.json();
};

/**
 * Update user profile
 */
export const updateProfile = async (data: UserUpdateData): Promise<User> => {
  const response = await authFetch(`${API_BASE_URL}/users/me`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Update failed');
  }

  return response.json();
};

/**
 * Change password
 */
export const changePassword = async (
  currentPassword: string,
  newPassword: string
): Promise<void> => {
  const response = await authFetch(`${API_BASE_URL}/users/me/change-password`, {
    method: 'POST',
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });

  if (!response.ok) {
    throw await toApiError(response, 'Nie udało się zmienić hasła. Spróbuj ponownie za chwilę.');
  }

  // Nowe hasło kończy wszystkie wcześniejsze sesje (także tę) — backend oddaje
  // świeże tokeny, bez nich następne kliknięcie by wylogowało (F-028)
  const tokens = await response.json();
  if (tokens?.access_token && tokens?.refresh_token) {
    storeTokens(tokens.access_token, tokens.refresh_token);
  }
};

/**
 * Prośba o link do ustawienia nowego hasła. Odpowiedź jest ta sama dla
 * każdego adresu — backend nie zdradza, czy konto istnieje.
 */
export const forgotPassword = async (email: string): Promise<string> => {
  const response = await postJson(`${API_BASE_URL}/auth/forgot-password`, { email });
  if (!response.ok) {
    throw await toApiError(response, 'Nie udało się wysłać linku. Spróbuj ponownie za chwilę.');
  }
  const result = await response.json();
  return result.message;
};

/** Nowe hasło z linku z maila — po sukcesie konto jest od razu zalogowane. */
export const resetPassword = async (token: string, newPassword: string): Promise<AuthResponse> => {
  const response = await postJson(`${API_BASE_URL}/auth/reset-password`, {
    token,
    new_password: newPassword,
  });
  if (!response.ok) {
    throw await toApiError(response, 'Nie udało się ustawić hasła. Spróbuj ponownie za chwilę.');
  }
  const result: AuthResponse = await response.json();
  storeTokens(result.tokens.access_token, result.tokens.refresh_token);
  return result;
};

/**
 * Refresh access token
 */
export const refreshAccessToken = async (): Promise<boolean> => {
  const refreshToken = getRefreshToken();

  if (!refreshToken) {
    return false;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      clearTokens();
      return false;
    }

    const result = await response.json();
    storeTokens(result.access_token, result.refresh_token);
    return true;
  } catch {
    clearTokens();
    return false;
  }
};

/**
 * Get available locations
 */
export const getLocations = async (): Promise<{ locations: string[]; default: string }> => {
  const response = await fetch(`${API_BASE_URL}/users/locations`);

  if (!response.ok) {
    throw new Error('Failed to get locations');
  }

  return response.json();
};
