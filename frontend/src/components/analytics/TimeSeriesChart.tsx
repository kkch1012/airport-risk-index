import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import api from '@/services/api';

const PERIOD_OPTIONS = [
  { value: '1W', label: '1주' },
  { value: '1M', label: '1개월' },
  { value: '3M', label: '3개월' },
  { value: '6M', label: '6개월' },
];

const CATEGORY_COLORS: Record<string, string> = {
  total: '#334155',
  weather: '#6366f1',
  aviation: '#3b82f6',
  security: '#ef4444',
  health: '#22c55e',
  operational: '#f59e0b',
  external: '#a855f7',
};

interface TimeSeriesDataPoint {
  date: string;
  total_score: number;
  categories?: Record<string, number>;
}

export default function TimeSeriesChart() {
  const [period, setPeriod] = useState('1M');
  const [airportCode, setAirportCode] = useState<string>('');

  const { data, isLoading } = useQuery<{ data: TimeSeriesDataPoint[] }>({
    queryKey: ['timeSeries', period, airportCode],
    queryFn: async () => {
      const params: Record<string, string> = { period };
      if (airportCode) params.airport_code = airportCode;
      const { data } = await api.get('/analytics/time-series', { params });
      return data;
    },
  });

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-slate-800">위험지수 시계열</h3>
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="공항코드"
            value={airportCode}
            onChange={(e) => setAirportCode(e.target.value.toUpperCase())}
            className="w-24 px-2 py-1 text-sm border border-slate-300 rounded"
          />
          <div className="flex gap-1">
            {PERIOD_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setPeriod(opt.value)}
                className={`px-2 py-1 text-xs rounded ${
                  period === opt.value
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="h-64 flex items-center justify-center text-slate-400">로딩 중...</div>
      ) : !data?.data?.length ? (
        <div className="h-64 flex items-center justify-center text-slate-400">데이터가 없습니다</div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data.data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#94a3b8" />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} stroke="#94a3b8" />
            <Tooltip
              contentStyle={{ borderRadius: '8px', fontSize: '12px' }}
            />
            <Legend wrapperStyle={{ fontSize: '12px' }} />
            <Line
              type="monotone"
              dataKey="total_score"
              name="종합 위험지수"
              stroke={CATEGORY_COLORS.total}
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
