# 위험지수 산출 모델

## 개요

본 문서는 공항 위험지수를 산출하는 방법론과 알고리즘을 설명합니다.

> ⚠️ **문서 구성 안내:** 아래 "실제 구현 현황(2026-06)" 섹션이 현재 코드(`app/services/risk_calculator.py`)와
> 일치하는 **권위 있는 설명**입니다. 그 이후의 정규화/상관분석/ML 가중치/백테스트 섹션은 **향후 설계 참고용**이며
> 아직 구현되지 않았거나 단순화되어 있습니다(혼잡도·시설노후도 등 일부 요인은 제외됨).

---

## 실제 구현 현황 (2026-06 크롤링+공개데이터 전환)

### A. 카테고리 가중치 (`CATEGORY_WEIGHTS`)

| 카테고리 | 코드 | 가중치 |
|----------|------|--------|
| 항공안전 | aviation | 0.25 |
| 보안위협 | security | 0.20 |
| 기상위험 | weather | 0.20 |
| 보건위험 | health | 0.15 |
| 운영위험 | operational | 0.10 |
| 외부요인 | external | 0.10 |

### B. has_data 플래그 & 가중치 재정규화 (핵심)

각 카테고리 점수(`CategoryScore`)는 `has_data: bool` 필드를 가집니다.
데이터 소스에서 유효한 데이터를 얻지 못하면 `has_data=False`가 되고, **종합점수 계산에서 제외**됩니다.

```python
# 가용(has_data=True) 카테고리만으로 가중치 재정규화
available = {code: cat for code, cat in categories.items() if cat.has_data}
weight_sum = sum(active_weights[code] for code in available)
total_score = (
    sum(cat.score * active_weights[code] for code, cat in available.items()) / weight_sum
    if weight_sum > 0 else 0.0   # 가용 데이터가 전혀 없으면 종합점수 = 0
)
```

- **가짜 점수 금지:** 과거 `random.uniform()` 기반 mock은 전면 제거됨. 데이터 없음 = 정직하게 제외.
- **예외(실제 LOW 판정):** 국제선이 없는 국내 전용 공항의 외부요인/보건위험은 데이터 없이도
  실제 낮은 위험이므로 `has_data=True`로 유지(score≈5.0). 항공안전은 입력이 비면 `has_data=False`,
  데이터는 있으나 항공기 사고가 없으면 `has_data=True`.

### C. 운영위험 재정의 (지연 중심)

혼잡도·시설노후도·파업은 **공항 운영자 내부데이터**라 무료 공개데이터/크롤링으로 확보 불가 → 제외.
공개데이터로 산출 가능한 지표만 사용:

```python
delay_score  = min(65, delay_rate * 2.5)    # 지연율 주축 (0–65), 지연율 26%↑ 이면 최대
cancel_score = min(35, cancel_rate * 5)     # 결항율 보조 (0–35), 결항율 7%↑ 이면 최대
operational_score = delay_score + cancel_score
# 운항 데이터 소스 없음 → score=10.0, has_data=False
```

### D. 카테고리별 점수 산식 요약 (실제 구현)

| 카테고리 | 산식 요약 | 무데이터 처리 |
|----------|-----------|----------------|
| weather | 풍속35% + 강수형태30% + 강수량25% + 습도10% (가용 요인 가중평균) | factors 없으면 has_data=False |
| aviation | 사고이력(0–40) + 준사고(0–30) + 심각도(0–30) | 입력 빔→has_data=False, 사고無→True |
| security | 테러(0–40) + 밀수(0–30) + 불법입국(0–30) (각 max60%+avg40%) | 빈 데이터→score=5, has_data=False |
| health | 감염병경보60% + 검역지역수20% + 근접도20% | 국제선無→True, 데이터無→False |
| external | 여행경보50% + 국제정세15% + 해외기상20% + 해외항공15% | 국제선無→True, 데이터無→False |
| operational | 위 C 참조 | 운항데이터無→score=10, has_data=False |

