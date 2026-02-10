import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import api from '@/services/api';

interface MatrixData {
  categories: string[];
  matrix: number[][];
}

function getColor(value: number): string {
  if (value >= 0.7) return 'bg-red-500 text-white';
  if (value >= 0.4) return 'bg-red-300 text-white';
  if (value >= 0.2) return 'bg-red-100 text-red-800';
  if (value >= -0.2) return 'bg-slate-50 text-slate-600';
  if (value >= -0.4) return 'bg-blue-100 text-blue-800';
  if (value >= -0.7) return 'bg-blue-300 text-white';
  return 'bg-blue-500 text-white';
}

export default function CorrelationHeatmap() {
  const { t } = useTranslation();

  const { data, isLoading } = useQuery<MatrixData>({
    queryKey: ['correlationMatrix'],
    queryFn: async () => {
      const { data } = await api.get('/analytics/correlation-matrix');
      return data;
    },
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-slate-800 mb-4">{t('correlation.title')}</h3>
        <div className="h-64 flex items-center justify-center text-slate-400">{t('common.loadingShort')}</div>
      </div>
    );
  }

  if (!data?.categories?.length) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-slate-800 mb-4">{t('correlation.title')}</h3>
        <div className="h-64 flex items-center justify-center text-slate-400">
          {t('correlation.noData')}
        </div>
      </div>
    );
  }

  const getCategoryLabel = (cat: string) => t(`category.${cat}Short` as const, { defaultValue: cat });

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-slate-800 mb-4">{t('correlation.title')}</h3>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>
              <th className="p-2 text-xs text-slate-500"></th>
              {data.categories.map((cat) => (
                <th key={cat} className="p-2 text-xs text-slate-500 text-center">
                  {getCategoryLabel(cat)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.categories.map((rowCat, i) => (
              <tr key={rowCat}>
                <td className="p-2 text-xs text-slate-500 font-medium">
                  {getCategoryLabel(rowCat)}
                </td>
                {data.matrix[i].map((value, j) => (
                  <td key={j} className="p-1">
                    <div
                      className={`w-full py-2 text-center text-xs rounded ${getColor(value)}`}
                      title={`${getCategoryLabel(data.categories[i])} vs ${getCategoryLabel(data.categories[j])}: ${value.toFixed(2)}`}
                    >
                      {value.toFixed(2)}
                    </div>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex justify-center mt-3 gap-2 text-xs text-slate-400">
        <span className="inline-block w-4 h-3 bg-blue-400 rounded"></span> {t('correlation.negative')}
        <span className="inline-block w-4 h-3 bg-slate-100 rounded border"></span> {t('correlation.none')}
        <span className="inline-block w-4 h-3 bg-red-400 rounded"></span> {t('correlation.positive')}
      </div>
    </div>
  );
}
