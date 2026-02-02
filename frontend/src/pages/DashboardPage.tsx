import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { fetchDashboard } from '@/services/api';
import RiskBadge from '@/components/common/RiskBadge';
import RiskGauge from '@/components/common/RiskGauge';

export default function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboard,
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
      {/* 헤더 */}
      <div>
        <h1 className="text-2xl font-bold text-slate-800">대시보드</h1>
        <p className="text-slate-500">전체 공항 위험지수 현황</p>
      </div>

      {/* 요약 카드 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-slate-500">총 공항</div>
          <div className="text-3xl font-bold text-slate-800">{data.summary.total_airports}개</div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-slate-500">고위험 공항</div>
          <div className="text-3xl font-bold text-orange-600">{data.summary.high_risk_count}개</div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-slate-500">평균 위험지수</div>
          <div className="text-3xl font-bold text-slate-800">{data.summary.average_score}</div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-slate-500">활성 알림</div>
          <div className="text-3xl font-bold text-blue-600">{data.alerts.length}건</div>
        </div>
      </div>

      {/* 알림 패널 */}
      {data.alerts.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-slate-800 mb-4">알림</h2>
          <div className="space-y-2">
            {data.alerts.map((alert, idx) => (
              <div
                key={idx}
                className={`p-3 rounded-lg flex items-center justify-between ${
                  alert.severity === 'CRITICAL'
                    ? 'bg-red-50 border border-red-200'
                    : alert.severity === 'WARNING'
                    ? 'bg-yellow-50 border border-yellow-200'
                    : 'bg-blue-50 border border-blue-200'
                }`}
              >
                <div>
                  <span className="font-medium">{alert.airport}</span>
                  <span className="mx-2 text-slate-400">|</span>
                  <span className="text-slate-600">{alert.message}</span>
                </div>
                <span
                  className={`text-sm font-medium ${
                    alert.severity === 'CRITICAL'
                      ? 'text-red-600'
                      : alert.severity === 'WARNING'
                      ? 'text-yellow-600'
                      : 'text-blue-600'
                  }`}
                >
                  {alert.type}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 공항 목록 */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-800">공항별 위험지수</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase">순위</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase">공항</th>
                <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase">위험지수</th>
                <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase">등급</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {data.airports.map((airport, idx) => (
                <tr key={airport.code} className="hover:bg-slate-50">
                  <td className="px-6 py-4 text-sm text-slate-500">{idx + 1}</td>
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
                    <RiskBadge level={airport.level} />
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Link
                      to={`/airport/${airport.code}`}
                      className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                    >
                      상세보기
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
