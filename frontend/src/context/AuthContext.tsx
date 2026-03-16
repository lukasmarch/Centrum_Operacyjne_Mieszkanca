/**
 * AuthContext - Global authentication state management
 * Provides user info, login/logout functions, and loading states
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from 'react';
import {
  User,
  LoginCredentials,
  RegisterData,
  UserUpdateData,
} from '../../types';
import * as authApi from '../services/authApi';
import { DashboardLayoutId, getUserDashboardLayout } from '../config/dashboardLayouts';

interface AuthContextType {
  // State
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => Promise<void>;
  updateProfile: (data: UserUpdateData) => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  clearError: () => void;

  // Helpers
  isPremium: boolean;
  userLocation: string;
  dashboardLayout: DashboardLayoutId;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Check if user has premium access
  const isPremium = user?.tier === 'premium' || user?.tier === 'business';

  // Get user's location (default to Rybno)
  const userLocation = user?.location || 'Rybno';

  // Get user's dashboard layout preference
  const dashboardLayout = getUserDashboardLayout(user?.preferences ?? null);

  /**
   * Initialize auth state on mount
   * Check if user is already logged in (has valid token)
   */
  useEffect(() => {
    const initAuth = async () => {
      const token = authApi.getAccessToken();

      if (!token) {
        setIsLoading(false);
        return;
      }

      try {
        const currentUser = await authApi.getCurrentUser();
        setUser(currentUser);
      } catch (err) {
        // Token invalid or expired, try refresh
        const refreshed = await authApi.refreshAccessToken();
        if (refreshed) {
          try {
            const currentUser = await authApi.getCurrentUser();
            setUser(currentUser);
          } catch {
            // Still failed, clear everything
            authApi.clearTokens();
          }
        }
      } finally {
        setIsLoading(false);
      }
    };

    initAuth();
  }, []);

  /**
   * Login user
   */
  const login = useCallback(async (credentials: LoginCredentials) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await authApi.login(credentials);
      setUser(response.user);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Register new user
   */
  const register = useCallback(async (data: RegisterData) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await authApi.register(data);
      setUser(response.user);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Registration failed';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Logout user
   */
  const logout = useCallback(async () => {
    setIsLoading(true);

    try {
      await authApi.logout();
    } finally {
      setUser(null);
      setIsLoading(false);
    }
  }, []);

  /**
   * Update user profile
   */
  const updateProfile = useCallback(async (data: UserUpdateData) => {
    setError(null);

    try {
      const updatedUser = await authApi.updateProfile(data);
      setUser(updatedUser);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Update failed';
      setError(message);
      throw err;
    }
  }, []);

  /**
   * Change password
   */
  const changePassword = useCallback(
    async (currentPassword: string, newPassword: string) => {
      setError(null);

      try {
        await authApi.changePassword(currentPassword, newPassword);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Password change failed';
        setError(message);
        throw err;
      }
    },
    []
  );

  /**
   * Clear error state
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    error,
    login,
    register,
    logout,
    updateProfile,
    changePassword,
    clearError,
    isPremium,
    userLocation,
    dashboardLayout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

/**
 * Hook to use auth context
 */
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

/**
 * Hook to require authentication
 * Returns user or redirects to login
 */
export const useRequireAuth = (): User | null => {
  const { user, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && !user) {
      // Could dispatch navigation event here
      console.warn('Authentication required');
    }
  }, [user, isLoading]);

  return user;
};
