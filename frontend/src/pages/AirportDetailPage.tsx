import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchAirportRisk } from '@/services/api';
import RiskBadge from '@/components/common/RiskBadge';
import RiskGauge from '@/components/common/RiskGauge';
import type { CategoryCode } from '@/types';

const categoryConfig: Record<CategoryCode, { name: string; icon: string; color: string }> = {
  aviation: { name: '항공안전', icon: '✈️', color: 'bg-blue-500' },
  security: { name: '보안위협', icon: '🛡️', color: 'bg-red-500' },
  health: { name: '보건위험', icon: '🏥', color: 'bg-green-500' },
  operational: { name: '운영위험', icon: '⚙️', color: 'bg-amber-500' },
  weather: { name: '기상위험', icon: '🌦️', color: 'bg-indigo-500' },
  external: { name: '외부요인', icon: '🌍', color: 'bg-purple-500' },
};

export default function AirportDetailPage() {
  const { airportCode } = useParams<{ airportCode: string }>();

  const { data, isLoading, error } = useQuery({
    queryKey: ['airportRisk', airportCode],
    queryFn: () => fetchAirportRisk(airportCode!),
    enabled: !!airportCode,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-500">데이터를 불러오는 중...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-500">데이터를 불러오는데 실패했습니다.</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 뒤로가기 */}
      <Link to="/" className="text-blue-600 hover:text-blue-800 text-sm">
        ← 대시보드로 돌아가기
      </Link>

      {/* 헤더 */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">{data.airport.name}</h1>
            <p className="text-slate-500">{data.airport.code} | {data.date}</p>
          </div>
          <div className="flex items-center space-x-4">
            <RiskGauge score={data.total_score} size="lg" />
            <div className="text-center">
              <RiskBadge level={data.risk_level} size="lg" />
              <p className="mt-1 text-sm text-slate-500">종합 위험등급</p>
            </div>
          </div>
        </div>
      </div>

      {/* 카테고리별 점수 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {(Object.entries(data.categories) as [CategoryCode, typeof data.categories[CategoryCode]][]).map(
          ([code, category]) => {
            const config = categoryConfig[code];
            return (
              <div key={code} className="bg-white rounded-lg shadow p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center space-x-2">
                    <span className="text-2xl">{config.icon}</span>
                    <h3 className="font-semibold text-slate-800">{category.name}</h3>
                  </div>
                  <RiskBadge level={category.level} size="sm" />
                </div>

                {/* 점수 바 */}
                <div className="mb-4">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-slate-500">위험도</span>
                    <span className="font-medium">{category.score.toFixed(1)}</span>
                  </div>
                  <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${config.color} transition-all duration-500`}
                      style={{ width: `${category.score}%` }}
                    />
                  </div>
                </div>

                {/* 세부 요인 */}
                <div className="space-y-2">
                  {Object.entries(category.factors).map(([factor, value]) => (
                    <div key={factor} className="flex justify-between text-sm">
                      <span className="text-slate-500">{factor}</span>
                      <span className="text-slate-700">{value.toFixed(1)}</span>
                    </div>
                  ))}
                </div>
              </div>
            );
          }
        )}
      </div>

      {/* 업데이트 시간 */}
      <div className="text-center text-sm text-slate-500">
        마지막 업데이트: {new Date(data.updated_at).toLocaleString('ko-KR')}
      </div>
    </div>
  );
}
