"""
알림 판단 및 발송 서비스
"""

import logging
import threading
import time
from typing import Dict, List, Tuple

from app.services.email_service import EmailService
from app.services.risk_calculator import RiskResult

logger = logging.getLogger(__name__)

# 중복 알림 방지 캐시: {(airport_code, risk_level): timestamp}
_alert_cache: Dict[Tuple[str, str], float] = {}
_alert_cache_lock = threading.Lock()

# 중복 알림 방지 간격 (초)
ALERT_COOLDOWN = 3600  # 1시간


class AlertService:
    """위험 알림 판단 및 발송"""

    def __init__(self):
        self.email_service = EmailService()

    def check_and_notify(self, risk_results: List[RiskResult]) -> int:
        """
        HIGH/CRITICAL 감지 시 이메일 알림 발송

        Args:
            risk_results: 전체 공항 위험지수 결과

        Returns:
            발송된 알림 수
        """
        high_risk = [r for r in risk_results if r.risk_level in ("HIGH", "CRITICAL")]

        if not high_risk:
            return 0

        # 중복 필터링
        new_alerts = self._filter_duplicates(high_risk)

        if not new_alerts:
            logger.info(
                "[Alert] %d개 HIGH/CRITICAL 감지 — 모두 쿨다운 중 (발송 건너뜀)",
                len(high_risk),
            )
            return 0

        # 이메일 발송
        critical_count = sum(1 for r in new_alerts if r.risk_level == "CRITICAL")
        high_count = sum(1 for r in new_alerts if r.risk_level == "HIGH")

        if critical_count > 0:
            subject = f"[공항위험지수] CRITICAL {critical_count}건 + HIGH {high_count}건 감지"
        else:
            subject = f"[공항위험지수] HIGH {high_count}건 감지"

        html = self.email_service.build_risk_alert_html(new_alerts)
        sent = self.email_service.send(subject, html)

        if sent:
            # 캐시 갱신 (thread-safe)
            now = time.time()
            with _alert_cache_lock:
                for r in new_alerts:
                    _alert_cache[(r.airport_code, r.risk_level)] = now

            logger.info(
                "[Alert] 알림 발송 완료: CRITICAL=%d, HIGH=%d",
                critical_count,
                high_count,
            )
        else:
            logger.warning("[Alert] 알림 발송 실패 또는 SMTP 미설정")

        return len(new_alerts) if sent else 0

    def send_daily_report(self, risk_results: List[RiskResult]) -> bool:
        """
        일일 리포트 발송

        Args:
            risk_results: 전체 공항 위험지수 결과

        Returns:
            발송 성공 여부
        """
        if not risk_results:
            logger.warning("[Alert] 일일 리포트: 위험지수 데이터 없음")
            return False

        date_str = risk_results[0].date if risk_results else ""
        subject = f"[공항위험지수] 일일 리포트 ({date_str})"
        html = self.email_service.build_daily_report_html(risk_results)
        return self.email_service.send(subject, html)

    def _filter_duplicates(self, high_risk: List[RiskResult]) -> List[RiskResult]:
        """중복 알림 필터링 (쿨다운 내 동일 공항+등급 제외)"""
        now = time.time()
        new_alerts = []

        with _alert_cache_lock:
            # 만료된 캐시 정리
            expired = [k for k, t in _alert_cache.items() if now - t > ALERT_COOLDOWN]
            for k in expired:
                del _alert_cache[k]

            for r in high_risk:
                key = (r.airport_code, r.risk_level)
                last_sent = _alert_cache.get(key)

                if last_sent is None or (now - last_sent) > ALERT_COOLDOWN:
                    new_alerts.append(r)

        return new_alerts


def reset_alert_cache():
    """테스트용 캐시 초기화"""
    with _alert_cache_lock:
        _alert_cache.clear()
