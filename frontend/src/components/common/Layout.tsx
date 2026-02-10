import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';

const navigation = [
  { name: '대시보드', path: '/' },
  { name: '분석', path: '/analytics' },
];

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, user, logout } = useAuthStore();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* 헤더 */}
      <header className="bg-white shadow-sm border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* 로고 */}
            <Link to="/" className="flex items-center space-x-2">
              <span className="text-2xl">✈️</span>
              <span className="text-xl font-bold text-slate-800">
                공항 위험지수
              </span>
            </Link>

            {/* 네비게이션 */}
            <nav className="flex space-x-4">
              {navigation.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    location.pathname === item.path
                      ? 'bg-blue-100 text-blue-700'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  {item.name}
                </Link>
              ))}
            </nav>

            {/* 인증 상태 */}
            <div className="flex items-center gap-3">
              {isAuthenticated && user ? (
                <>
                  <span className="text-sm text-slate-600">{user.username}</span>
                  <button
                    onClick={handleLogout}
                    className="text-sm text-slate-500 hover:text-slate-700 transition-colors"
                  >
                    로그아웃
                  </button>
                </>
              ) : (
                <Link
                  to="/login"
                  className="text-sm text-blue-600 hover:text-blue-800 transition-colors"
                >
                  로그인
                </Link>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* 메인 컨텐츠 */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>

      {/* 푸터 */}
      <footer className="bg-white border-t border-slate-200 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <p className="text-center text-sm text-slate-500">
            공항 위험지수 모니터링 시스템 v1.0.0
          </p>
        </div>
      </footer>
    </div>
  );
}
