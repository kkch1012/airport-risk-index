import type { Alert } from '@/types';

interface AlertListProps {
  alerts: Alert[];
}

const SEVERITY_CONFIG = {
  INFO: {
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    icon: 'ℹ️',
    text: 'text-blue-700',
  },
  WARNING: {
    bg: 'bg-yellow-50',
    border: 'border-yellow-200',
    icon: '⚠️',
    text: 'text-yellow-700',
  },
  CRITICAL: {
    bg: 'bg-red-50',
    border: 'border-red-200',
    icon: '🚨',
    text: 'text-red-700',
  },
};

const TYPE_LABELS: Record<string, string> = {
  WEATHER: '기상',
  SECURITY: '보안',
  HEALTH: '보건',
  OPERATIONAL: '운영',
  AVIATION: '항공',
};

export default function AlertList({ alerts }: AlertListProps) {
  if (alerts.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-slate-800 mb-4">실시간 알림</h3>
        <div className="text-center py-8 text-slate-500">
          <span className="text-3xl mb-2 block">✅</span>
          현재 발생한 알림이 없습니다.
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-slate-800">실시간 알림</h3>
        <span className="bg-red-100 text-red-700 text-xs font-medium px-2 py-1 rounded-full">
          {alerts.length}건
        </span>
      </div>

      <div className="space-y-3 max-h-80 overflow-y-auto">
        {alerts.map((alert, idx) => {
          const config = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.INFO;

          return (
            <div
              key={idx}
              className={`${config.bg} ${config.border} border rounded-lg p-3 flex items-start space-x-3`}
            >
              <span className="text-xl flex-shrink-0">{config.icon}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center space-x-2 mb-1">
                  <span className={`font-semibold ${config.text}`}>
                    {alert.airport}
                  </span>
                  <span className="text-xs bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded">
                    {TYPE_LABELS[alert.type] || alert.type}
                  </span>
                </div>
                <p className="text-sm text-slate-600 truncate">
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
