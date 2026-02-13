"""
커스텀 Prometheus 메트릭 정의

모든 애플리케이션 메트릭을 한 곳에 모아 관리.
prometheus_client 미설치 시 graceful skip.
"""

from typing import Optional

# 메트릭 객체 (prometheus_client 미설치 시 None)
risk_score_current: Optional[object] = None
risk_calculation_duration: Optional[object] = None
collector_runs_total: Optional[object] = None
collector_duration: Optional[object] = None
celery_tasks_total: Optional[object] = None
celery_task_duration: Optional[object] = None
alerts_sent_total: Optional[object] = None

try:
    from prometheus_client import Counter, Gauge, Histogram

    risk_score_current = Gauge(
        "risk_score_current",
        "Current risk score per airport",
        labelnames=["airport_code"],
    )

    risk_calculation_duration = Histogram(
        "risk_calculation_duration_seconds",
        "Time spent calculating risk scores",
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    )

    collector_runs_total = Counter(
        "collector_runs_total",
        "Total collector executions",
        labelnames=["collector", "status"],
    )

    collector_duration = Histogram(
        "collector_duration_seconds",
        "Time spent in each data collector",
        labelnames=["collector"],
        buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
    )

    celery_tasks_total = Counter(
        "celery_tasks_total",
        "Total Celery task executions",
        labelnames=["task_name", "status"],
    )

    celery_task_duration = Histogram(
        "celery_task_duration_seconds",
        "Celery task execution duration",
        labelnames=["task_name"],
        buckets=(0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
    )

    alerts_sent_total = Counter(
        "alerts_sent_total",
        "Total alerts sent",
        labelnames=["severity"],
    )

except ImportError:
    pass
