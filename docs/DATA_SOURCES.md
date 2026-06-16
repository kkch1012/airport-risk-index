# 데이터 소스 가이드

본 문서는 공항 위험지수 시스템이 실제로 사용하는 데이터 소스와 **폴백 우선순위**를 설명합니다.

---

## 데이터 확보 원칙 (2026-06 전환)

공항과의 외부 계약(SSO·운영자 내부데이터)이 불가하다는 전제 아래, **무료 공개 API + 웹 크롤링만으로**
위험지수를 산출합니다. (data.go.kr·기상청 키는 "계약"이 아니라 무료 신청이므로 그대로 활용)

각 수집기(collector)는 다음 순서로 동작합니다.

```
① 키가 있으면  → 공개 API (data.go.kr / 기상청)
② 키 없음/실패 → 무료 크롤링 폴백 (키 불필요)
③ 그래도 없음  → 빈 리스트 [] 반환 (= "데이터 없음")
```

> **핵심: 데이터가 없을 때 `random.uniform()` 같은 가짜 점수를 생성하지 않습니다.**
> 데이터가 없는 카테고리는 `has_data=False`로 표시되어 종합 위험지수 가중치에서 제외(재정규화)됩니다.
> (점수 모델은 [RISK_MODEL.md](RISK_MODEL.md) 참조)

뉴스 기반 폴백(운항 지연·여행경보)은 실측 통계가 아닌 **뉴스 신호량 기반 추정 프록시**이며,
산출 항목에 `is_proxy: True` 플래그가 붙습니다.

---

## 수집기별 소스 & 폴백

### 1. 기상위험 — `weather.py`

| 단계 | 소스 | 비고 |
|------|------|------|
| 1차 API | 기상청 단기예보((구)동네예보) 조회서비스 | `data.go.kr` 15084084, 격자(nx,ny) 기반 |
| 2차 폴백 | **aviationweather.gov METAR** (`/api/data/metar`) | 키 불필요. 국내공항 ICAO(RKSI 등)로 조회 |
| 3차 | `[]` (데이터 없음) | 소규모 공항(원주/사천/군산 등)은 METAR 미보고 → 자동 no-data |

- METAR 폴백은 원문(`rawOb`)에서 강수현상을 정규식으로 파싱(`_present_weather_from_raw`).
  `wxString` 필드가 비어오는 경우가 많기 때문.
- 단위 변환: knots→m/s(×0.514444), 기온/이슬점→Magnus 식으로 습도 추정.
- **라이브 검증됨** (15개 중 9개 공항 METAR 응답).

### 2. 운영위험 — `flight_status.py`

| 단계 | 소스 | 비고 |
|------|------|------|
| 1차 API | 한국공항공사 운항정보 | `data.go.kr` 15000126 / 15113771 |
| 2차 폴백 | **Google News RSS** 운항장애 신호 → **지연율 프록시** | `is_proxy: True` |
| 3차 | `[]` (데이터 없음) | |

- 폴백은 공항명 기준 뉴스 제목의 지연/결항 신호량을 버킷 매핑(`_signal_to_rate`).
  - 지연율 버킷: hits≥6→25%, ≥3→16%, ≥1→8%
  - 결항율 버킷: hits≥3→5%, ≥1→2%
  - `total_flights: 0` (실측 운항편수 없음을 명시)

### 3. 항공안전 — `aviation_safety.py`

| 단계 | 소스 | 비고 |
|------|------|------|
| 1차 | 항공철도사고조사위원회(ARAIB) 게시판 크롤링 | `araib.molit.go.kr` |
| 2차 | `[]` (데이터 없음) | mock 제거됨 |

### 4. 보건위험 — `health_risk.py`

| 단계 | 소스 | 비고 |
|------|------|------|
| 1차 API | 질병관리청 검역관리지역정보 | `data.go.kr` 15139251 |
| 2차 폴백 | **WHO Disease Outbreak News JSON API** (`/api/news/diseaseoutbreaknews`) | 키 불필요 (OData) |
| 3차 | `[]` (데이터 없음) | |

