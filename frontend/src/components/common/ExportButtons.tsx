import { useState } from 'react';
import api from '@/services/api';

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

  const handleDownload = async (format: string) => {
    setLoading(format);
    try {
      const params = airportCode ? `?airport_code=${airportCode}` : '';
      const url = `${api.defaults.baseURL}/reports/${format}${params}`;

      const response = await fetch(url);
      if (!response.ok) throw new Error('Download failed');

      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;

      const contentDisposition = response.headers.get('Content-Disposition');
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
