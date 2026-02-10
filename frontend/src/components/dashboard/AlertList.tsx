import { useTranslation } from 'react-i18next';
import type { Alert } from '@/types';
import type { TFunction } from 'i18next';

interface AlertListProps {
  alerts: Alert[];
}

const SEVERITY_CONFIG = {
  INFO: {
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    icon: 'ℹ️',
    text: 'text-blue-700',
    pulse: false,
  },
  WARNING: {
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    icon: '⚠️',
    text: 'text-amber-700',
    pulse: false,
  },
  CRITICAL: {
    bg: 'bg-red-50',
    border: 'border-red-300',
    icon: '🚨',
    text: 'text-red-700',
    pulse: true,
  },
};

const TYPE_KEYS: Record<string, string> = {
  WEATHER: 'alert.typeWeather',
  SECURITY: 'alert.typeSecurity',
  HEALTH: 'alert.typeHealth',
  OPERATIONAL: 'alert.typeOperational',
  AVIATION: 'alert.typeAviation',
};

const TYPE_COLORS: Record<string, string> = {
  WEATHER: 'bg-indigo-100 text-indigo-700',
  SECURITY: 'bg-red-100 text-red-700',
  HEALTH: 'bg-emerald-100 text-emerald-700',
  OPERATIONAL: 'bg-amber-100 text-amber-700',
  AVIATION: 'bg-blue-100 text-blue-700',
};

function formatTimeAgo(isoStr: string | undefined, t: TFunction): string {
  if (!isoStr) return '';
  try {
    const date = new Date(isoStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);

    if (diffMin < 1) return t('timeAgo.justNow');
    if (diffMin < 60) return t('timeAgo.minutesAgo', { count: diffMin });

    const diffHour = Math.floor(diffMin / 60);
    if (diffHour < 24) return t('timeAgo.hoursAgo', { count: diffHour });

    return date.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

export default function AlertList({ alerts }: AlertListProps) {
  const { t } = useTranslation();

  if (alerts.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-slate-800 mb-4">{t('alert.title')}</h3>
        <div className="text-center py-8 text-slate-500">
          <span className="text-3xl mb-2 block">✅</span>
          {t('alert.noAlerts')}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <h3 className="text-lg font-semibold text-slate-800">{t('alert.title')}</h3>
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500"></span>
          </span>
        </div>
        <span className="bg-red-100 text-red-700 text-xs font-medium px-2.5 py-1 rounded-full">
          {t('common.countCase', { count: alerts.length })}
        </span>
      </div>

      <div className="space-y-3 max-h-80 overflow-y-auto">
        {alerts.map((alert, idx) => {
          const config = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.INFO;
          const typeKey = TYPE_KEYS[alert.type];
          const typeLabel = typeKey ? t(typeKey) : alert.type;
          const typeColor = TYPE_COLORS[alert.type] || 'bg-slate-100 text-slate-600';
          const timeAgo = formatTimeAgo(alert.created_at, t);

          return (
            <div
              key={`${alert.airport}-${alert.type}-${idx}`}
              className={`${config.bg} ${config.border} border rounded-lg p-3 flex items-start space-x-3 transition-all ${
                config.pulse ? 'animate-pulse-slow' : ''
              }`}
            >
              <span className="text-xl flex-shrink-0 mt-0.5">{config.icon}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center space-x-2 mb-1">
                  <span className={`font-semibold text-sm ${config.text}`}>
                    {alert.airport}
                  </span>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${typeColor}`}>
                    {typeLabel}
                  </span>
                  {timeAgo && (
                    <span className="text-xs text-slate-400 ml-auto flex-shrink-0">
                      {timeAgo}
                    </span>
                  )}
                </div>
                <p className="text-sm text-slate-700 leading-relaxed">
                  {alert.message}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
