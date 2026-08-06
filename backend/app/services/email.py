import logging
import smtplib
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class BaseEmailAdapter(ABC):
    """Abstract base class for email sending adapters."""

    @abstractmethod
    def send_task_assignment_notification(
        self,
        recipient_email: str,
        task_title: str,
        task_status: str,
        task_link: str,
        assigner_name: str,
    ) -> bool:
        """Send task assignment notification email.

        Returns:
            bool: True if email was sent successfully or mocked, False if sending failed.
        """
        pass


class MockEmailAdapter(BaseEmailAdapter):
    """Mock email adapter for development and testing environments.

    Stores sent emails in an in-memory list without creating network connections.
    """

    def __init__(self) -> None:
        self.sent_emails: list[dict[str, Any]] = []

    def send_task_assignment_notification(
        self,
        recipient_email: str,
        task_title: str,
        task_status: str,
        task_link: str,
        assigner_name: str,
    ) -> bool:
        email_data = {
            "recipient_email": recipient_email,
            "task_title": task_title,
            "task_status": task_status,
            "task_link": task_link,
            "assigner_name": assigner_name,
        }
        self.sent_emails.append(email_data)
        logger.info(
            f"[EMAIL MOCK] To: {recipient_email} | Title: '{task_title}' | "
            f"Status: '{task_status}' | Link: '{task_link}' | By: {assigner_name}"
        )
        return True

    def clear(self) -> None:
        """Clear recorded in-memory emails."""
        self.sent_emails.clear()


class SmtpEmailAdapter(BaseEmailAdapter):
    """SMTP email adapter for production environment (e.g. Resend Cloud SMTP)."""

    def __init__(
        self,
        smtp_host: str = settings.SMTP_HOST,
        smtp_port: int = settings.SMTP_PORT,
        smtp_user: str = settings.SMTP_USER,
        smtp_password: str = settings.SMTP_PASSWORD,
        email_from: str = settings.EMAIL_FROM,
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.email_from = email_from

    def __repr__(self) -> str:
        return (
            f"<SmtpEmailAdapter host={self.smtp_host}:{self.smtp_port} "
            f"user={self.smtp_user} smtp_password='***'>"
        )

    def send_task_assignment_notification(
        self,
        recipient_email: str,
        task_title: str,
        task_status: str,
        task_link: str,
        assigner_name: str,
    ) -> bool:
        if not self.smtp_host or not recipient_email:
            logger.warning("SMTP host or recipient email missing. Email sending aborted.")
            return False

        subject = f"[TaskHub] Bạn được gán công việc mới: {task_title}"

        text_body = (
            f"Xin chào,\n\n"
            f"Bạn vừa được {assigner_name} gán phụ trách công việc trên TaskHub:\n\n"
            f"- Tiêu đề công việc: {task_title}\n"
            f"- Trạng thái: {task_status}\n"
            f"- Truy cập chi tiết tại: {task_link}\n\n"
            f"Trân trọng,\n"
            f"TaskHub Team"
        )

        html_body = (
            "<p>Xin chào,</p>"
            f"<p>Bạn vừa được <strong>{assigner_name}</strong> gán phụ trách công việc "
            "trên TaskHub:</p>"
            "<ul>"
            f"  <li><strong>Tiêu đề công việc:</strong> {task_title}</li>"
            f"  <li><strong>Trạng thái:</strong> {task_status}</li>"
            f'  <li><strong>Truy cập chi tiết tại:</strong> <a href="{task_link}">'
            f"{task_link}</a></li>"
            "</ul>"
            "<p>Trân trọng,<br>TaskHub Team</p>"
        )

        msg = MIMEMultipart("alternative")
        msg["From"] = self.email_from
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                if self.smtp_port == 587:
                    server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            logger.info(f"Email assignment notification sent successfully to {recipient_email}")
            return True
        except (smtplib.SMTPException, OSError) as exc:
            logger.warning(f"Failed to send email notification to {recipient_email}: {exc}")
            return False


class EmailService:
    """Facade / Resolver for email operations."""

    def __init__(self, adapter: BaseEmailAdapter | None = None) -> None:
        if adapter is not None:
            self.adapter = adapter
        elif (
            settings.ENVIRONMENT in ("development", "testing")
            or settings.TESTING
            or not settings.SMTP_PASSWORD
        ):
            self.adapter = MockEmailAdapter()
        else:
            self.adapter = SmtpEmailAdapter()

    def send_task_assignment_notification(
        self,
        recipient_email: str,
        task_title: str,
        task_status: str,
        task_link: str,
        assigner_name: str,
    ) -> bool:
        return self.adapter.send_task_assignment_notification(
            recipient_email=recipient_email,
            task_title=task_title,
            task_status=task_status,
            task_link=task_link,
            assigner_name=assigner_name,
        )
