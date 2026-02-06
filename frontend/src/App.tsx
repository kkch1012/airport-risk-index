import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/common/Layout';

// Code splitting: 페이지 단위 지연 로딩
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const AirportDetailPage = lazy(() => import('./pages/AirportDetailPage'));
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'));

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-3"></div>
        <div className="text-sm text-slate-400">로딩 중...</div>
      </div>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoader />}>
        <Routes>
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