- 기존 WHO DON **RSS는 폐지(404)**되어 JSON API로 교체함.
- `$orderby=PublicationDate desc&$top=80`로 최신순 조회, **최근 180일(`WHO_DON_LOOKBACK_DAYS`)** + 취항 대상국만 유지.
- 영문 질병/국가 매핑(`DISEASE_EN_KEYWORDS`, `COUNTRY_EN_TO_ISO`) 추가. NIPAH(니파바이러스) 포함.
- **라이브 검증됨**.

### 5. 외부요인(여행경보) — `travel_advisory.py`

| 단계 | 소스 | 비고 |
|------|------|------|
| 1차 API | 외교부 0404 국가·지역별 여행경보 | `data.go.kr` 15095500 |
| 2차 폴백 | **Google News RSS** 불안정 신호 → **경보단계 프록시** | `is_proxy: True` |
| 3차 | `[]` (데이터 없음) | |

- 불안정 키워드: 테러/내전/쿠데타/시위/폭동/교전/비상사태/여행경보/납치.
- **과대경보 방지**: 폴백은 최대 2단계(여행자제)까지만 추정. hits≥4→"2", hits≥2→"1", 그 외 제외.
- **라이브 검증됨** (러시아/일본/미얀마 등).

### 6. 보안위협 — `security_threat.py`

| 단계 | 소스 | 비고 |
|------|------|------|
| 1차 | Google News RSS 키워드 스코어링 (테러/밀수/불법입국) | 공항 코드 자동 탐지 |
| 2차 | `[]` (데이터 없음) | mock 제거됨 |

### 7. 뉴스 — `news_crawler.py`

| 단계 | 소스 | 비고 |
|------|------|------|
| 1차 | Google News RSS 키워드 스코어링 (5개 카테고리) | 공항 코드 자동 탐지 |
| 2차 | `[]` (데이터 없음) | mock 제거됨 |

---

## 해외 데이터 소스

| 소스 | URL | 데이터 | 형식 |
|------|-----|--------|------|
| WHO Disease Outbreak News | who.int/api/news/diseaseoutbreaknews | 국제 감염병 발생 | JSON (OData) |
| The Aviation Herald | avherald.com | 국제 항공사건 | HTML 크롤링 |
| Aviation Weather (METAR) | aviationweather.gov/api/data/metar | 해외 주요공항 기상 | JSON |

> 과거 문서의 **Aviation Safety Network(ASN)** 는 The Aviation Herald로 교체됨.
> Global Terrorism Index(GTI)는 현재 미연동.

---

## 수집 주기

| 수집기 | 주기 |
|--------|------|
| WeatherCollector / InternationalWeatherCollector | 1시간 |
| FlightStatusCollector | 30분 |
| SecurityThreatCollector / NewsCrawler | 1시간 |
| HealthRiskCollector / TravelAdvisoryCollector | 6시간 |
| AviationSafetyCollector / InternationalAviationCollector | 6시간 |

---

## API 키 관리

```bash
# .env — 무료 신청 키 (없어도 폴백으로 동작, 데이터 정확도만 하락)
KMA_API_KEY=...           # 기상청
DATA_GO_KR_API_KEY=...    # 공공데이터포털
```

| 서비스 | 발급 URL |
|--------|----------|
| 기상청 단기예보 | https://www.data.go.kr/data/15084084/openapi.do |
| 한국공항공사 운항정보 | https://www.data.go.kr/data/15000126/openapi.do |
| 질병관리청 검역관리지역 | https://www.data.go.kr/data/15139251/openapi.do |
| 외교부 여행경보 | https://www.data.go.kr/data/15095500/openapi.do |

> aviationweather.gov · WHO JSON API · Google News RSS · The Aviation Herald 는 **키 불필요**.

---

## 크롤링 주의사항

- XML/RSS 파싱은 `defusedxml`로 처리(외부 엔티티 공격 방어).
- robots.txt 준수 및 요청 간 rate limiting 권장.
- 정부 사이트 중 `airportal.go.kr`, `0404.go.kr` 웹페이지는 JavaScript 렌더링 앱이라
  직접 스크레이핑 불가 → 공개 API(data.go.kr) 또는 Google News RSS 프록시로 대체함.
