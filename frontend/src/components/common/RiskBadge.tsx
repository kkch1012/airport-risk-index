import type { RiskLevel } from '@/types';

interface RiskBadgeProps {
  level: RiskLevel;
  size?: 'sm' | 'md' | 'lg';
}

const levelConfig: Record<RiskLevel, { label: string; bgColor: string; textColor: string }> = {
  LOW: { label: '정상', bgColor: 'bg-green-100', textColor: 'text-green-800' },
  MODERATE: { label: '주의', bgColor: 'bg-yellow-100', textColor: 'text-yellow-800' },
  HIGH: { label: '경계', bgColor: 'bg-orange-100', textColor: 'text-orange-800' },
  CRITICAL: { label: '심각', bgColor: 'bg-red-100', textColor: 'text-red-800' },
};

const sizeConfig = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-2.5 py-1 text-sm',
  lg: 'px-3 py-1.5 text-base',
};

export default function RiskBadge({ level, size = 'md' }: RiskBadgeProps) {
  const { label, bgColor, textColor } = levelConfig[level];

  return (
    <span
      className={`inline-flex items-center font-medium rounded-full ${bgColor} ${textColor} ${sizeConfig[size]}`}
    >
      {label}
    </span>
  );
}
