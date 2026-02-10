import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import api from '@/services/api';

interface InternationalIncident {
  title: string;
  link: string;
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
  const { t } = useTranslation();
  const { data, isLoading } = useQuery<SummaryData>({
    queryKey: ['internationalSummary'],
    queryFn: async () => {
      const { data } = await api.get('/international/summary');
      return data;
    },
    refetchInterval: 300000,
  });

  if (isLoading || !data) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-slate-800 mb-4">{t('international.title')}</h3>
        <div className="text-sm text-slate-400">{t('common.loadingShort')}</div>
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
      <h3 className="text-lg font-semibold text-slate-800 mb-4">{t('international.title')}</h3>

      {/* 요약 */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-slate-50 rounded p-3">
          <div className="text-xs text-slate-500">{t('international.incidents')}</div>
          <div className="text-xl font-bold text-slate-800">{t('common.countCase', { count: data.incidents.total })}</div>
          {data.incidents.high_risk > 0 && (
            <div className="text-xs text-red-500">{t('international.highRisk', { count: data.incidents.high_risk })}</div>
          )}
        </div>
        <div className="bg-slate-50 rounded p-3">
          <div className="text-xs text-slate-500">{t('international.weatherAlerts')}</div>
          <div className="text-xl font-bold text-slate-800">{t('common.countCase', { count: data.weather.high_risk })}</div>
          <div className="text-xs text-slate-400">{t('international.monitoring', { count: data.weather.total })}</div>
        </div>
      </div>

      {/* 최근 사고 */}
      {data.incidents.recent.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-medium text-slate-500 uppercase">{t('international.recentIncidents')}</div>
          {data.incidents.recent.slice(0, 3).map((item, idx) => (
            <a
              key={idx}
              href={item.link}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-start justify-between py-2 border-b border-slate-100 last:border-0 group cursor-pointer hover:bg-slate-50 -mx-2 px-2 rounded transition-colors"
            >
              <div className="flex-1 min-w-0">
                <div className="text-sm text-slate-700 group-hover:text-blue-600 truncate transition-colors">{item.title}</div>
                <div className="text-xs text-slate-400">{item.incident_date} | {item.country_code}</div>
              </div>
              <span className={`ml-2 text-xs px-2 py-0.5 rounded flex-shrink-0 ${severityColor[item.severity] || 'bg-slate-100 text-slate-600'}`}>
                {item.severity}
              </span>
            </a>
          ))}
        </div>
      )}

      {/* 기상 경보 */}
      {data.weather.alerts.length > 0 && (
        <div className="mt-4 space-y-2">
          <div className="text-xs font-medium text-slate-500 uppercase">{t('international.internationalWeather')}</div>
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
