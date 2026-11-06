"""Out-of-band account notifications; never log addresses or reset tokens."""

from smtplib import SMTPException

from celery import shared_task

from .services import deliver_password_reset


@shared_task(
    ignore_result=True,
    autoretry_for=(OSError, SMTPException),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def send_password_reset(email: str) -> None:
    deliver_password_reset(email)
