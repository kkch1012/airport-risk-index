import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { fetchAirportRisk } from '@/services/api';
import { useRiskUpdates } from '@/hooks/useRiskUpdates';
import RiskBadge from '@/components/common/RiskBadge';
import RiskGauge from '@/components/common/RiskGauge';
import ExportButtons from '@/components/common/ExportButtons';
import { CategoryBarChart } from '@/components/dashboard';
import type { CategoryCode } from '@/types';

const categoryIcons: Record<CategoryCode, string> = {
  weather: '🌦️',
  aviation: '✈️',
  security: '🛡️',
  health: '🏥',
  operational: '⚙️',
  external: '🌍',
};

const categoryColors: Record<CategoryCode, string> = {
  weather: 'bg-indigo-500',
  aviation: 'bg-blue-500',
  security: 'bg-red-500',
  health: 'bg-green-500',
  operational: 'bg-amber-500',
  external: 'bg-purple-500',
};

export default function AirportDetailPage() {
  const { t, i18n } = useTranslation();
  const { airportCode } = useParams<{ airportCode: string }>();
  const { wsStatus } = useRiskUpdates({ airportCode });

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['airportRisk', airportCode],
    queryFn: () => fetchAirportRisk(airportCode!),
    enabled: !!airportCode,
    refetchInterval: wsStatus === 'connected' ? false : 60000,
  });

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

  const categoryChartData = Object.entries(data.categories).map(([code, cat]) => ({
    code,
    name: t(`category.${code}` as const),
    score: cat.score,
  }));

  const locale = i18n.language === 'ko' ? 'ko-KR' : 'en-US';

  return (
    <div className="space-y-6">
      {/* 뒤로가기 */}
      <Link
        to="/"
        className="inline-flex items-center text-blue-600 hover:text-blue-800 text-sm"
      >
        <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        {t('detail.backToDashboard')}
      </Link>

      {/* 헤더 */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          <div>
            <div className="flex items-center space-x-3 mb-2">
              <span className="text-3xl">✈️</span>
              <h1 className="text-2xl font-bold text-slate-800">{data.airport.name}</h1>
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
            <div className="flex items-center space-x-4 text-slate-500">
              <span className="bg-slate-100 px-2 py-1 rounded text-sm font-mono">{data.airport.code}</span>
              <span>{data.date}</span>
            </div>
          </div>
          <div className="flex items-center space-x-6">
            <RiskGauge score={data.total_score} size="lg" />
            <div className="text-center">
              <RiskBadge level={data.risk_level} size="lg" />
              <p className="mt-2 text-sm text-slate-500">{t('detail.overallGrade')}</p>
            </div>
          </div>
        </div>

        {/* 데이터 소스 정보 */}
        {data.data_source && (
          <div className="mt-4 pt-4 border-t border-slate-200">
            <div className="flex flex-wrap gap-2">
              <span className="text-xs text-slate-500">{t('detail.dataSource')}:</span>
              <span className={`text-xs px-2 py-0.5 rounded ${
                data.data_source.weather === '실제 데이터'
                  ? 'bg-green-100 text-green-700'
                  : 'bg-yellow-100 text-yellow-700'
              }`}>
                {t('detail.dataSourceWeather', { value: data.data_source.weather })}
              </span>
              <span className="text-xs px-2 py-0.5 rounded bg-yellow-100 text-yellow-700">
                {t('detail.dataSourceOthers', { value: data.data_source.others })}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* 카테고리 차트 */}
      <CategoryBarChart data={categoryChartData} title={t('detail.categoryChart')} />

      {/* 카테고리별 상세 점수 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {(Object.entries(data.categories) as [CategoryCode, typeof data.categories[CategoryCode]][]).map(
          ([code, category]) => (
            <div key={code} className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-2">
                  <span className="text-2xl">{categoryIcons[code]}</span>
                  <div>
                    <h3 className="font-semibold text-slate-800">{category.name}</h3>
                    <p className="text-xs text-slate-500">{t(`categoryDesc.${code}` as const)}</p>
                  </div>
                </div>
                <RiskBadge level={category.level} size="sm" />
              </div>

              {/* 점수 바 */}
              <div className="mb-4">
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-slate-500">{t('detail.riskLevel')}</span>
                  <span className="font-bold text-lg">{category.score.toFixed(1)}</span>
                </div>
                <div className="h-3 bg-slate-200 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${categoryColors[code]} transition-all duration-500`}
                    style={{ width: `${Math.min(category.score, 100)}%` }}
                  />
                </div>
              </div>

              {/* 세부 요인 */}
              <div className="space-y-2 pt-3 border-t border-slate-100">
                <div className="text-xs font-medium text-slate-500 uppercase">{t('detail.subFactors')}</div>
                {Object.entries(category.factors).map(([factor, value]) => (
                  <div key={factor} className="flex justify-between items-center">
                    <span className="text-sm text-slate-600">
                      {t(`factors.${factor}` as const, { defaultValue: factor })}
                    </span>
                    <div className="flex items-center space-x-2">
                      <div className="w-20 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-slate-400"
                          style={{ width: `${Math.min(value, 100)}%` }}
                        />
                      </div>
                      <span className="text-sm font-medium text-slate-700 w-12 text-right">
                        {typeof value === 'number' ? value.toFixed(1) : value}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )
        )}
      </div>

      {/* 내보내기 + 업데이트 시간 */}
      <div className="flex items-center justify-between">
        <ExportButtons airportCode={airportCode} />
        <div className="text-sm text-slate-500">
          {t('common.lastUpdated', { time: new Date(data.updated_at).toLocaleString(locale) })}
        </div>
      </div>
    </div>
  );
}
