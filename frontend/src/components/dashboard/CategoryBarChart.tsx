import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { useTranslation } from 'react-i18next';

interface CategoryData {
  code: string;
  name: string;
  score: number;
}

interface CategoryBarChartProps {
  data: CategoryData[];
  title?: string;
}

const CATEGORY_COLORS: Record<string, string> = {
  weather: '#6366f1',
  aviation: '#3b82f6',
  security: '#ef4444',
  health: '#22c55e',
  operational: '#f59e0b',
  external: '#8b5cf6',
};

export default function CategoryBarChart({ data, title }: CategoryBarChartProps) {
  const { t } = useTranslation();
  const chartTitle = title || t('detail.categoryChart');
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-slate-800 mb-4">{chartTitle}</h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 20, right: 20 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} />
            <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}`} />
            <YAxis
              type="category"
              dataKey="name"
              width={80}
              tick={{ fontSize: 12 }}
            />
            <Tooltip
              formatter={(value: number) => [`${value.toFixed(1)}`, t('common.riskIndex')]}
              labelFormatter={(label) => `${label}`}
            />
            <Bar dataKey="score" radius={[0, 4, 4, 0]}>
              {data.map((entry) => (
                <Cell
                  key={entry.code}
                  fill={CATEGORY_COLORS[entry.code] || '#94a3b8'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
