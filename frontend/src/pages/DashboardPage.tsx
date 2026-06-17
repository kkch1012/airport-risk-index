import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { fetchDashboard } from '@/services/api';
import { useRiskUpdates } from '@/hooks/useRiskUpdates';
import RiskBadge from '@/components/common/RiskBadge';
import RiskGauge from '@/components/common/RiskGauge';
import {
  RiskDistributionChart,
  AlertList,
} from '@/components/dashboard';
import InternationalAlerts from '@/components/dashboard/InternationalAlerts';
import NewsFeed from '@/components/dashboard/NewsFeed';
import type { RiskLevel } from '@/types';

export default function DashboardPage() {
  const { t, i18n } = useTranslation();
  const { wsStatus } = useRiskUpdates();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboard,
    refetchInterval: wsStatus === 'connected' ? false : 60000,
  });

  // 훅은 항상 early return보다 위에서 호출해야 한다(React Hooks 규칙).
  // data가 아직 없을 수 있으므로 null-safe 처리.
  const riskDistribution = useMemo(
    () => (['LOW', 'MODERATE', 'HIGH', 'CRITICAL'] as RiskLevel[]).map((level) => ({
      level,
      count: data?.airports.filter((a) => a.level === level).length ?? 0,
    })),
    [data?.airports],
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <div className="text-slate-500">{t('common.loading')}</div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="text-red-500 text-xl mb-2">{t('common.error')}</div>
          <button
            onClick={() => refetch()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            {t('common.retry')}
          </button>
        </div>
      </div>
    );
  }

  const locale = i18n.language === 'ko' ? 'ko-KR' : 'en-US';

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold text-slate-800">{t('dashboard.title')}</h1>
            <span
              className={`inline-block w-2 h-2 rounded-full ${
                wsStatus === 'connected' ? 'bg-green-500' :
                wsStatus === 'connecting' ? 'bg-yellow-500 animate-pulse' :
                'bg-slate-300'
              }`}
              title={
                wsStatus === 'connected' ? t('ws.connected') :
                wsStatus === 'connecting' ? t('ws.connecting') :
                t('ws.offline')
              }
            />
          </div>
          <p className="text-slate-500">{t('dashboard.subtitle')}</p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isLoading}
          className="px-4 py-2 text-sm bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg flex items-center space-x-2 disabled:opacity-50"
        >
          <span>{t('common.refresh')}</span>
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>

      {/* 요약 카드 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-slate-500">{t('dashboard.totalAirports')}</div>
              <div className="text-3xl font-bold text-slate-800">{t('common.count', { count: data.summary.total_airports })}</div>
            </div>
            <div className="text-4xl">✈️</div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-slate-500">{t('dashboard.highRiskAirports')}</div>
              <div className={`text-3xl font-bold ${data.summary.high_risk_count > 0 ? 'text-orange-600' : 'text-green-600'}`}>
                {t('common.count', { count: data.summary.high_risk_count })}
              </div>
            </div>
            <div className="text-4xl">{data.summary.high_risk_count > 0 ? '⚠️' : '✅'}</div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-slate-500">{t('dashboard.avgRiskIndex')}</div>
              <div className="text-3xl font-bold text-slate-800">{data.summary.average_score}</div>
            </div>
            <RiskGauge score={data.summary.average_score} size="sm" showLabel={false} />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-slate-500">{t('dashboard.activeAlerts')}</div>
              <div className={`text-3xl font-bold ${data.alerts.length > 0 ? 'text-red-600' : 'text-slate-800'}`}>
                {t('common.countCase', { count: data.alerts.length })}
              </div>
            </div>
            <div className="text-4xl">{data.alerts.length > 0 ? '🔔' : '🔕'}</div>
          </div>
        </div>
      </div>

      {/* 차트 및 알림 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RiskDistributionChart data={riskDistribution} />
        <AlertList alerts={data.alerts} />
      </div>

      {/* 해외 현황 및 뉴스 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <InternationalAlerts />
        <NewsFeed />
      </div>

      {/* 공항 목록 */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-800">{t('dashboard.airportRiskTable')}</h2>
          <p className="text-sm text-slate-500 mt-1">{t('dashboard.airportRiskTableDesc')}</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase">{t('dashboard.rank')}</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase">{t('dashboard.airport')}</th>
                <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase">{t('dashboard.totalRiskIndex')}</th>
                <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase">{t('dashboard.weatherRisk')}</th>
                <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase">{t('dashboard.grade')}</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {data.airports.map((airport, idx) => (
                <tr key={airport.code} className="hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-medium ${
                      idx === 0 ? 'bg-yellow-100 text-yellow-800' :
                      idx === 1 ? 'bg-slate-200 text-slate-700' :
                      idx === 2 ? 'bg-orange-100 text-orange-800' :
                      'bg-slate-100 text-slate-600'
                    }`}>
                      {idx + 1}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="font-medium text-slate-800">{airport.name}</div>
                    <div className="text-sm text-slate-500">{airport.code}</div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex justify-center">
                      <RiskGauge score={airport.score} size="sm" showLabel={false} />
                    </div>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <span className={`text-sm font-medium ${
                      (airport.weather_score ?? 0) >= 50 ? 'text-orange-600' : 'text-slate-600'
                    }`}>
                      {airport.weather_score?.toFixed(1) ?? '-'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <RiskBadge level={airport.level} />
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Link
                      to={`/airport/${airport.code}`}
                      className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-lg transition-colors"
                    >
                      {t('dashboard.detail')}
                      <svg className="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 업데이트 시간 */}
      <div className="text-center text-sm text-slate-500">
        {t('common.lastUpdated', { time: new Date(data.summary.updated_at).toLocaleString(locale) })}
      </div>
    </div>
  );
}
