// 위험등급 타입
export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';

// 위험 카테고리 코드
export type CategoryCode = 'aviation' | 'security' | 'health' | 'operational' | 'weather' | 'external';

// 공항 정보
export interface Airport {
  code: string;
  name: string;
  region: string;
  latitude: number;
  longitude: number;
}

// 카테고리별 점수
export interface CategoryScore {
  name: string;
  score: number;
  level: RiskLevel;
  factors: Record<string, number>;
}

// 공항 위험지수 요약
export interface AirportRiskSummary {
  code: string;
  name: string;
  score: number;
  level: RiskLevel;
  weather_score?: number;
  operational_score?: number;
}

// 대시보드 데이터
export interface DashboardData {
  summary: {
    total_airports: number;
    high_risk_count: number;
    average_score: number;
    updated_at: string;
  };
  airports: AirportRiskSummary[];
  alerts: Alert[];
}

// 데이터 소스 정보
export interface DataSourceInfo {
  weather: string;
  others: string;
  [key: string]: string;
}

// 공항 상세 위험지수
export interface AirportRiskDetail {
  airport: {
    code: string;
    name: string;
  };
  date: string;
  total_score: number;
  risk_level: RiskLevel;
  categories: Record<CategoryCode, CategoryScore>;
  updated_at: string;
  data_source?: DataSourceInfo;
}

// 알림
export interface Alert {
  airport: string;
  type: string;
  message: string;
  severity: 'INFO' | 'WARNING' | 'CRITICAL';
  created_at?: string;
}

// 트렌드 데이터
export interface TrendData {
  airport_code: string;
  category: string;
  period: string;
  data: { day: number; score: number }[];
  statistics: {
    average: number;
    min: number;
    max: number;
    trend: string;
  };
}

// 상관분석 결과
export interface CorrelationData {
  factors: Record<string, {
    incident_count: number;
    severity_score: number;
    significant: boolean;
  }>;
  last_updated: string;
  sample_size: number;
}

// 시계열 데이터
export interface TimeSeriesDataPoint {
  date: string;
  total_score: number;
  categories?: Record<string, number>;
}

export interface TimeSeriesResponse {
  data: TimeSeriesDataPoint[];
}

// 상관관계 행렬
export interface CorrelationMatrixData {
  categories: string[];
  matrix: number[][];
}

// 인증 관련 타입
export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface AuthUser {
  id: number;
  email: string;
  username: string;
  is_active: boolean;
  is_admin: boolean;
}