### E. 위험등급

| 등급 | 점수 범위 |
|------|-----------|
| LOW | 0 ≤ s < 25 |
| MODERATE | 25 ≤ s < 50 |
| HIGH | 50 ≤ s < 75 |
| CRITICAL | 75 ≤ s ≤ 100 |

### F. 폴백 우선순위

데이터는 **① 공개 API → ② 무료 크롤링 폴백 → ③ 빈 리스트(데이터 없음)** 순으로 확보합니다.
뉴스 기반 폴백(운항 지연·여행경보)은 실측이 아닌 추정 프록시로 `is_proxy: True`가 붙습니다.
소스별 상세는 [DATA_SOURCES.md](DATA_SOURCES.md) 참조.

---

> 이하 섹션은 **향후 설계 참고용**입니다. (현재 코드와 다를 수 있음 — 특히 혼잡도/시정/ML 가중치 부분)

---

## 위험지수 산출 프레임워크

```
┌─────────────────────────────────────────────────────────────────────┐
│                        위험지수 산출 프로세스                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐ │
│  │ 1. 데이터 │───▶│ 2. 정규화 │───▶│ 3. 가중치 │───▶│ 4. 점수  │ │
│  │    수집   │    │           │    │    적용   │    │    산출   │ │
│  └───────────┘    └───────────┘    └───────────┘    └───────────┘ │
│        │                                                  │        │
│        │         ┌───────────────────────────┐           │        │
│        └────────▶│    상관분석 (주기적)      │◀──────────┘        │
│                  │  → 가중치 업데이트        │                    │
│                  └───────────────────────────┘                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 1. 위험요인 정규화

### 정규화 목적
- 서로 다른 단위의 데이터를 0-100 스케일로 통일
- 비교 가능한 형태로 변환

### 정규화 방법

#### 1.1 Min-Max 정규화 (기본)
```python
def min_max_normalize(value, min_val, max_val, inverse=False):
    """
    Min-Max 정규화

    Args:
        value: 원본 값
        min_val: 최소값 (정상 상태)
        max_val: 최대값 (위험 상태)
        inverse: True면 값이 낮을수록 위험 (예: 시정)

    Returns:
        0-100 사이 정규화된 값
    """
    if max_val == min_val:
        return 0

    normalized = (value - min_val) / (max_val - min_val) * 100
    normalized = max(0, min(100, normalized))

    if inverse:
        normalized = 100 - normalized

    return normalized
```

#### 1.2 요인별 정규화 기준

| 요인 | 단위 | 안전값 | 위험값 | 방향 |
|------|------|--------|--------|------|
| 시정 | m | 10000 | 500 | 역방향 (낮을수록 위험) |
| 풍속 | m/s | 0 | 20 | 정방향 (높을수록 위험) |
| 돌풍 | m/s | 0 | 25 | 정방향 |
| 강수량 | mm/h | 0 | 30 | 정방향 |
| 적설량 | cm | 0 | 20 | 정방향 |
| 혼잡도 | % | 0 | 100 | 정방향 |
| 지연율 | % | 0 | 30 | 정방향 |
| 감염병경보 | 1-4 | 1 | 4 | 정방향 |
| 테러경보 | 1-5 | 1 | 5 | 정방향 |
| 여행경보 | 1-4 | 1 | 4 | 정방향 |

#### 1.3 정규화 함수 구현

```python
# backend/app/services/normalizer.py

from typing import Dict, Any, Callable
from dataclasses import dataclass

@dataclass
class NormalizationRule:
    min_val: float
    max_val: float
    inverse: bool = False
    transform: Callable = None  # 추가 변환 함수

