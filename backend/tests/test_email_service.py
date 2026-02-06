"""
이메일 알림 서비스 테스트
"""

import pytest
from unittest.mock import patch, MagicMock

from app.services.risk_calculator import RiskResult, CategoryScore
from app.services.email_service import EmailService
from app.services.alert_service import AlertService, reset_alert_cache, _alert_cache
from app.core.constants import AIRPORT_NAMES


def _make_risk_result(
    airport_code="ICN",
    total_score=42.5,
    risk_level="MODERATE",
) -> RiskResult:
    """테스트용 RiskResult"""
    categories = {
        "weather": CategoryScore(code="weather", name="기상", score=35.0, level="MODERATE", factors={"wind": 10.0}),
        "aviation": CategoryScore(code="aviation", name="항공안전", score=20.0, level="LOW", factors={}),
        "security": CategoryScore(code="security", name="보안", score=30.0, level="MODERATE", factors={}),
        "health": CategoryScore(code="health", name="보건", score=15.0, level="LOW", factors={}),
        "operational": CategoryScore(code="operational", name="운영", score=50.0, level="MODERATE", factors={}),
        "external": CategoryScore(code="external", name="외부", score=25.0, level="LOW", factors={}),
    }
    return RiskResult(
        airport_code=airport_code,
        airport_name=AIRPORT_NAMES.get(airport_code, airport_code),
        date="2025-01-15",
        total_score=total_score,
        risk_level=risk_level,
        categories=categories,
        updated_at="2025-01-15T12:00:00",
    )


# ─── EmailService 테스트 ────────────────────────────


class TestEmailService:
    """이메일 발송 서비스 테스트"""

    def test_is_configured_false_when_no_credentials(self):
        """SMTP 미설정 시 is_configured == False"""
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SMTP_USER = ""
            mock_settings.SMTP_PASSWORD = ""
            mock_settings.SMTP_HOST = "smtp.gmail.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_FROM = "test@example.com"
            mock_settings.ALERT_RECIPIENTS_LIST = ["admin@example.com"]

            service = EmailService()
            assert service.is_configured is False

    def test_is_configured_true_with_credentials(self):
        """SMTP 설정 완료 시 is_configured == True"""
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SMTP_USER = "user@gmail.com"
            mock_settings.SMTP_PASSWORD = "password123"
            mock_settings.SMTP_HOST = "smtp.gmail.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_FROM = "test@example.com"
            mock_settings.ALERT_RECIPIENTS_LIST = ["admin@example.com"]

            service = EmailService()
            assert service.is_configured is True

    def test_send_skips_when_not_configured(self):
        """SMTP 미설정 시 발송 건너뜀"""
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SMTP_USER = ""
            mock_settings.SMTP_PASSWORD = ""
            mock_settings.SMTP_HOST = "smtp.gmail.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_FROM = "test@example.com"
            mock_settings.ALERT_RECIPIENTS_LIST = ["admin@example.com"]

            service = EmailService()
            result = service.send("Test Subject", "<p>Test</p>")
            assert result is False

    def test_send_skips_when_no_recipients(self):
        """수신자 미설정 시 발송 건너뜀"""
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SMTP_USER = "user@gmail.com"
            mock_settings.SMTP_PASSWORD = "password123"
            mock_settings.SMTP_HOST = "smtp.gmail.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_FROM = "test@example.com"
            mock_settings.ALERT_RECIPIENTS_LIST = []

            service = EmailService()
            result = service.send("Test Subject", "<p>Test</p>")
            assert result is False

    @patch("app.services.email_service.smtplib.SMTP")
    def test_send_success(self, mock_smtp_class):
        """SMTP 발송 성공"""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SMTP_USER = "user@gmail.com"
            mock_settings.SMTP_PASSWORD = "password123"
            mock_settings.SMTP_HOST = "smtp.gmail.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_FROM = "Airport Risk <noreply@example.com>"
            mock_settings.ALERT_RECIPIENTS_LIST = ["admin@example.com"]

            service = EmailService()
            result = service.send("Test", "<p>Body</p>")

        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@gmail.com", "password123")
        mock_server.sendmail.assert_called_once()

    def test_build_risk_alert_html(self):
        """위험 알림 HTML 생성"""
        service = EmailService()
        high_risk = [
            _make_risk_result("ICN", 78.5, "CRITICAL"),
            _make_risk_result("CJU", 55.0, "HIGH"),
        ]
        html = service.build_risk_alert_html(high_risk)

        assert "인천국제공항" in html
        assert "제주국제공항" in html
        assert "CRITICAL" in html
        assert "HIGH" in html
        assert "78.5" in html

    def test_build_daily_report_html(self):
        """일일 리포트 HTML 생성"""
        service = EmailService()
        results = [
            _make_risk_result("ICN", 42.5, "MODERATE"),
            _make_risk_result("GMP", 30.0, "MODERATE"),
            _make_risk_result("CJU", 55.0, "HIGH"),
        ]
        html = service.build_daily_report_html(results)

        assert "일일" in html
        assert "인천국제공항" in html
        assert "김포국제공항" in html
        assert "제주국제공항" in html


