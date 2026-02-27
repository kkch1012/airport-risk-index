import { useTranslation } from 'react-i18next';
import type { RiskLevel } from '@/types';

interface RiskBadgeProps {
  level: RiskLevel;
  size?: 'sm' | 'md' | 'lg';
}

const styleConfig: Record<RiskLevel, { bgColor: string; textColor: string }> = {
  LOW: { bgColor: 'bg-green-100', textColor: 'text-green-800' },
  MODERATE: { bgColor: 'bg-yellow-100', textColor: 'text-yellow-800' },
  HIGH: { bgColor: 'bg-orange-100', textColor: 'text-orange-800' },
  CRITICAL: { bgColor: 'bg-red-100', textColor: 'text-red-800' },
};

const sizeConfig = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-2.5 py-1 text-sm',
  lg: 'px-3 py-1.5 text-base',
};

import { memo } from 'react';

const RiskBadge = memo(function RiskBadge({ level, size = 'md' }: RiskBadgeProps) {
  const { t } = useTranslation();
  const { bgColor, textColor } = styleConfig[level];

  return (
    <span
      className={`inline-flex items-center font-medium rounded-full ${bgColor} ${textColor} ${sizeConfig[size]}`}
    >
      {t(`riskLevel.${level}`)}
    </span>
  );
});

export default RiskBadge;
