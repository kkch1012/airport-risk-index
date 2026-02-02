import { useQuery } from '@tanstack/react-query';
import { fetchCorrelations, fetchWeights, fetchTrends } from '@/services/api';

export default function AnalyticsPage() {
  const { data: correlations, isLoading: loadingCorr } = useQuery({
    queryKey: ['correlations'],
    queryFn: fetchCorrelations,
  });

  const { data: weights, isLoading: loadingWeights } = useQuery({
    queryKey: ['weights'],
    queryFn: fetchWeights,
  });

  const { data: trends, isLoading: loadingTrends } = useQuery({
    queryKey: ['trends'],
    queryFn: () => fetchTrends(undefined, undefined, '1M'),
  });

  const isLoading = loadingCorr || loadingWeights || loadingTrends;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-500">데이터를 불러오는 중...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div>
        <h1 className="text-2xl font-bold text-slate-800">분석</h1>
        <p className="text-slate-500">위험요인 상관분석 및 가중치 정보</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 상관분석 결과 */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-slate-800 mb-4">상관분석 결과</h2>
          {correlations && (
            <div className="space-y-3">
              {Object.entries(correlations.factors).map(([factor, data]) => (
                <div key={factor} className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-slate-700">{factor}</span>
                    {data.significant && (
                      <span className="text-xs text-green-600 bg-green-100 px-1.5 py-0.5 rounded">
                        유의미
                      </span>
                    )}
                  </div>
                  <div className="flex items-center space-x-4 text-sm">
                    <span className="text-slate-500">
                      사고수: <span className={data.incident_count > 0 ? 'text-red-600' : 'text-blue-600'}>
                        {data.incident_count > 0 ? '+' : ''}{data.incident_count.toFixed(2)}
                      </span>
                    </span>
                    <span className="text-slate-500">
                      심각도: <span className={data.severity_score > 0 ? 'text-red-600' : 'text-blue-600'}>
                        {data.severity_score > 0 ? '+' : ''}{data.severity_score.toFixed(2)}
                      </span>
                    </span>
                  </div>
                </div>
              ))}
              <div className="mt-4 pt-4 border-t border-slate-200 text-sm text-slate-500">
                분석 기간: {correlations.sample_size.toLocaleString()}개 샘플
              </div>
            </div>
          )}
        </div>

        {/* 카테고리 가중치 */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-slate-800 mb-4">카테고리 가중치</h2>
          {weights && (
            <div className="space-y-3">
              {Object.entries(weights.category_weights).map(([category, weight]) => (
                <div key={category}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-slate-700 capitalize">{category}</span>
                    <span className="font-medium">{(weight * 100).toFixed(0)}%</span>
                  </div>
                  <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500 transition-all"
                      style={{ width: `${weight * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 트렌드 통계 */}
        <div className="bg-white rounded-lg shadow p-6 lg:col-span-2">
          <h2 className="text-lg font-semibold text-slate-800 mb-4">트렌드 통계 (최근 1개월)</h2>
          {trends && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 bg-slate-50 rounded-lg">
                <div className="text-sm text-slate-500">평균</div>
                <div className="text-2xl font-bold text-slate-800">
                  {trends.statistics.average.toFixed(1)}
                </div>
              </div>
              <div className="p-4 bg-slate-50 rounded-lg">
                <div className="text-sm text-slate-500">최소</div>
                <div className="text-2xl font-bold text-green-600">
                  {trends.statistics.min.toFixed(1)}
                </div>
              </div>
              <div className="p-4 bg-slate-50 rounded-lg">
                <div className="text-sm text-slate-500">최대</div>
                <div className="text-2xl font-bold text-red-600">
                  {trends.statistics.max.toFixed(1)}
                </div>
              </div>
              <div className="p-4 bg-slate-50 rounded-lg">
                <div className="text-sm text-slate-500">추세</div>
                <div className="text-2xl font-bold text-slate-800">
                  {trends.statistics.trend === 'increasing' ? '📈 상승' :
                   trends.statistics.trend === 'decreasing' ? '📉 하락' : '➡️ 유지'}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
