"""
캐시 모듈 테스트
"""

import pytest
from unittest.mock import patch, MagicMock
from app.core.cache import _make_key, cache_result, invalidate_cache, invalidate_all


class TestMakeKey:
    """키 생성 테스트"""

    def test_same_inputs_same_key(self):
        k1 = _make_key("test", "a", "b")
        k2 = _make_key("test", "a", "b")
        assert k1 == k2

    def test_different_inputs_different_key(self):
        k1 = _make_key("test", "a")
        k2 = _make_key("test", "b")
        assert k1 != k2

    def test_prefix_in_key(self):
        key = _make_key("dashboard")
        assert "ari:cache:dashboard:" in key

    def test_kwargs_order_independent(self):
        k1 = _make_key("test", x=1, y=2)
        k2 = _make_key("test", y=2, x=1)
        assert k1 == k2


class TestCacheResult:
    """cache_result 데코레이터 테스트"""

    @pytest.mark.asyncio
    async def test_no_redis_executes_function(self):
        """Redis 없을 때 함수 직접 실행"""
        call_count = 0

        @cache_result("test", ttl_seconds=60)
        async def my_func():
            nonlocal call_count
            call_count += 1
            return {"data": "hello"}

        # Redis 없음 시뮬레이션
        with patch("app.core.cache._get_redis", return_value=None):
            result = await my_func()
            assert result == {"data": "hello"}
            assert call_count == 1

            # 두 번째 호출도 실행
            result2 = await my_func()
            assert result2 == {"data": "hello"}
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_with_redis_caches(self):
        """Redis 있을 때 캐싱"""
        call_count = 0

        @cache_result("test", ttl_seconds=60)
        async def my_func():
            nonlocal call_count
            call_count += 1
            return {"data": "hello"}

        mock_redis = MagicMock()
        mock_redis.get.return_value = None  # 첫 호출: 캐시 미스

        with patch("app.core.cache._get_redis", return_value=mock_redis):
            result = await my_func()
            assert result == {"data": "hello"}
            assert call_count == 1
            mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """캐시 히트 시 함수 미실행"""
        call_count = 0

        @cache_result("test", ttl_seconds=60)
        async def my_func():
            nonlocal call_count
            call_count += 1
            return {"data": "hello"}

        mock_redis = MagicMock()
        mock_redis.get.return_value = '{"data": "cached"}'

        with patch("app.core.cache._get_redis", return_value=mock_redis):
            result = await my_func()
            assert result == {"data": "cached"}
            assert call_count == 0  # 함수 실행되지 않음


class TestInvalidateCache:
    """캐시 무효화 테스트"""

    def test_no_redis_returns_zero(self):
        with patch("app.core.cache._get_redis", return_value=None):
            assert invalidate_cache("test") == 0

    def test_with_redis_deletes_keys(self):
        mock_redis = MagicMock()
        mock_redis.scan_iter.return_value = ["key1", "key2"]
        mock_redis.delete.return_value = 2

        with patch("app.core.cache._get_redis", return_value=mock_redis):
            count = invalidate_cache("test")
            assert count == 2

    def test_invalidate_all_no_redis(self):
        with patch("app.core.cache._get_redis", return_value=None):
            assert invalidate_all() == 0

    def test_invalidate_all_with_redis(self):
        mock_redis = MagicMock()
        mock_redis.scan_iter.return_value = ["k1", "k2", "k3"]
        mock_redis.delete.return_value = 3

        with patch("app.core.cache._get_redis", return_value=mock_redis):
            count = invalidate_all()
            assert count == 3
