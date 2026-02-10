import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { loginAPI, fetchMe } from '@/services/api';
import { useAuthStore } from '@/stores/authStore';

export default function LoginPage() {
  const navigate = useNavigate();
  const { setAuth, isAuthenticated } = useAuthStore();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // 이미 로그인 상태면 대시보드로
  if (isAuthenticated) {
    navigate('/', { replace: true });
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const { access_token } = await loginAPI({ username, password });
      // 토큰을 먼저 localStorage에 저장해야 fetchMe에서 인터셉터가 사용 가능
      localStorage.setItem('auth-storage', JSON.stringify({ token: access_token }));
      const user = await fetchMe();
      setAuth(access_token, user);
      navigate('/', { replace: true });
    } catch (err) {
      if (typeof err === 'object' && err !== null && 'response' in err) {
        const axiosErr = err as { response?: { status?: number } };
        if (axiosErr.response?.status === 401) {
          setError('아이디 또는 비밀번호가 올바르지 않습니다.');
        } else {
          setError('로그인 중 오류가 발생했습니다.');
        }
      } else {
        setError('서버에 연결할 수 없습니다.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <span className="text-4xl">✈️</span>
          <h1 className="mt-3 text-2xl font-bold text-slate-800">
            공항 위험지수
          </h1>
          <p className="mt-1 text-sm text-slate-500">관리자 로그인</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 space-y-4"
        >
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="username" className="block text-sm font-medium text-slate-700 mb-1">
              사용자명
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoComplete="username"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm
                         focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="username"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-1">
              비밀번호
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm
                         focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="password"
            />
          </div>

          <button
            type="submit"
            disabled={loading || !username || !password}
            className="w-full py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg
                       hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed
                       transition-colors"
          >
            {loading ? '로그인 중...' : '로그인'}
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-slate-400">
          계정이 없으면 관리자에게 문의하세요.
        </p>
      </div>
    </div>
  );
}
