# ===========================================
# 공항 위험지수 시스템 - Frontend Dockerfile
# ===========================================

# 개발용 스테이지
FROM node:20-alpine AS development

WORKDIR /app

# 패키지 파일 복사 및 설치
COPY package*.json ./
RUN npm install

# 소스 복사
COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]


# 빌드 스테이지
FROM node:20-alpine AS builder

WORKDIR /app

ARG VITE_API_URL=http://localhost:8000/api/v1
ARG VITE_WS_URL=ws://localhost:8000/ws
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build


# 프로덕션 스테이지
FROM nginx:alpine AS production

# nginx 설정 복사
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 빌드된 파일 복사
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