# 요인별 정규화 규칙
NORMALIZATION_RULES: Dict[str, NormalizationRule] = {
    # 기상
    "visibility": NormalizationRule(500, 10000, inverse=True),
    "wind_speed": NormalizationRule(0, 20),
    "wind_gust": NormalizationRule(0, 25),
    "precipitation": NormalizationRule(0, 30),
    "snowfall": NormalizationRule(0, 20),

    # 운영
    "congestion_rate": NormalizationRule(0, 100),
    "delay_rate": NormalizationRule(0, 30),
    "cancellation_rate": NormalizationRule(0, 20),

    # 보건
    "disease_alert_level": NormalizationRule(1, 4),
    "quarantine_cases": NormalizationRule(0, 50),

    # 보안
    "terror_threat_level": NormalizationRule(1, 5),
    "smuggling_cases": NormalizationRule(0, 20),

    # 외부
    "travel_advisory": NormalizationRule(1, 4),
    "country_risk_index": NormalizationRule(0, 10),
}

class FactorNormalizer:
    def __init__(self):
        self.rules = NORMALIZATION_RULES

    def normalize(self, factor_code: str, value: float) -> float:
        """요인값 정규화"""
        if factor_code not in self.rules:
            return min(100, max(0, value))

        rule = self.rules[factor_code]

        # 추가 변환이 있으면 적용
        if rule.transform:
            value = rule.transform(value)

        # Min-Max 정규화
        normalized = (value - rule.min_val) / (rule.max_val - rule.min_val) * 100
        normalized = max(0, min(100, normalized))

        if rule.inverse:
            normalized = 100 - normalized

        return round(normalized, 2)
```

---

## 2. 상관분석

### 2.1 목적
- 각 위험요인과 실제 사고 간의 통계적 관계 파악
- 과학적 근거 기반의 가중치 산출

### 2.2 분석 대상

```
독립변수 (X): 위험요인
├── 기상: 시정, 풍속, 강수량, 적설량, ...
├── 운영: 혼잡도, 지연율, 결항율, ...
├── 보건: 감염병경보, 검역적발, ...
└── 보안: 테러경보, 밀수적발, ...

종속변수 (Y): 사고 지표
├── 사고 발생 건수 (incident_count)
├── 사망자 수 (fatalities)
├── 부상자 수 (injuries)
└── 심각도 점수 (severity_score)
```

### 2.3 심각도 점수 산출

```python
def calculate_severity_score(incident: dict) -> float:
    """
    사고 심각도 점수 산출

    가중치:
    - 사망: 10점/명
    - 중상: 3점/명
    - 경상: 1점/명
    - 기체 전손: 50점
    - 기체 대파: 30점
    - 기체 소파: 10점
    """
    score = 0

    # 인명 피해
    score += incident.get("fatalities", 0) * 10
    score += incident.get("serious_injuries", 0) * 3
    score += incident.get("minor_injuries", 0) * 1

    # 기체 피해
    damage_scores = {"destroyed": 50, "substantial": 30, "minor": 10, "none": 0}
    score += damage_scores.get(incident.get("aircraft_damage", "none"), 0)

    return score
```

### 2.4 상관분석 구현

```python
# backend/app/ml/correlation.py

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple

class CorrelationAnalyzer:
    """위험요인-사고 상관분석"""

    def __init__(self, min_samples: int = 30):
        self.min_samples = min_samples

    def analyze(
        self,
        factor_df: pd.DataFrame,
        incident_df: pd.DataFrame,
        target_columns: List[str] = None
    ) -> Dict[str, Dict]:
        """
        상관분석 수행

        Args:
            factor_df: 위험요인 시계열 데이터 (date, airport_id, factor1, factor2, ...)
            incident_df: 사고 시계열 데이터 (date, airport_id, incident_count, severity_score, ...)
            target_columns: 분석할 종속변수 컬럼

        Returns:
            요인별 상관분석 결과
        """
        if target_columns is None:
            target_columns = ["incident_count", "severity_score"]

        # 데이터 병합 (날짜, 공항 기준)
        merged = pd.merge(
            factor_df,
            incident_df,
            on=["date", "airport_id"],
            how="inner"
        )

        results = {}
        factor_columns = [c for c in factor_df.columns if c not in ["date", "airport_id"]]

        for factor in factor_columns:
            factor_results = {}

            for target in target_columns:
                # 결측치 제거
                valid_data = merged[[factor, target]].dropna()

                if len(valid_data) < self.min_samples:
                    continue

                x = valid_data[factor]
                y = valid_data[target]

                # Pearson 상관계수
                pearson_r, pearson_p = stats.pearsonr(x, y)

                # Spearman 상관계수 (비선형 관계)
                spearman_r, spearman_p = stats.spearmanr(x, y)

                factor_results[target] = {
                    "pearson_r": round(pearson_r, 4),
                    "pearson_p": round(pearson_p, 6),
                    "spearman_r": round(spearman_r, 4),
                    "spearman_p": round(spearman_p, 6),
                    "sample_size": len(valid_data),
                    "significant": pearson_p < 0.05
                }

            results[factor] = factor_results

        return results

    def get_significant_factors(
        self,
        results: Dict[str, Dict],
        target: str = "severity_score",
        p_threshold: float = 0.05
    ) -> List[Tuple[str, float]]:
        """
        유의미한 상관관계를 가진 요인 추출

        Returns:
            [(factor_name, correlation), ...] 상관계수 절대값 내림차순
        """
        significant = []

        for factor, targets in results.items():
            if target in targets:
                data = targets[target]
                if data.get("pearson_p", 1) < p_threshold:
                    significant.append((factor, data["pearson_r"]))

        # 상관계수 절대값 기준 정렬
        significant.sort(key=lambda x: abs(x[1]), reverse=True)

        return significant
```

---

## 3. 가중치 산출

### 3.1 가중치 산출 방법

#### 방법 1: 상관계수 기반
```python
def weights_from_correlation(correlations: Dict[str, float]) -> Dict[str, float]:
    """
    상관계수를 기반으로 가중치 산출
    - 상관계수 절대값의 비율로 가중치 할당
    """
    abs_corrs = {k: abs(v) for k, v in correlations.items()}
    total = sum(abs_corrs.values())

    if total == 0:
        return {k: 1/len(correlations) for k in correlations}

    return {k: v/total for k, v in abs_corrs.items()}
```

#### 방법 2: 회귀분석 기반
```python
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

def weights_from_regression(
    X: pd.DataFrame,
    y: pd.Series,
    alpha: float = 1.0
) -> Dict[str, float]:
    """
    Ridge 회귀분석으로 가중치 산출
    - 표준화된 회귀계수를 가중치로 사용
    """
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = Ridge(alpha=alpha)
    model.fit(X_scaled, y)

    # 절대값 기준 정규화
    abs_coefs = np.abs(model.coef_)
    weights = abs_coefs / abs_coefs.sum()

    return dict(zip(X.columns, weights))
```

#### 방법 3: Random Forest 기반
```python
from sklearn.ensemble import RandomForestRegressor

def weights_from_random_forest(
    X: pd.DataFrame,
    y: pd.Series,
    n_estimators: int = 100
) -> Dict[str, float]:
    """
    Random Forest Feature Importance로 가중치 산출
    """
    model = RandomForestRegressor(n_estimators=n_estimators, random_state=42)
    model.fit(X, y)

    importances = model.feature_importances_
    weights = importances / importances.sum()

    return dict(zip(X.columns, weights))
