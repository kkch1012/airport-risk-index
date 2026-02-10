import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import { useTranslation } from 'react-i18next';
import type { RiskLevel } from '@/types';

interface RiskDistributionChartProps {
  data: { level: RiskLevel; count: number }[];
}

const COLORS: Record<RiskLevel, string> = {
  LOW: '#22c55e',
  MODERATE: '#eab308',
  HIGH: '#f97316',
  CRITICAL: '#ef4444',
};

export default function RiskDistributionChart({ data }: RiskDistributionChartProps) {
  const { t } = useTranslation();

  const chartData = data.map((item) => ({
    name: t(`riskLevel.${item.level}`),
    value: item.count,
    color: COLORS[item.level],
  }));

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-slate-800 mb-4">{t('distribution.title')}</h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={80}
              paddingAngle={5}
              dataKey="value"
              label={({ name, value }) => `${name}: ${value}`}
              labelLine={false}
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value: number) => [t('distribution.airportCount', { count: value }), '']}
            />
            <Legend
              verticalAlign="bottom"
              height={36}
              formatter={(value) => <span className="text-sm text-slate-600">{value}</span>}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
