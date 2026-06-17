# 배포 가이드 — Render(백엔드, 무료) + Vercel(프론트)

> 프론트는 Vercel, 백엔드는 Render 무료 + SQLite. 둘 중 하나가 아니라 **둘을 연결**하는 구조다.
> (프론트=정적, 백엔드=API 서버) Vercel만으로는 백엔드를 못 돌리기 때문.

```
[브라우저] → Vercel(정적 프론트) --HTTPS--> Render(FastAPI 백엔드, SQLite)
                  VITE_API_URL 로 백엔드 주소 지정          CORS 로 Vercel 도메인 허용
```

---

## 1단계 — 백엔드를 Render에 배포

1. https://render.com 가입 (GitHub 계정으로 로그인 추천)
2. **New +** → **Blueprint** 선택
3. 이 GitHub 저장소(`kkch1012/airport-risk-index`) 연결 → 루트의 `render.yaml` 자동 감지
4. **Apply** → 빌드 시작 (첫 빌드 약 5~10분; pandas/scipy 설치 때문)
5. 완료되면 백엔드 URL이 생긴다 → 예: `https://airport-risk-backend.onrender.com`
6. 확인: 브라우저에서 `https://airport-risk-backend.onrender.com/health`
   → `{"status":"healthy",...}` 나오면 성공

> 무료 티어는 15분 미사용 시 잠든다. 첫 요청이 30~60초 느린 건 정상(콜드스타트).

---

## 2단계 — Vercel 프론트가 Render 백엔드를 보게 하기

1. Vercel 프로젝트 → **Settings → Environment Variables**
2. 추가:
   | Key | Value |
   |---|---|
   | `VITE_API_URL` | `https://airport-risk-backend.onrender.com/api/v1` |
   (끝에 **`/api/v1` 까지** 포함. 본인 Render URL로 교체)
3. **Deployments → 최신 배포 → Redeploy** (환경변수는 빌드 시점에 박히므로 재배포 필수)

---

## 3단계 — 백엔드 CORS에 Vercel 도메인 허용

1. Render → 백엔드 서비스 → **Environment** 탭
2. `CORS_ORIGINS_STR` 값을 본인 Vercel 도메인으로 수정
   예: `https://airport-risk-index.vercel.app,http://localhost:5173`
3. 저장 → 자동 재배포됨

---

## 4단계 — 확인

- Vercel 사이트 접속 → 대시보드에 15개 공항 점수 표시
- 공항 상세 → 카테고리 카드에 **추정치 / 데이터 없음** 배지 확인
- 안 되면 브라우저 개발자도구(F12) → Network 탭에서 `/api/v1/...` 요청이
  Render URL로 가는지, 200인지, CORS 에러 없는지 확인

---

## (선택) 데이터 더 채우기
`operational·aviation·security`가 "데이터 없음"으로 뜨는 건 정상(무료 키 없음 + 그 시점 크롤링 폴백 빔).
무료 키를 발급해 Render **Environment**에 넣으면 공개 API가 살아난다:
- `DATA_GO_KR_API_KEY` — https://www.data.go.kr (운항/항공안전/여행경보)
- `KMA_API_KEY` — 기상청 (기상; 없어도 METAR 폴백으로 채워짐)

## 참고 — 한계와 다음 단계
- SQLite는 재배포 시 초기화(데모엔 무방). 이력 영속화가 필요하면 Render Postgres(무료는 30일 만료) 또는 유료로 전환.
- Celery 워커(주기 수집)는 이 배포에 없음 — API는 호출 시점에 라이브 계산하므로 데모엔 충분.
