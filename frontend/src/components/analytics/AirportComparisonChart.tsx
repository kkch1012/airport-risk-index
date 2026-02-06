import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Legend, Tooltip,
} from 'recharts';
import { fetchComparison } from '@/services/api';

const AIRPORT_OPTIONS = [
  { code: 'ICN', name: '인천' },
  { code: 'GMP', name: '김포' },
  { code: 'PUS', name: '김해' },
  { code: 'CJU', name: '제주' },
  { code: 'TAE', name: '대구' },
  { code: 'CJJ', name: '청주' },
  { code: 'KWJ', name: '광주' },
  { code: 'MWX', name: '무안' },
];

const COLORS = ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b'];

const categoryLabels: Record<string, string> = {
  weather: '기상',
  aviation: '항공',
  security: '보안',
  health: '보건',
  operational: '운영',
  external: '외부',
};

export default function AirportComparisonChart() {
  const [selected, setSelected] = useState<string[]>(['ICN', 'PUS']);

  const { data, isLoading } = useQuery({
    queryKey: ['comparison', selected],
    queryFn: () => fetchComparison(selected),
    enabled: selected.length >= 2,
  });

  const toggleAirport = (code: string) => {
    setSelected((prev) => {
      if (prev.includes(code)) {
        return prev.length > 2 ? prev.filter((c) => c !== code) : prev;
      }
      return prev.length < 4 ? [...prev, code] : prev;
    });
  };

  // 레이더 차트용 데이터 변환
  const chartData = data?.comparison
    ? Object.keys(data.comparison[0]?.categories || {}).map((cat) => {
        const point: Record<string, string | number> = {
          category: categoryLabels[cat] || cat,
        };
        data.comparison.forEach((airport) => {
          point[airport.code] = airport.categories[cat] || 0;
        });
        return point;
      })
    : [];

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-slate-800 mb-4">공항 비교</h3>

      {/* 공항 선택 */}
      <div className="flex flex-wrap gap-2 mb-4">
        {AIRPORT_OPTIONS.map((apt) => (
          <button
            key={apt.code}
            onClick={() => toggleAirport(apt.code)}
            className={`px-3 py-1 text-sm rounded-full border ${
              selected.includes(apt.code)
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white text-slate-600 border-slate-300 hover:border-blue-400'
            }`}
          >
            {apt.name} ({apt.code})
          </button>
        ))}
      </div>
      <div className="text-xs text-slate-400 mb-4">2~4개 공항 선택 가능</div>

      {isLoading ? (
        <div className="h-64 flex items-center justify-center text-slate-400">로딩 중...</div>
      ) : !chartData.length ? (
        <div className="h-64 flex items-center justify-center text-slate-400">데이터가 없습니다</div>
      ) : (
        <ResponsiveContainer width="100%" height={350}>
          <RadarChart data={chartData}>
            <PolarGrid stroke="#e2e8f0" />
            <PolarAngleAxis dataKey="category" tick={{ fontSize: 12 }} />
            <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={{ borderRadius: '8px', fontSize: '12px' }} />
            <Legend wrapperStyle={{ fontSize: '12px' }} />
            {data?.comparison.map((airport, i) => (
              <Radar
                key={airport.code}
                name={`${airport.name} (${airport.code})`}
                dataKey={airport.code}
                stroke={COLORS[i % COLORS.length]}
                fill={COLORS[i % COLORS.length]}
                fillOpacity={0.15}
              />
            ))}
          </RadarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
