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

// Use env var with fallback to localhost (for development)
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

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
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Registration failed');
  }

  const result: AuthResponse = await response.json();
  storeTokens(result.tokens.access_token, result.tokens.refresh_token);
  return result;
};

/**
 * Login user
 */
export const login = async (credentials: LoginCredentials): Promise<AuthResponse> => {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Login failed');
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
    const error = await response.json();
    throw new Error(error.detail || 'Password change failed');
  }
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
