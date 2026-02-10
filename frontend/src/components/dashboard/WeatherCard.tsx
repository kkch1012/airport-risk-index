import { useTranslation } from 'react-i18next';

interface WeatherData {
  temperature?: number;
  wind_speed?: number;
  humidity?: number;
  precipitation_1h?: number;
  precipitation_type?: number;
  precipitation_type_text?: string;
  is_strong_wind?: boolean;
}

interface WeatherCardProps {
  airportName: string;
  weather: WeatherData;
}

const PTY_ICONS: Record<string, string> = {
  '없음': '☀️',
  '비': '🌧️',
  '비/눈': '🌨️',
  '눈': '❄️',
  '소나기': '🌦️',
  '빗방울': '💧',
  '빗방울눈날림': '🌨️',
  '눈날림': '🌬️',
};

// API에서 오는 한국어 PTY 값 → 번역 키 매핑
const PTY_KEYS: Record<string, string> = {
  '없음': 'weather.ptyNone',
  '비': 'weather.ptyRain',
  '비/눈': 'weather.ptyRainSnow',
  '눈': 'weather.ptySnow',
  '소나기': 'weather.ptyShower',
  '빗방울': 'weather.ptyDrizzle',
  '빗방울눈날림': 'weather.ptyDrizzleSnow',
  '눈날림': 'weather.ptySnowDrift',
};

export default function WeatherCard({ airportName, weather }: WeatherCardProps) {
  const { t } = useTranslation();
  const ptyText = weather.precipitation_type_text || '없음';
  const precipIcon = PTY_ICONS[ptyText] || '☀️';
  const ptyKey = PTY_KEYS[ptyText];
  const ptyLabel = ptyKey ? t(ptyKey) : ptyText;

  return (
    <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg p-4 border border-blue-100">
      <div className="flex items-center justify-between mb-3">
        <h4 className="font-medium text-slate-700">{airportName}</h4>
        <span className="text-2xl">{precipIcon}</span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {/* 기온 */}
        <div className="flex items-center space-x-2">
          <span className="text-lg">🌡️</span>
          <div>
            <div className="text-xs text-slate-500">{t('weather.temperature')}</div>
            <div className="font-semibold text-slate-800">
              {weather.temperature?.toFixed(1) ?? '-'}°C
            </div>
          </div>
        </div>

        {/* 풍속 */}
        <div className="flex items-center space-x-2">
          <span className="text-lg">💨</span>
          <div>
            <div className="text-xs text-slate-500">{t('weather.windSpeed')}</div>
            <div className={`font-semibold ${weather.is_strong_wind ? 'text-orange-600' : 'text-slate-800'}`}>
              {weather.wind_speed?.toFixed(1) ?? '-'} m/s
              {weather.is_strong_wind && <span className="text-xs ml-1">⚠️</span>}
            </div>
          </div>
        </div>

        {/* 습도 */}
        <div className="flex items-center space-x-2">
          <span className="text-lg">💧</span>
          <div>
            <div className="text-xs text-slate-500">{t('weather.humidity')}</div>
            <div className="font-semibold text-slate-800">
              {weather.humidity?.toFixed(0) ?? '-'}%
            </div>
          </div>
        </div>

        {/* 강수 */}
        <div className="flex items-center space-x-2">
          <span className="text-lg">🌧️</span>
          <div>
            <div className="text-xs text-slate-500">{t('weather.precipitation')}</div>
            <div className="font-semibold text-slate-800">
              {ptyLabel}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
