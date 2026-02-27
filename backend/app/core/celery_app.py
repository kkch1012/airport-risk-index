"""
Celery 앱 인스턴스 및 Beat 스케줄 설정
"""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "airport_risk",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.collect_risks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=False,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=600,   # 10분 소프트 리밋
    task_time_limit=900,        # 15분 하드 킬
)

# Beat 스케줄 (주기적 태스크)
celery_app.conf.beat_schedule = {
    "collect-all-risks-every-30min": {
        "task": "app.tasks.collect_risks.collect_and_calculate_all_risks",
        "schedule": 30 * 60,  # 30분
        "options": {"expires": 25 * 60},  # 25분 내 미실행 시 폐기
    },
    "collect-weather-hourly": {
        "task": "app.tasks.collect_risks.collect_weather_data",
        "schedule": 60 * 60,  # 1시간
        "options": {"expires": 55 * 60},
    },
    "collect-advisory-every-6h": {
        "task": "app.tasks.collect_risks.collect_advisory_data",
        "schedule": 6 * 60 * 60,  # 6시간
        "options": {"expires": 5 * 60 * 60},
    },
    "send-daily-report-9am": {
        "task": "app.tasks.collect_risks.send_daily_report",
        "schedule": crontab(hour=9, minute=0),  # 매일 09:00
        "options": {"expires": 60 * 60},
    },
    "recalculate-weights-weekly": {
        "task": "app.tasks.collect_risks.recalculate_weights",
        "schedule": crontab(hour=3, minute=0, day_of_week=1),  # 매주 월요일 03:00
        "options": {"expires": 60 * 60},
    },
    "generate-forecasts-daily": {
        "task": "app.tasks.collect_risks.generate_daily_forecasts",
        "schedule": crontab(hour=4, minute=0),  # 매일 04:00
        "options": {"expires": 60 * 60},
    },
}
