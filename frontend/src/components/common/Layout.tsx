import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@/stores/authStore';

export default function Layout() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, user, logout } = useAuthStore();

  const navigation = [
    { name: t('nav.dashboard'), path: '/' },
    { name: t('nav.analytics'), path: '/analytics' },
  ];

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const toggleLang = () => {
    i18n.changeLanguage(i18n.language === 'ko' ? 'en' : 'ko');
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
                {t('app.title')}
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

            {/* 언어 토글 + 인증 상태 */}
            <div className="flex items-center gap-3">
              <button
                onClick={toggleLang}
                className="px-2 py-1 text-xs font-medium border border-slate-300 rounded hover:bg-slate-100 transition-colors text-slate-600"
              >
                {i18n.language === 'ko' ? 'EN' : 'KO'}
              </button>
              {isAuthenticated && user ? (
                <>
                  <span className="text-sm text-slate-600">{user.username}</span>
                  <button
                    onClick={handleLogout}
                    className="text-sm text-slate-500 hover:text-slate-700 transition-colors"
                  >
                    {t('nav.logout')}
                  </button>
                </>
              ) : (
                <Link
                  to="/login"
                  className="text-sm text-blue-600 hover:text-blue-800 transition-colors"
                >
                  {t('nav.login')}
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
            {t('app.footer')}
          </p>
        </div>
      </footer>
    </div>
  );
}
