import axios from 'axios';
import type {
  DashboardData, AirportRiskDetail, Airport, TrendData, CorrelationData,
  LoginRequest, TokenResponse, AuthUser, AirportForecastResponse,
} from '@/types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';
const STORAGE_KEY = 'auth-storage';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request 인터셉터: Bearer 토큰 주입 (sessionStorage 직접 읽기 — 순환 의존성 방지)
api.interceptors.request.use((config) => {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (raw) {
      const { token } = JSON.parse(raw);
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
  } catch {
    // sessionStorage 접근 실패 시 무시
  }
  return config;
});

// Response 인터셉터: 401 시 인증 상태 초기화 + 로그인 페이지로 리다이렉트
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      sessionStorage.removeItem(STORAGE_KEY);
      // 로그인 페이지가 아닌 경우에만 리다이렉트
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

// 대시보드 데이터 조회
export const fetchDashboard = async (): Promise<DashboardData> => {
  const { data } = await api.get('/risks/dashboard');
  return data;
};

// 공항 목록 조회
export const fetchAirports = async (region?: string): Promise<{ total: number; airports: Airport[] }> => {
  const { data } = await api.get('/airports', { params: { region } });
  return data;
};

// 공항 상세 위험지수 조회
export const fetchAirportRisk = async (airportCode: string, date?: string): Promise<AirportRiskDetail> => {
  const { data } = await api.get(`/risks/airports/${airportCode}`, {
    params: { target_date: date },
  });
  return data;
};

// 위험지수 이력 조회
export const fetchRiskHistory = async (
  airportCode: string,
  startDate: string,
  endDate: string
): Promise<{ history: { date: string; total_score: number }[] }> => {
  const { data } = await api.get(`/risks/airports/${airportCode}/history`, {
    params: { start_date: startDate, end_date: endDate },
  });
  return data;
};

// 공항 비교
export const fetchComparison = async (airportCodes: string[]): Promise<{
  date: string;
  comparison: { code: string; name: string; total_score: number; categories: Record<string, number> }[];
}> => {
  const { data } = await api.get('/risks/comparison', {
    params: { airport_codes: airportCodes },
    paramsSerializer: (params) => {
      return params.airport_codes.map((c: string) => `airport_codes=${c}`).join('&');
    },
  });
  return data;
};

// 트렌드 분석
export const fetchTrends = async (
  airportCode?: string,
  category?: string,
  period?: string
): Promise<TrendData> => {
  const { data } = await api.get('/analytics/trends', {
    params: { airport_code: airportCode, category, period },
  });
  return data;
};

// 상관분석 결과
export const fetchCorrelations = async (): Promise<CorrelationData> => {
  const { data } = await api.get('/analytics/correlations');
  return data;
};

// 가중치 조회
export const fetchWeights = async (): Promise<{
  category_weights: Record<string, number>;
  factor_weights: Record<string, Record<string, number>>;
}> => {
  const { data } = await api.get('/analytics/weights');
  return data;
};

// 시계열 데이터 조회
export const fetchTimeSeries = async (
  period?: string,
  airportCode?: string
): Promise<{ data: { date: string; total_score: number; categories?: Record<string, number> }[] }> => {
  const { data } = await api.get('/analytics/time-series', {
    params: { period, airport_code: airportCode },
  });
  return data;
};

// 상관관계 행렬 조회
export const fetchCorrelationMatrix = async (): Promise<{
  categories: string[];
  matrix: number[][];
}> => {
  const { data } = await api.get('/analytics/correlation-matrix');
  return data;
};

// 예측 데이터 조회
export const fetchForecast = async (
  airportCode: string,
  category?: string,
  horizon?: number
): Promise<AirportForecastResponse> => {
  const { data } = await api.get('/analytics/forecast', {
    params: { airport_code: airportCode, category, horizon },
  });
  return data;
};

// 로그인
export const loginAPI = async (credentials: LoginRequest): Promise<TokenResponse> => {
  const { data } = await api.post('/auth/login', credentials);
  return data;
};

// 내 정보 조회
export const fetchMe = async (): Promise<AuthUser> => {
  const { data } = await api.get('/auth/me');
  return data;
};

export default api;