# ─── AlertService 테스트 ────────────────────────────


class TestAlertService:
    """알림 판단 서비스 테스트"""

    def setup_method(self):
        """각 테스트 전 캐시 초기화"""
        reset_alert_cache()

    def test_no_notification_when_no_high_risk(self):
        """HIGH/CRITICAL 없으면 알림 안 보냄"""
        results = [
            _make_risk_result("ICN", 30.0, "MODERATE"),
            _make_risk_result("GMP", 20.0, "LOW"),
        ]

        with patch.object(EmailService, "send", return_value=True) as mock_send:
            service = AlertService()
            notified = service.check_and_notify(results)

        assert notified == 0
        mock_send.assert_not_called()

    def test_notification_sent_for_high_risk(self):
        """HIGH 공항 감지 시 알림 발송"""
        results = [
            _make_risk_result("ICN", 60.0, "HIGH"),
            _make_risk_result("GMP", 20.0, "LOW"),
        ]

        with patch.object(EmailService, "send", return_value=True):
            service = AlertService()
            notified = service.check_and_notify(results)

        assert notified == 1

    def test_notification_sent_for_critical(self):
        """CRITICAL 공항 감지 시 알림 발송"""
        results = [
            _make_risk_result("ICN", 80.0, "CRITICAL"),
            _make_risk_result("CJU", 65.0, "HIGH"),
        ]

        with patch.object(EmailService, "send", return_value=True):
            service = AlertService()
            notified = service.check_and_notify(results)

        assert notified == 2

    def test_duplicate_prevention(self):
        """중복 알림 방지 — 같은 공항+등급 1시간 내 재발송 안 함"""
        results = [
            _make_risk_result("ICN", 60.0, "HIGH"),
        ]

        with patch.object(EmailService, "send", return_value=True):
            service = AlertService()
            first = service.check_and_notify(results)
            second = service.check_and_notify(results)

        assert first == 1
        assert second == 0  # 중복 방지

    def test_different_level_sends_again(self):
        """같은 공항이라도 등급이 바뀌면 재발송"""
        with patch.object(EmailService, "send", return_value=True):
            service = AlertService()

            results_high = [_make_risk_result("ICN", 60.0, "HIGH")]
            first = service.check_and_notify(results_high)

            results_critical = [_make_risk_result("ICN", 80.0, "CRITICAL")]
            second = service.check_and_notify(results_critical)

        assert first == 1
        assert second == 1  # 등급 변경 → 재발송

    def test_send_failure_returns_zero(self):
        """이메일 발송 실패 시 0 반환"""
        results = [_make_risk_result("ICN", 60.0, "HIGH")]

        with patch.object(EmailService, "send", return_value=False):
            service = AlertService()
            notified = service.check_and_notify(results)

        assert notified == 0

    def test_send_daily_report(self):
        """일일 리포트 발송"""
        results = [
            _make_risk_result("ICN", 42.5, "MODERATE"),
            _make_risk_result("GMP", 30.0, "MODERATE"),
        ]

        with patch.object(EmailService, "send", return_value=True) as mock_send:
            service = AlertService()
            sent = service.send_daily_report(results)

        assert sent is True
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert "일일 리포트" in call_args[0][0]  # subject

    def test_send_daily_report_empty_results(self):
        """빈 결과로 일일 리포트 시도"""
        with patch.object(EmailService, "send") as mock_send:
            service = AlertService()
            sent = service.send_daily_report([])

        assert sent is False
        mock_send.assert_not_called()


# ─── 캐시 테스트 ────────────────────────────────────


class TestAlertCache:
    """알림 캐시 테스트"""

    def setup_method(self):
        reset_alert_cache()

    def test_reset_cache(self):
        """캐시 초기화"""
        _alert_cache[("ICN", "HIGH")] = 100.0
        assert len(_alert_cache) == 1

        reset_alert_cache()
        assert len(_alert_cache) == 0

    def test_expired_cache_cleaned(self):
        """만료된 캐시 자동 정리"""
        import time

        # 과거 시간으로 캐시 설정 (2시간 전)
        _alert_cache[("ICN", "HIGH")] = time.time() - 7200

        results = [_make_risk_result("ICN", 60.0, "HIGH")]

        with patch.object(EmailService, "send", return_value=True):
            service = AlertService()
            notified = service.check_and_notify(results)

        assert notified == 1  # 만료되어 재발송
