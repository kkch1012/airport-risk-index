import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { fetchCorrelations, fetchWeights, fetchTrends } from '@/services/api';
import TimeSeriesChart from '@/components/analytics/TimeSeriesChart';
import CorrelationHeatmap from '@/components/analytics/CorrelationHeatmap';
import AirportComparisonChart from '@/components/analytics/AirportComparisonChart';
import ExportButtons from '@/components/common/ExportButtons';

type Tab = 'overview' | 'timeseries' | 'correlation' | 'comparison';

export default function AnalyticsPage() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<Tab>('overview');

  const TABS = useMemo<{ key: Tab; label: string }[]>(() => [
    { key: 'overview', label: t('analytics.tabOverview') },
    { key: 'timeseries', label: t('analytics.tabTimeSeries') },
    { key: 'correlation', label: t('analytics.tabCorrelation') },
    { key: 'comparison', label: t('analytics.tabComparison') },
  ], [t]);

  const { data: correlations, isLoading: loadingCorr } = useQuery({
    queryKey: ['correlations'],
    queryFn: fetchCorrelations,
    enabled: activeTab === 'overview',
  });

  const { data: weights, isLoading: loadingWeights } = useQuery({
    queryKey: ['weights'],
    queryFn: fetchWeights,
    enabled: activeTab === 'overview',
  });

  const { data: trends, isLoading: loadingTrends } = useQuery({
    queryKey: ['trends'],
    queryFn: () => fetchTrends(undefined, undefined, '1M'),
    enabled: activeTab === 'overview',
  });

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">{t('analytics.title')}</h1>
          <p className="text-slate-500">{t('analytics.subtitle')}</p>
        </div>
        <ExportButtons />
      </div>

      {/* 탭 네비게이션 */}
      <div className="border-b border-slate-200">
        <nav className="flex gap-4">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* 개요 탭 */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {(loadingCorr || loadingWeights || loadingTrends) ? (
            <div className="flex items-center justify-center h-64">
              <div className="text-slate-500">{t('common.loading')}</div>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* 상관분석 결과 */}
              <div className="bg-white rounded-lg shadow p-6">
                <h2 className="text-lg font-semibold text-slate-800 mb-4">{t('analytics.correlationResults')}</h2>
                {correlations && (
                  <div className="space-y-3">
                    {Object.entries(correlations.factors).map(([factor, data]) => (
                      <div key={factor} className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <span className="text-slate-700">{factor}</span>
                          {data.significant && (
                            <span className="text-xs text-green-600 bg-green-100 px-1.5 py-0.5 rounded">
                              {t('analytics.significant')}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center space-x-4 text-sm">
                          <span className="text-slate-500">
                            {t('analytics.incidentCount')}: <span className={data.incident_count > 0 ? 'text-red-600' : 'text-blue-600'}>
                              {data.incident_count > 0 ? '+' : ''}{data.incident_count.toFixed(2)}
                            </span>
                          </span>
                          <span className="text-slate-500">
                            {t('analytics.severityScore')}: <span className={data.severity_score > 0 ? 'text-red-600' : 'text-blue-600'}>
                              {data.severity_score > 0 ? '+' : ''}{data.severity_score.toFixed(2)}
                            </span>
                          </span>
                        </div>
                      </div>
                    ))}
                    <div className="mt-4 pt-4 border-t border-slate-200 text-sm text-slate-500">
                      {t('analytics.analysisPeriod', { count: correlations.sample_size })}
                    </div>
                  </div>
                )}
              </div>

              {/* 카테고리 가중치 */}
              <div className="bg-white rounded-lg shadow p-6">
                <h2 className="text-lg font-semibold text-slate-800 mb-4">{t('analytics.categoryWeights')}</h2>
                {weights && (
                  <div className="space-y-3">
                    {Object.entries(weights.category_weights).map(([category, weight]) => (
                      <div key={category}>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="text-slate-700 capitalize">{category}</span>
                          <span className="font-medium">{((weight as number) * 100).toFixed(0)}%</span>
                        </div>
                        <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-blue-500 transition-all"
                            style={{ width: `${(weight as number) * 100}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* 트렌드 통계 */}
              <div className="bg-white rounded-lg shadow p-6 lg:col-span-2">
                <h2 className="text-lg font-semibold text-slate-800 mb-4">{t('analytics.trendStats')}</h2>
                {trends && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="p-4 bg-slate-50 rounded-lg">
                      <div className="text-sm text-slate-500">{t('analytics.average')}</div>
                      <div className="text-2xl font-bold text-slate-800">
                        {trends.statistics.average.toFixed(1)}
                      </div>
                    </div>
                    <div className="p-4 bg-slate-50 rounded-lg">
                      <div className="text-sm text-slate-500">{t('analytics.min')}</div>
                      <div className="text-2xl font-bold text-green-600">
                        {trends.statistics.min.toFixed(1)}
                      </div>
                    </div>
                    <div className="p-4 bg-slate-50 rounded-lg">
                      <div className="text-sm text-slate-500">{t('analytics.max')}</div>
                      <div className="text-2xl font-bold text-red-600">
                        {trends.statistics.max.toFixed(1)}
                      </div>
                    </div>
                    <div className="p-4 bg-slate-50 rounded-lg">
                      <div className="text-sm text-slate-500">{t('analytics.trend')}</div>
                      <div className="text-2xl font-bold text-slate-800">
                        {trends.statistics.trend === 'increasing' ? t('analytics.trendIncreasing') :
                         trends.statistics.trend === 'decreasing' ? t('analytics.trendDecreasing') : t('analytics.trendStable')}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 시계열 탭 */}
      {activeTab === 'timeseries' && <TimeSeriesChart />}

      {/* 상관관계 탭 */}
      {activeTab === 'correlation' && <CorrelationHeatmap />}

      {/* 공항 비교 탭 */}
      {activeTab === 'comparison' && <AirportComparisonChart />}
    </div>
  );
}
