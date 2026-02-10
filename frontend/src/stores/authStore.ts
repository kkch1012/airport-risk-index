import { create } from 'zustand';
import type { AuthUser } from '@/types';

const STORAGE_KEY = 'auth-storage';

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  setAuth: (token: string, user: AuthUser) => void;
  logout: () => void;
  checkAuth: () => Promise<void>;
}

function loadToken(): string | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw).token || null;
  } catch {
    return null;
  }
}

function persist(token: string | null) {
  if (token) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ token }));
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  token: loadToken(),
  user: null,
  isAuthenticated: false,

  setAuth: (token, user) => {
    persist(token);
    set({ token, user, isAuthenticated: true });
  },

  logout: () => {
    persist(null);
    set({ token: null, user: null, isAuthenticated: false });
  },

  checkAuth: async () => {
    const token = loadToken();
    if (!token) {
      set({ token: null, user: null, isAuthenticated: false });
      return;
    }

    try {
      // 동적 import로 순환 의존성 방지
      const { fetchMe } = await import('@/services/api');
      const user = await fetchMe();
      set({ token, user, isAuthenticated: true });
    } catch {
      persist(null);
      set({ token: null, user: null, isAuthenticated: false });
    }
  },
}));
