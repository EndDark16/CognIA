import os
import sys
import uuid

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from api.services import job_queue_service
from app.models import AppUser, db
from config.settings import TestingConfig


def _build_app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
    return app


def _teardown(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_job_queue_service_enqueue_claim_and_complete():
    app = _build_app()
    try:
        with app.app_context():
            user = AppUser(
                username=f"queue_{uuid.uuid4().hex[:8]}",
                email=f"queue_{uuid.uuid4().hex[:8]}@example.com",
                password="hashed",
                user_type="guardian",
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()

            created = job_queue_service.enqueue_job(
                job_type="report_generate",
                requested_by_user_id=user.id,
                payload={"months": 3},
            )
            assert created.status == "queued"

            claimed = job_queue_service.claim_next_job(worker_id="test-worker")
            assert claimed is not None
            assert claimed.id == created.id
            assert claimed.status == "running"

            finished = job_queue_service.mark_job_succeeded(
                job=claimed,
                result_meta={"report_type": "executive_monthly"},
            )
            assert finished.status == "completed"

            snapshot = job_queue_service.queue_snapshot()
            assert snapshot["counts"].get("completed", 0) >= 1
    finally:
        _teardown(app)


def test_job_queue_service_fail_and_retry_path():
    app = _build_app()
    try:
        with app.app_context():
            user = AppUser(
                username=f"queue_{uuid.uuid4().hex[:8]}",
                email=f"queue_{uuid.uuid4().hex[:8]}@example.com",
                password="hashed",
                user_type="guardian",
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()

            created = job_queue_service.enqueue_job(
                job_type="email_send",
                requested_by_user_id=user.id,
                payload={"to": "sample@example.com"},
            )
            claimed = job_queue_service.claim_next_job(worker_id="retry-worker")
            assert claimed is not None

            failed = job_queue_service.mark_job_failed(
                job=claimed,
                error_message="smtp_timeout",
                retryable=True,
            )
            assert failed.status == "queued"
            assert int((failed.params_json or {}).get("attempts") or 0) >= 1

            reclaimed = job_queue_service.claim_next_job(worker_id="retry-worker-2")
            assert reclaimed is not None
            assert reclaimed.id == created.id
    finally:
        _teardown(app)
