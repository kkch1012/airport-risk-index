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

/** JWT 만료 확인 (base64 디코딩으로 exp 필드 검사) */
function isTokenExpired(token: string): boolean {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return true;
    const payload = JSON.parse(atob(parts[1]));
    if (!payload.exp) return false;
    // 10초 여유를 두고 만료 판단
    return payload.exp * 1000 < Date.now() - 10000;
  } catch {
    return true;
  }
}

function loadToken(): string | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const token = JSON.parse(raw).token || null;
    if (token && isTokenExpired(token)) {
      sessionStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return token;
  } catch {
    return null;
  }
}

function persist(token: string | null) {
  if (token) {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ token }));
  } else {
    sessionStorage.removeItem(STORAGE_KEY);
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
