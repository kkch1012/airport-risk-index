import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import {
  Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Area, ReferenceLine, ComposedChart,
} from 'recharts';
import api from '@/services/api';
import { fetchForecast } from '@/services/api';
import type { AirportForecastResponse } from '@/types';

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

interface ChartDataPoint {
  date: string;
  total_score?: number;
  forecast?: number;
  forecast_lower?: number;
  forecast_upper?: number;
}

const METHOD_LABELS: Record<string, string> = {
  holt_linear: 'forecast.holtLinear',
  linear_fallback: 'forecast.linearFallback',
  none: 'forecast.none',
};

export default function TimeSeriesChart() {
  const { t } = useTranslation();
  const [period, setPeriod] = useState('1M');
  const [airportCode, setAirportCode] = useState<string>('');
  const [showForecast, setShowForecast] = useState(true);

  const PERIOD_OPTIONS = [
    { value: '1W', label: t('timeSeries.period1W') },
    { value: '1M', label: t('timeSeries.period1M') },
    { value: '3M', label: t('timeSeries.period3M') },
    { value: '6M', label: t('timeSeries.period6M') },
  ];

  const { data, isLoading } = useQuery<{ data: TimeSeriesDataPoint[] }>({
    queryKey: ['timeSeries', period, airportCode],
    queryFn: async () => {
      const params: Record<string, string> = { period };
      if (airportCode) params.airport_code = airportCode;
      const { data } = await api.get('/analytics/time-series', { params });
      return data;
    },
  });

  const { data: forecastData } = useQuery<AirportForecastResponse>({
    queryKey: ['forecast', airportCode],
    queryFn: () => fetchForecast(airportCode),
    enabled: !!airportCode && showForecast,
  });

  const hasForecast = forecastData && forecastData.predictions.length > 0;

  // 실측 + 예측 데이터 병합
  const chartData = useMemo<ChartDataPoint[]>(() => {
    const historical: ChartDataPoint[] = (data?.data || []).map((d) => ({
      date: d.date,
      total_score: d.total_score,
    }));

    if (!hasForecast || !forecastData) return historical;

    // 마지막 실측 데이터 포인트를 예측 시작점으로 연결
    const lastHistorical = historical[historical.length - 1];
    const forecastPoints: ChartDataPoint[] = [];

    if (lastHistorical) {
      forecastPoints.push({
        date: lastHistorical.date,
        forecast: lastHistorical.total_score,
        forecast_lower: lastHistorical.total_score,
        forecast_upper: lastHistorical.total_score,
      });
    }

    for (const pt of forecastData.predictions) {
      forecastPoints.push({
        date: pt.date,
        forecast: pt.value,
        forecast_lower: pt.lower_ci,
        forecast_upper: pt.upper_ci,
      });
    }

    return [...historical, ...forecastPoints];
  }, [data, forecastData, hasForecast]);

  // 예측/실측 경계 날짜
  const boundaryDate = data?.data?.length
    ? data.data[data.data.length - 1].date
    : undefined;

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-slate-800">{t('timeSeries.title')}</h3>
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder={t('timeSeries.airportCode')}
            value={airportCode}
            onChange={(e) => setAirportCode(e.target.value.toUpperCase())}
            className="w-24 px-2 py-1 text-sm border border-slate-300 rounded"
          />
          {airportCode && (
            <button
              onClick={() => setShowForecast(!showForecast)}
              className={`px-2 py-1 text-xs rounded transition-colors ${
                showForecast
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {showForecast ? t('forecast.hideForecast') : t('forecast.showForecast')}
            </button>
          )}
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
        <div className="h-64 flex items-center justify-center text-slate-400">{t('common.loadingShort')}</div>
      ) : !chartData.length ? (
        <div className="h-64 flex items-center justify-center text-slate-400">{t('common.noData')}</div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#94a3b8" />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} stroke="#94a3b8" />
            <Tooltip
              contentStyle={{ borderRadius: '8px', fontSize: '12px' }}
              formatter={(value: number, name: string) => {
                const labels: Record<string, string> = {
                  total_score: t('forecast.actualLabel'),
                  forecast: t('forecast.forecastLabel'),
                  forecast_upper: t('forecast.confidenceInterval'),
                  forecast_lower: t('forecast.confidenceInterval'),
                };
                return [value?.toFixed(1), labels[name] || name];
              }}
            />
            <Legend wrapperStyle={{ fontSize: '12px' }} />

            {/* 실측 데이터 (실선) */}
            <Line
              type="monotone"
              dataKey="total_score"
              name={t('forecast.actualLabel')}
              stroke={CATEGORY_COLORS.total}
              strokeWidth={2}
              dot={false}
              connectNulls={false}
            />

            {/* 예측 신뢰구간 (반투명 영역) */}
            {hasForecast && (
              <Area
                type="monotone"
                dataKey="forecast_upper"
                stroke="none"
                fill="#6366f1"
                fillOpacity={0.1}
                connectNulls={false}
              />
            )}
            {hasForecast && (
              <Area
                type="monotone"
                dataKey="forecast_lower"
                stroke="none"
                fill="#ffffff"
                fillOpacity={1}
                connectNulls={false}
              />
            )}

            {/* 예측 데이터 (점선) */}
            {hasForecast && (
              <Line
                type="monotone"
                dataKey="forecast"
                name={t('forecast.forecastLabel')}
                stroke="#6366f1"
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={false}
                connectNulls={false}
              />
            )}

            {/* 실측/예측 경계선 */}
            {hasForecast && boundaryDate && (
              <ReferenceLine
                x={boundaryDate}
                stroke="#94a3b8"
                strokeDasharray="3 3"
                strokeWidth={1}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* 예측 메트릭 정보 바 */}
      {hasForecast && forecastData && (
        <div className="mt-3 flex items-center gap-4 text-xs text-slate-500 border-t border-slate-100 pt-3">
          <span>
            {t('forecast.method')}: {t(METHOD_LABELS[forecastData.metrics.method] || forecastData.metrics.method)}
          </span>
          <span>
            {t('forecast.mae')}: {forecastData.metrics.mae.toFixed(1)}
          </span>
          <span>
            {t('forecast.dataPoints')}: {t('forecast.days', { count: forecastData.metrics.data_points_used })}
          </span>
          <span className="ml-auto text-indigo-500">
            {t('forecast.confidenceInterval')}
          </span>
        </div>
      )}
    </div>
  );
}
