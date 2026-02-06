import { useQuery } from '@tanstack/react-query';
import api from '@/services/api';

interface InternationalIncident {
  title: string;
  incident_date: string;
  country_code: string;
  severity: string;
  risk_score: number;
}

interface InternationalWeather {
  airport_name: string;
  country_code: string;
  risk_score: number;
  weather_phenomena: string;
  wind_speed_kt: number;
}

interface SummaryData {
  incidents: {
    total: number;
    high_risk: number;
    recent: InternationalIncident[];
  };
  weather: {
    total: number;
    high_risk: number;
    alerts: InternationalWeather[];
  };
}

export default function InternationalAlerts() {
  const { data, isLoading } = useQuery<SummaryData>({
    queryKey: ['internationalSummary'],
    queryFn: async () => {
      const { data } = await api.get('/international/summary');
      return data;
    },
    refetchInterval: 300000, // 5분
  });

  if (isLoading || !data) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-slate-800 mb-4">해외 위험 현황</h3>
        <div className="text-sm text-slate-400">불러오는 중...</div>
      </div>
    );
  }

  const severityColor: Record<string, string> = {
    fatal: 'bg-red-100 text-red-700',
    serious: 'bg-orange-100 text-orange-700',
    minor: 'bg-yellow-100 text-yellow-700',
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-slate-800 mb-4">해외 위험 현황</h3>

      {/* 요약 */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-slate-50 rounded p-3">
          <div className="text-xs text-slate-500">항공사고</div>
          <div className="text-xl font-bold text-slate-800">{data.incidents.total}건</div>
          {data.incidents.high_risk > 0 && (
            <div className="text-xs text-red-500">{data.incidents.high_risk}건 고위험</div>
          )}
        </div>
        <div className="bg-slate-50 rounded p-3">
          <div className="text-xs text-slate-500">기상 경보</div>
          <div className="text-xl font-bold text-slate-800">{data.weather.high_risk}건</div>
          <div className="text-xs text-slate-400">{data.weather.total}개 공항 모니터링</div>
        </div>
      </div>

      {/* 최근 사고 */}
      {data.incidents.recent.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-medium text-slate-500 uppercase">최근 해외 사고</div>
          {data.incidents.recent.slice(0, 3).map((item, idx) => (
            <div key={idx} className="flex items-start justify-between py-2 border-b border-slate-100 last:border-0">
              <div className="flex-1 min-w-0">
                <div className="text-sm text-slate-700 truncate">{item.title}</div>
                <div className="text-xs text-slate-400">{item.incident_date} | {item.country_code}</div>
              </div>
              <span className={`ml-2 text-xs px-2 py-0.5 rounded ${severityColor[item.severity] || 'bg-slate-100 text-slate-600'}`}>
                {item.severity}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* 기상 경보 */}
      {data.weather.alerts.length > 0 && (
        <div className="mt-4 space-y-2">
          <div className="text-xs font-medium text-slate-500 uppercase">해외 기상 경보</div>
          {data.weather.alerts.slice(0, 3).map((item, idx) => (
            <div key={idx} className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0">
              <div>
                <div className="text-sm text-slate-700">{item.airport_name}</div>
                <div className="text-xs text-slate-400">
                  {item.weather_phenomena || 'N/A'} | {item.wind_speed_kt}kt
                </div>
              </div>
              <span className={`text-sm font-medium ${
                item.risk_score >= 60 ? 'text-red-600' :
                item.risk_score >= 40 ? 'text-orange-600' :
                'text-slate-600'
              }`}>
                {item.risk_score}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