```

### 3.2 가중치 통합

```python
class WeightCalculator:
    """가중치 산출 및 관리"""

    def calculate_ensemble_weights(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        method_weights: Dict[str, float] = None
    ) -> Dict[str, float]:
        """
        여러 방법의 앙상블로 최종 가중치 산출

        Args:
            method_weights: 각 방법의 비중
                {"correlation": 0.3, "regression": 0.4, "rf": 0.3}
        """
        if method_weights is None:
            method_weights = {
                "correlation": 0.3,
                "regression": 0.4,
                "rf": 0.3
            }

        # 각 방법으로 가중치 산출
        corr_weights = self._correlation_weights(X, y)
        reg_weights = self._regression_weights(X, y)
        rf_weights = self._rf_weights(X, y)

        # 앙상블
        final_weights = {}
        for factor in X.columns:
            final_weights[factor] = (
                corr_weights.get(factor, 0) * method_weights["correlation"] +
                reg_weights.get(factor, 0) * method_weights["regression"] +
                rf_weights.get(factor, 0) * method_weights["rf"]
            )

        # 정규화
        total = sum(final_weights.values())
        return {k: v/total for k, v in final_weights.items()}
```

### 3.3 기본 가중치 (상관분석 전)

```python
# 초기 기본 가중치 (도메인 전문가 기반)
DEFAULT_CATEGORY_WEIGHTS = {
    "AVIATION": 0.25,      # 항공안전
    "SECURITY": 0.20,      # 보안위협
    "HEALTH": 0.15,        # 보건위험
    "OPERATIONAL": 0.15,   # 운영위험
    "WEATHER": 0.15,       # 기상위험
    "EXTERNAL": 0.10,      # 외부요인
}

DEFAULT_FACTOR_WEIGHTS = {
    # 기상
    "visibility": 0.25,
    "wind_speed": 0.20,
    "wind_gust": 0.15,
    "precipitation": 0.15,
    "snowfall": 0.15,
    "thunderstorm": 0.10,

    # 운영
    "congestion_rate": 0.40,
    "delay_rate": 0.35,
    "cancellation_rate": 0.25,

    # 보건
    "disease_alert_level": 0.50,
    "quarantine_cases": 0.30,
    "origin_country_risk": 0.20,

    # 보안
    "terror_threat_level": 0.50,
    "smuggling_cases": 0.30,
    "security_incidents": 0.20,

    # 외부
    "travel_advisory": 0.40,
    "airline_safety_rating": 0.30,
    "geopolitical_risk": 0.30,
}
```

---

## 4. 위험지수 계산

### 4.1 계산 공식

```
카테고리 점수 = Σ (요인i_정규화값 × 요인i_가중치) × 100
종합 위험지수 = Σ (카테고리j_점수 × 카테고리j_가중치)
```

### 4.2 구현

```python
# backend/app/services/risk_calculator.py

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import date

@dataclass
class CategoryScore:
    code: str
    name: str
    score: float
    level: str
    factors: Dict[str, float]

@dataclass
class RiskResult:
    airport_id: int
    airport_code: str
    date: date
    total_score: float
    risk_level: str
    categories: List[CategoryScore]

