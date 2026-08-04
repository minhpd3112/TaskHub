import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending email notifications asynchronously via SMTP."""

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

    def send_task_assignment_notification(
        self,
        assignee_email: str,
        task_title: str,
        assigner_name: str,
    ) -> None:
        """Send email notification when a user is assigned to a task.

        Safe execution: handles SMTP errors gracefully without throwing exceptions.
        """
        if not self.smtp_host or not assignee_email:
            logger.info(
                f"[EMAIL MOCK] Notification to {assignee_email}: "
                f"Task '{task_title}' assigned by {assigner_name}"
            )
            return

        subject = f"[TaskHub] Bạn được gán công việc mới: {task_title}"
        body = (
            f"Xin chào,\n\n"
            f"Bạn vừa được {assigner_name} gán phụ trách công việc '{task_title}' trên TaskHub.\n\n"
            f"Vui lòng truy cập hệ thống để biết thêm chi tiết.\n\n"
            f"Trân trọng,\n"
            f"TaskHub Team"
        )

        msg = MIMEMultipart()
        msg["From"] = self.email_from
        msg["To"] = assignee_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                if self.smtp_port == 587:
                    server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            logger.info(f"Email assignment notification sent successfully to {assignee_email}")
        except Exception as exc:
            logger.warning(f"Failed to send email notification to {assignee_email}: {exc}")
