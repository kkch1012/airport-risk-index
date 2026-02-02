/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 위험등급 색상
        risk: {
          low: '#22c55e',       // 녹색
          moderate: '#eab308',  // 노란색
          high: '#f97316',      // 주황색
          critical: '#ef4444',  // 빨간색
        },
        // 카테고리 색상
        category: {
          aviation: '#3b82f6',    // 파랑
          security: '#ef4444',    // 빨강
          health: '#22c55e',      // 녹색
          operational: '#f59e0b', // 주황
          weather: '#6366f1',     // 인디고
          external: '#8b5cf6',    // 보라
        },
      },
    },
  },
  plugins: [],
}