class RiskCalculator:
    """공항 위험지수 계산기"""

    RISK_LEVELS = [
        (0, 25, "LOW", "정상"),
        (25, 50, "MODERATE", "주의"),
        (50, 75, "HIGH", "경계"),
        (75, 100, "CRITICAL", "심각"),
    ]

    def __init__(
        self,
        category_weights: Dict[str, float] = None,
        factor_weights: Dict[str, float] = None
    ):
        self.category_weights = category_weights or DEFAULT_CATEGORY_WEIGHTS
        self.factor_weights = factor_weights or DEFAULT_FACTOR_WEIGHTS
        self.normalizer = FactorNormalizer()

    def calculate(
        self,
        airport_id: int,
        airport_code: str,
        target_date: date,
        raw_data: Dict[str, Dict[str, float]]
    ) -> RiskResult:
        """
        위험지수 계산

        Args:
            airport_id: 공항 ID
            airport_code: 공항 코드 (ICN, GMP 등)
            target_date: 계산 대상 날짜
            raw_data: 카테고리별 요인 데이터
                {
                    "WEATHER": {"visibility": 5000, "wind_speed": 12, ...},
                    "OPERATIONAL": {"congestion_rate": 85, ...},
                    ...
                }

        Returns:
            RiskResult: 계산 결과
        """
        category_scores = []

        for category_code, factors in raw_data.items():
            cat_score = self._calculate_category_score(category_code, factors)
            category_scores.append(cat_score)

        # 종합 점수 계산
        total_score = sum(
            cat.score * self.category_weights.get(cat.code, 0)
            for cat in category_scores
        )

        return RiskResult(
            airport_id=airport_id,
            airport_code=airport_code,
            date=target_date,
            total_score=round(total_score, 2),
            risk_level=self._get_risk_level(total_score),
            categories=category_scores
        )

    def _calculate_category_score(
        self,
        category_code: str,
        factors: Dict[str, float]
    ) -> CategoryScore:
        """카테고리별 점수 계산"""
        normalized_factors = {}
        weighted_sum = 0
        total_weight = 0

        for factor_code, value in factors.items():
            # 정규화
            normalized = self.normalizer.normalize(factor_code, value)
            normalized_factors[factor_code] = normalized

            # 가중 합산
            weight = self.factor_weights.get(factor_code, 1.0)
            weighted_sum += normalized * weight
            total_weight += weight

        score = weighted_sum / total_weight if total_weight > 0 else 0

        category_names = {
            "AVIATION": "항공안전",
            "SECURITY": "보안위협",
            "HEALTH": "보건위험",
            "OPERATIONAL": "운영위험",
            "WEATHER": "기상위험",
            "EXTERNAL": "외부요인",
        }

        return CategoryScore(
            code=category_code,
            name=category_names.get(category_code, category_code),
            score=round(score, 2),
            level=self._get_risk_level(score),
            factors=normalized_factors
        )

    def _get_risk_level(self, score: float) -> str:
        """점수에 따른 위험등급 반환"""
        for min_val, max_val, level, _ in self.RISK_LEVELS:
            if min_val <= score < max_val:
                return level
        return "CRITICAL"
```

---

## 5. 알림 로직

### 5.1 알림 조건

```python
@dataclass
class AlertRule:
    code: str
    name: str
    condition: str
    threshold: float
    severity: str  # INFO, WARNING, CRITICAL

ALERT_RULES = [
    # 종합 위험지수
    AlertRule("TOTAL_HIGH", "고위험 상태", "total_score >= threshold", 50, "WARNING"),
    AlertRule("TOTAL_CRITICAL", "긴급 위험 상태", "total_score >= threshold", 75, "CRITICAL"),

    # 급격한 변화
    AlertRule("RAPID_INCREASE", "위험지수 급상승", "score_change >= threshold", 20, "WARNING"),

    # 카테고리별
    AlertRule("WEATHER_CRITICAL", "기상 위험", "weather_score >= threshold", 70, "CRITICAL"),
    AlertRule("SECURITY_HIGH", "보안 위협", "security_score >= threshold", 60, "CRITICAL"),
    AlertRule("HEALTH_HIGH", "보건 위험", "health_score >= threshold", 60, "WARNING"),
]
```

### 5.2 알림 서비스

```python
# backend/app/services/alert_service.py

from typing import List
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Alert:
    id: str
    airport_code: str
    rule_code: str
    severity: str
    message: str
    score: float
    created_at: datetime

