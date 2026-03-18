'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { ApiError, clearStoredToken, fetchMe, getStoredToken, login as loginRequest, setStoredToken } from '@/features/admin/data';
import type { AuthUser } from '@/features/admin/types';

interface AuthContextValue {
  ready: boolean;
  token: string | null;
  user: AuthUser | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);

  const hydrate = useCallback(async (incomingToken: string) => {
    const identity = await fetchMe(incomingToken);
    setToken(incomingToken);
    setUser(identity);
  }, []);

  useEffect(() => {
    const stored = getStoredToken();
    if (!stored) {
      setReady(true);
      return;
    }

    hydrate(stored)
      .catch(() => {
        clearStoredToken();
        setToken(null);
        setUser(null);
      })
      .finally(() => setReady(true));
  }, [hydrate]);

  const login = useCallback(async (email: string, password: string) => {
    const response = await loginRequest(email, password);
    setStoredToken(response.access_token);
    setToken(response.access_token);
    setUser(response.user);
    setReady(true);
  }, []);

  const logout = useCallback(() => {
    clearStoredToken();
    setToken(null);
    setUser(null);
    setReady(true);
  }, []);

  const refresh = useCallback(async () => {
    const stored = getStoredToken();
    if (!stored) {
      logout();
      return;
    }
    try {
      await hydrate(stored);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        logout();
        return;
      }
      throw error;
    }
  }, [hydrate, logout]);

  const value = useMemo(
    () => ({ ready, token, user, login, logout, refresh }),
    [ready, token, user, login, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
