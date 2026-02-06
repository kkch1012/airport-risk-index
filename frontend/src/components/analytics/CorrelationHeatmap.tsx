import { useQuery } from '@tanstack/react-query';
import api from '@/services/api';

interface MatrixData {
  categories: string[];
  matrix: number[][];
}

const categoryLabels: Record<string, string> = {
  weather: '기상',
  aviation: '항공',
  security: '보안',
  health: '보건',
  operational: '운영',
  external: '외부',
};

function getColor(value: number): string {
  // -1 ~ 1 → blue ~ white ~ red
  if (value >= 0.7) return 'bg-red-500 text-white';
  if (value >= 0.4) return 'bg-red-300 text-white';
  if (value >= 0.2) return 'bg-red-100 text-red-800';
  if (value >= -0.2) return 'bg-slate-50 text-slate-600';
  if (value >= -0.4) return 'bg-blue-100 text-blue-800';
  if (value >= -0.7) return 'bg-blue-300 text-white';
  return 'bg-blue-500 text-white';
}

export default function CorrelationHeatmap() {
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
        <h3 className="text-lg font-semibold text-slate-800 mb-4">카테고리 상관관계</h3>
        <div className="h-64 flex items-center justify-center text-slate-400">로딩 중...</div>
      </div>
    );
  }

  if (!data?.categories?.length) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-slate-800 mb-4">카테고리 상관관계</h3>
        <div className="h-64 flex items-center justify-center text-slate-400">
          데이터가 부족합니다 (최소 30일 이력 필요)
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-slate-800 mb-4">카테고리 상관관계</h3>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>
              <th className="p-2 text-xs text-slate-500"></th>
              {data.categories.map((cat) => (
                <th key={cat} className="p-2 text-xs text-slate-500 text-center">
                  {categoryLabels[cat] || cat}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.categories.map((rowCat, i) => (
              <tr key={rowCat}>
                <td className="p-2 text-xs text-slate-500 font-medium">
                  {categoryLabels[rowCat] || rowCat}
                </td>
                {data.matrix[i].map((value, j) => (
                  <td key={j} className="p-1">
                    <div
                      className={`w-full py-2 text-center text-xs rounded ${getColor(value)}`}
                      title={`${categoryLabels[data.categories[i]] || data.categories[i]} vs ${categoryLabels[data.categories[j]] || data.categories[j]}: ${value.toFixed(2)}`}
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
        <span className="inline-block w-4 h-3 bg-blue-400 rounded"></span> 음의 상관
        <span className="inline-block w-4 h-3 bg-slate-100 rounded border"></span> 없음
        <span className="inline-block w-4 h-3 bg-red-400 rounded"></span> 양의 상관
      </div>
    </div>
  );
}