class AlertService:
    def __init__(self, email_service: EmailService):
        self.email_service = email_service
        self.rules = ALERT_RULES

    def check_and_create_alerts(
        self,
        risk_result: RiskResult,
        previous_result: Optional[RiskResult] = None
    ) -> List[Alert]:
        """위험지수 결과를 확인하고 필요시 알림 생성"""
        alerts = []

        for rule in self.rules:
            if self._evaluate_rule(rule, risk_result, previous_result):
                alert = self._create_alert(rule, risk_result)
                alerts.append(alert)

                # CRITICAL 알림은 이메일 발송
                if rule.severity == "CRITICAL":
                    self._send_email_alert(alert)

        return alerts

    def _evaluate_rule(
        self,
        rule: AlertRule,
        current: RiskResult,
        previous: Optional[RiskResult]
    ) -> bool:
        """알림 규칙 평가"""
        context = {
            "total_score": current.total_score,
            "threshold": rule.threshold,
        }

        # 카테고리별 점수 추가
        for cat in current.categories:
            context[f"{cat.code.lower()}_score"] = cat.score

        # 이전 결과와 비교
        if previous:
            context["score_change"] = current.total_score - previous.total_score
        else:
            context["score_change"] = 0

        try:
            return eval(rule.condition, {"__builtins__": {}}, context)
        except:
            return False

    def _send_email_alert(self, alert: Alert):
        """긴급 알림 이메일 발송"""
        self.email_service.send(
            subject=f"[긴급] {alert.airport_code} 공항 위험 알림",
            body=f"""
            공항: {alert.airport_code}
            위험등급: {alert.severity}
            메시지: {alert.message}
            현재 점수: {alert.score}
            발생 시각: {alert.created_at}

            즉시 확인이 필요합니다.
            """,
            recipients=self._get_alert_recipients(alert.airport_code)
        )
```

---

## 6. 모델 검증

### 6.1 백테스트

```python
def backtest_model(
    historical_data: pd.DataFrame,
    incident_data: pd.DataFrame,
    weights: Dict[str, float],
    threshold: float = 50
) -> Dict:
    """
    과거 데이터로 모델 성능 검증

    Returns:
        precision: 고위험 판정 시 실제 사고 발생 비율
        recall: 실제 사고 발생 시 고위험 판정 비율
        f1_score: 조화평균
    """
    # 위험지수 계산
    calculator = RiskCalculator(factor_weights=weights)
    predictions = []

    for _, row in historical_data.iterrows():
        score = calculator.calculate_simple(row.to_dict())
        predictions.append({
            "date": row["date"],
            "airport_id": row["airport_id"],
            "predicted_high_risk": score >= threshold
        })

    # 실제 사고 발생 여부
    pred_df = pd.DataFrame(predictions)
    merged = pd.merge(pred_df, incident_data, on=["date", "airport_id"])
    merged["actual_incident"] = merged["incident_count"] > 0

    # 성능 지표 계산
    tp = ((merged["predicted_high_risk"]) & (merged["actual_incident"])).sum()
    fp = ((merged["predicted_high_risk"]) & (~merged["actual_incident"])).sum()
    fn = ((~merged["predicted_high_risk"]) & (merged["actual_incident"])).sum()

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "true_positives": int(tp),
        "false_positives": int(fp),
        "false_negatives": int(fn)
    }
```

### 6.2 가중치 갱신 주기

```python
# 매주 월요일 새벽 3시에 가중치 재계산
@celery_app.task
def recalculate_weights():
    """가중치 주기적 재계산"""
    analyzer = CorrelationAnalyzer()
    calculator = WeightCalculator()

    # 최근 1년 데이터로 분석
    factor_data = get_factor_data(days=365)
    incident_data = get_incident_data(days=365)

    # 상관분석
    correlations = analyzer.analyze(factor_data, incident_data)

    # 새 가중치 산출
    new_weights = calculator.calculate_ensemble_weights(
        factor_data,
        incident_data["severity_score"]
    )

    # 가중치 이력 저장
    save_weight_history(new_weights, correlations)

    # 활성 가중치 업데이트
    update_active_weights(new_weights)

    return {"status": "success", "weights": new_weights}
```

---

## 7. 향후 개선 방향

### 7.1 예측 모델 도입
- 현재: 현재 상태 기반 위험지수
- 개선: 시계열 예측 모델로 미래 위험 예측 (LSTM, Prophet)

### 7.2 이상탐지
- 비정상적인 패턴 자동 감지
- Isolation Forest, Autoencoder 활용

### 7.3 설명 가능한 AI
- 위험지수 상승 원인 자동 분석
- SHAP, LIME 활용
