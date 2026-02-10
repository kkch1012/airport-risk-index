import { useTranslation } from 'react-i18next';

interface RiskGaugeProps {
  score: number;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
}

function getColor(score: number): string {
  if (score < 25) return '#22c55e'; // green
  if (score < 50) return '#eab308'; // yellow
  if (score < 75) return '#f97316'; // orange
  return '#ef4444'; // red
}

const sizeConfig = {
  sm: { width: 60, height: 60, strokeWidth: 6, fontSize: 'text-sm' },
  md: { width: 100, height: 100, strokeWidth: 8, fontSize: 'text-xl' },
  lg: { width: 150, height: 150, strokeWidth: 10, fontSize: 'text-3xl' },
};

export default function RiskGauge({ score, size = 'md', showLabel = true }: RiskGaugeProps) {
  const { t } = useTranslation();
  const config = sizeConfig[size];
  const radius = (config.width - config.strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (score / 100) * circumference;
  const color = getColor(score);

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: config.width, height: config.height }}>
        <svg
          className="transform -rotate-90"
          width={config.width}
          height={config.height}
        >
          {/* 배경 원 */}
          <circle
            cx={config.width / 2}
            cy={config.height / 2}
            r={radius}
            stroke="#e2e8f0"
            strokeWidth={config.strokeWidth}
            fill="none"
          />
          {/* 진행 원 */}
          <circle
            cx={config.width / 2}
            cy={config.height / 2}
            r={radius}
            stroke={color}
            strokeWidth={config.strokeWidth}
            fill="none"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-all duration-500"
          />
        </svg>
        {/* 점수 텍스트 */}
        <div
          className={`absolute inset-0 flex items-center justify-center ${config.fontSize} font-bold`}
          style={{ color }}
        >
          {score.toFixed(1)}
        </div>
      </div>
      {showLabel && (
        <span className="mt-1 text-xs text-slate-500">{t('common.riskIndex')}</span>
      )}
    </div>
  );
}
