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

export default function WeatherCard({ airportName, weather }: WeatherCardProps) {
  const precipIcon = PTY_ICONS[weather.precipitation_type_text || '없음'] || '☀️';

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
            <div className="text-xs text-slate-500">기온</div>
            <div className="font-semibold text-slate-800">
              {weather.temperature?.toFixed(1) ?? '-'}°C
            </div>
          </div>
        </div>

        {/* 풍속 */}
        <div className="flex items-center space-x-2">
          <span className="text-lg">💨</span>
          <div>
            <div className="text-xs text-slate-500">풍속</div>
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
            <div className="text-xs text-slate-500">습도</div>
            <div className="font-semibold text-slate-800">
              {weather.humidity?.toFixed(0) ?? '-'}%
            </div>
          </div>
        </div>

        {/* 강수 */}
        <div className="flex items-center space-x-2">
          <span className="text-lg">🌧️</span>
          <div>
            <div className="text-xs text-slate-500">강수</div>
            <div className="font-semibold text-slate-800">
              {weather.precipitation_type_text || '없음'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
