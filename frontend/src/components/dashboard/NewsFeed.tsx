import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import api from '@/services/api';

interface NewsArticle {
  title: string;
  url: string;
  published_at: string;
  source: string;
  category: string;
  risk_score: number;
  keywords: string[];
  airport_code: string | null;
}

const categoryColors: Record<string, string> = {
  weather: 'bg-indigo-100 text-indigo-700',
  security: 'bg-red-100 text-red-700',
  operational: 'bg-amber-100 text-amber-700',
  health: 'bg-green-100 text-green-700',
  aviation: 'bg-blue-100 text-blue-700',
};

export default function NewsFeed() {
  const { t } = useTranslation();

  const { data, isLoading } = useQuery<{ articles: NewsArticle[]; total: number }>({
    queryKey: ['newsRecent'],
    queryFn: async () => {
      const { data } = await api.get('/news/recent?limit=10');
      return data;
    },
    refetchInterval: 300000,
  });

  if (isLoading || !data) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-slate-800 mb-4">{t('news.title')}</h3>
        <div className="text-sm text-slate-400">{t('common.loadingShort')}</div>
      </div>
    );
  }

  if (data.articles.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-slate-800 mb-4">{t('news.title')}</h3>
        <div className="text-sm text-slate-400">{t('news.noNews')}</div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-slate-800">{t('news.title')}</h3>
        <span className="text-xs text-slate-400">{t('common.countCase', { count: data.total })}</span>
      </div>

      <div className="space-y-3">
        {data.articles.slice(0, 5).map((article, idx) => (
          <div key={idx} className="border-b border-slate-100 pb-3 last:border-0 last:pb-0">
            <div className="flex items-start gap-2">
              <span className={`text-xs px-1.5 py-0.5 rounded whitespace-nowrap ${
                categoryColors[article.category] || 'bg-slate-100 text-slate-600'
              }`}>
                {t(`category.${article.category}Short` as const, { defaultValue: article.category })}
              </span>
              <a
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-slate-700 hover:text-blue-600 line-clamp-2"
              >
                {article.title}
              </a>
            </div>
            <div className="flex items-center justify-between mt-1 ml-0">
              <div className="text-xs text-slate-400">
                {article.source}
                {article.airport_code && (
                  <span className="ml-1 text-blue-500">{article.airport_code}</span>
                )}
              </div>
              <span className={`text-xs font-medium ${
                article.risk_score >= 60 ? 'text-red-500' :
                article.risk_score >= 40 ? 'text-orange-500' :
                'text-slate-500'
              }`}>
                {article.risk_score}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
