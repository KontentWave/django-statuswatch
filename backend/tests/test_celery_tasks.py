"""Regression tests for Celery task registration."""

from __future__ import annotations

from app.celery import celery_app


def test_schedule_endpoint_checks_task_registered():
    """The monitoring scheduler task must stay registered with Celery."""

    task_name = "monitors.tasks.schedule_endpoint_checks"
    assert task_name in celery_app.tasks
    task = celery_app.tasks[task_name]
    assert task.name == task_name
