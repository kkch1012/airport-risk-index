import { useState } from 'react';
import { Link } from 'react-router-dom';
import api from '@/services/api';
import { useAuthStore } from '@/stores/authStore';

interface ExportButtonsProps {
  airportCode?: string;
}

const FORMATS = [
  { key: 'csv', label: 'CSV', icon: '📊' },
  { key: 'excel', label: 'Excel', icon: '📗' },
  { key: 'pdf', label: 'PDF', icon: '📄' },
] as const;

export default function ExportButtons({ airportCode }: ExportButtonsProps) {
  const [loading, setLoading] = useState<string | null>(null);
  const { isAuthenticated } = useAuthStore();

  const handleDownload = async (format: string) => {
    if (!isAuthenticated) return;
    setLoading(format);
    try {
      const params = airportCode ? { airport_code: airportCode } : {};
      const response = await api.get(`/reports/${format}`, {
        params,
        responseType: 'blob',
      });

      const blob = new Blob([response.data]);
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;

      const contentDisposition = response.headers['content-disposition'];
      const filenameMatch = contentDisposition?.match(/filename="?([^"]+)"?/);
      a.download = filenameMatch?.[1] || `report.${format === 'excel' ? 'xlsx' : format}`;

      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(downloadUrl);
    } catch (err) {
      console.error('Download error:', err);
    } finally {
      setLoading(null);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs text-slate-400 mr-1">내보내기</span>
        <Link
          to="/login"
          className="text-xs text-blue-600 hover:text-blue-800 hover:underline"
        >
          로그인 후 이용 가능
        </Link>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-400 mr-1">내보내기</span>
      {FORMATS.map((fmt) => (
        <button
          key={fmt.key}
          onClick={() => handleDownload(fmt.key)}
          disabled={loading !== null}
          className={`inline-flex items-center gap-1 px-3 py-1.5 text-xs rounded border transition-colors ${
            loading === fmt.key
              ? 'bg-blue-50 border-blue-300 text-blue-600'
              : 'bg-white border-slate-300 text-slate-600 hover:bg-slate-50 hover:border-slate-400'
          }`}
        >
          <span>{fmt.icon}</span>
          <span>{loading === fmt.key ? '...' : fmt.label}</span>
        </button>
      ))}
    </div>
  );
}
