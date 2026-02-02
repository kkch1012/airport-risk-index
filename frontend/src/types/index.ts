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
}

// 알림
export interface Alert {
  airport: string;
  type: string;
  message: string;
  severity: 'INFO' | 'WARNING' | 'CRITICAL';
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
