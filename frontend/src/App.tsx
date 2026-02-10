import { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Layout from './components/common/Layout';
import { useAuthStore } from './stores/authStore';

// Code splitting: 페이지 단위 지연 로딩
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const AirportDetailPage = lazy(() => import('./pages/AirportDetailPage'));
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));

function PageLoader() {
  const { t } = useTranslation();
  return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-3"></div>
        <div className="text-sm text-slate-400">{t('common.loadingShort')}</div>
      </div>
    </div>
  );
}

function App() {
  const checkAuth = useAuthStore((s) => s.checkAuth);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<Layout />}>
            <Route index element={<DashboardPage />} />
            <Route path="airport/:airportCode" element={<AirportDetailPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

export default App;
