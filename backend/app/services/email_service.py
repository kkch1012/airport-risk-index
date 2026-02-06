"""
이메일 발송 서비스
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional

from app.config import settings
from app.services.risk_calculator import RiskResult

logger = logging.getLogger(__name__)


class EmailService:
    """SMTP 이메일 발송 서비스"""

    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.user = settings.SMTP_USER
        self.password = settings.SMTP_PASSWORD
        self.from_addr = settings.SMTP_FROM
        self.recipients = settings.ALERT_RECIPIENTS_LIST

    @property
    def is_configured(self) -> bool:
        """SMTP 설정이 완료되었는지 확인"""
        return bool(self.user and self.password)

    def send(self, subject: str, html_body: str, recipients: Optional[List[str]] = None) -> bool:
        """
        이메일 발송

        Args:
            subject: 이메일 제목
            html_body: HTML 본문
            recipients: 수신자 목록 (None이면 기본 수신자)

        Returns:
            발송 성공 여부
        """
        to_addrs = recipients or self.recipients
        if not to_addrs:
            logger.warning("이메일 수신자가 설정되지 않았습니다 (ALERT_RECIPIENTS)")
            return False

        if not self.is_configured:
            logger.info("[Email] SMTP 미설정 — 이메일 발송 건너뜀: %s", subject)
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(to_addrs)
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                server.starttls()
                server.login(self.user, self.password)
                server.sendmail(self.from_addr, to_addrs, msg.as_string())

            logger.info("[Email] 발송 성공: %s → %s", subject, to_addrs)
            return True
        except Exception:
            logger.exception("[Email] 발송 실패: %s", subject)
            return False

    def build_risk_alert_html(self, high_risk_results: List[RiskResult]) -> str:
        """HIGH/CRITICAL 위험 알림 HTML 생성"""
        rows = ""
        for r in sorted(high_risk_results, key=lambda x: x.total_score, reverse=True):
            level_color = "#dc2626" if r.risk_level == "CRITICAL" else "#f59e0b"
            level_bg = "#fef2f2" if r.risk_level == "CRITICAL" else "#fffbeb"

            # 카테고리별 점수
            cat_cells = ""
            for code in ["weather", "aviation", "security", "health", "operational", "external"]:
                cat = r.categories.get(code)
                score = cat.score if cat else 0
                cat_cells += f"<td style='padding:6px;text-align:center'>{score:.1f}</td>"

            rows += f"""
            <tr style='background:{level_bg}'>
                <td style='padding:8px;font-weight:bold'>{r.airport_name}<br>
                    <small style='color:#666'>{r.airport_code}</small></td>
                <td style='padding:8px;text-align:center;font-size:18px;font-weight:bold'>
                    {r.total_score:.1f}</td>
                <td style='padding:8px;text-align:center'>
                    <span style='background:{level_color};color:white;padding:3px 8px;
                        border-radius:4px;font-size:12px'>{r.risk_level}</span></td>
                {cat_cells}
            </tr>"""

        return f"""
        <div style='font-family:sans-serif;max-width:800px;margin:0 auto'>
            <div style='background:#dc2626;color:white;padding:16px;border-radius:8px 8px 0 0'>
                <h2 style='margin:0'>⚠ 공항 위험지수 알림</h2>
                <p style='margin:4px 0 0;opacity:0.9'>
                    {len(high_risk_results)}개 공항에서 HIGH/CRITICAL 위험 감지</p>
            </div>
            <table style='width:100%;border-collapse:collapse;border:1px solid #e5e7eb'>
                <thead>
                    <tr style='background:#f9fafb'>
                        <th style='padding:8px;text-align:left'>공항</th>
                        <th style='padding:8px'>총점</th>
                        <th style='padding:8px'>등급</th>
                        <th style='padding:6px;font-size:11px'>기상</th>
                        <th style='padding:6px;font-size:11px'>항공</th>
                        <th style='padding:6px;font-size:11px'>보안</th>
                        <th style='padding:6px;font-size:11px'>보건</th>
                        <th style='padding:6px;font-size:11px'>운영</th>
                        <th style='padding:6px;font-size:11px'>외부</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
            <p style='color:#666;font-size:12px;padding:12px'>
                본 알림은 공항 위험지수 모니터링 시스템에서 자동 발송되었습니다.</p>
        </div>"""

    def build_daily_report_html(self, risk_results: List[RiskResult]) -> str:
        """일일 리포트 HTML 생성"""
        sorted_results = sorted(risk_results, key=lambda x: x.total_score, reverse=True)

        high_count = sum(1 for r in sorted_results if r.risk_level in ("HIGH", "CRITICAL"))
        avg_score = sum(r.total_score for r in sorted_results) / len(sorted_results) if sorted_results else 0

        rows = ""
        for r in sorted_results:
            colors = {
                "LOW": ("#22c55e", "#f0fdf4"),
                "MODERATE": ("#eab308", "#fefce8"),
                "HIGH": ("#f59e0b", "#fffbeb"),
                "CRITICAL": ("#dc2626", "#fef2f2"),
            }
            level_color, bg = colors.get(r.risk_level, ("#666", "#fff"))

            rows += f"""
            <tr style='background:{bg}'>
                <td style='padding:6px 8px'>{r.airport_name}
                    <small style='color:#888'>({r.airport_code})</small></td>
                <td style='padding:6px;text-align:center;font-weight:bold'>{r.total_score:.1f}</td>
                <td style='padding:6px;text-align:center'>
                    <span style='background:{level_color};color:white;padding:2px 6px;
                        border-radius:3px;font-size:11px'>{r.risk_level}</span></td>
            </tr>"""

        summary_color = "#dc2626" if high_count > 0 else "#2563eb"

        return f"""
        <div style='font-family:sans-serif;max-width:600px;margin:0 auto'>
            <div style='background:#1e40af;color:white;padding:16px;border-radius:8px 8px 0 0'>
                <h2 style='margin:0'>📊 일일 공항 위험지수 리포트</h2>
                <p style='margin:4px 0 0;opacity:0.9'>{risk_results[0].date if risk_results else ""}</p>
            </div>
            <div style='padding:16px;background:#f8fafc;border:1px solid #e5e7eb'>
                <div style='display:flex;gap:16px;text-align:center'>
                    <div style='flex:1;padding:12px;background:white;border-radius:6px'>
                        <div style='font-size:24px;font-weight:bold'>{len(sorted_results)}</div>
                        <div style='color:#666;font-size:12px'>모니터링 공항</div>
                    </div>
                    <div style='flex:1;padding:12px;background:white;border-radius:6px'>
                        <div style='font-size:24px;font-weight:bold'>{avg_score:.1f}</div>
                        <div style='color:#666;font-size:12px'>평균 위험지수</div>
                    </div>
                    <div style='flex:1;padding:12px;background:white;border-radius:6px'>
                        <div style='font-size:24px;font-weight:bold;color:{summary_color}'>{high_count}</div>
                        <div style='color:#666;font-size:12px'>고위험 공항</div>
                    </div>
                </div>
            </div>
            <table style='width:100%;border-collapse:collapse;border:1px solid #e5e7eb'>
                <thead>
                    <tr style='background:#f9fafb'>
                        <th style='padding:8px;text-align:left'>공항</th>
                        <th style='padding:8px'>위험지수</th>
                        <th style='padding:8px'>등급</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
            <p style='color:#666;font-size:12px;padding:12px'>
                본 리포트는 공항 위험지수 모니터링 시스템에서 매일 자동 발송됩니다.</p>
        </div>"""
