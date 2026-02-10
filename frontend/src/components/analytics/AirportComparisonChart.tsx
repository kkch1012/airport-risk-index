import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Legend, Tooltip,
} from 'recharts';
import { fetchComparison } from '@/services/api';

const AIRPORT_CODES = ['ICN', 'GMP', 'PUS', 'CJU', 'TAE', 'CJJ', 'KWJ', 'MWX'] as const;

const COLORS = ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b'];

export default function AirportComparisonChart() {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<string[]>(['ICN', 'PUS']);

  const AIRPORT_OPTIONS = AIRPORT_CODES.map((code) => ({
    code,
    name: t(`airports.${code}`),
  }));

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

  const chartData = data?.comparison
    ? Object.keys(data.comparison[0]?.categories || {}).map((cat) => {
        const point: Record<string, string | number> = {
          category: t(`category.${cat}Short` as const, { defaultValue: cat }),
        };
        data.comparison.forEach((airport) => {
          point[airport.code] = airport.categories[cat] || 0;
        });
        return point;
      })
    : [];

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-slate-800 mb-4">{t('comparison.title')}</h3>

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
      <div className="text-xs text-slate-400 mb-4">{t('comparison.selectHint')}</div>

      {isLoading ? (
        <div className="h-64 flex items-center justify-center text-slate-400">{t('common.loadingShort')}</div>
      ) : !chartData.length ? (
        <div className="h-64 flex items-center justify-center text-slate-400">{t('common.noData')}</div>
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
