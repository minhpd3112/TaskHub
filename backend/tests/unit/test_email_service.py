import logging
import smtplib
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.email import (
    BaseEmailAdapter,
    EmailService,
    MockEmailAdapter,
    SmtpEmailAdapter,
)


def test_mock_email_adapter_success() -> None:
    """Test MockEmailAdapter records emails in-memory without network operations."""
    adapter = MockEmailAdapter()
    assert len(adapter.sent_emails) == 0

    result = adapter.send_task_assignment_notification(
        recipient_email="dev@example.com",
        task_title="Build Auth System",
        task_status="TODO",
        task_link="http://localhost:3000/tasks/123",
        assigner_name="Alice Owner",
    )

    assert result is True
    assert len(adapter.sent_emails) == 1
    email = adapter.sent_emails[0]
    assert email["recipient_email"] == "dev@example.com"
    assert email["task_title"] == "Build Auth System"
    assert email["task_status"] == "TODO"
    assert email["task_link"] == "http://localhost:3000/tasks/123"
    assert email["assigner_name"] == "Alice Owner"

    adapter.clear()
    assert len(adapter.sent_emails) == 0


def test_smtp_email_adapter_repr_security() -> None:
    """Test SmtpEmailAdapter __repr__ masks password/API key."""
    adapter = SmtpEmailAdapter(
        smtp_host="smtp.resend.com",
        smtp_port=587,
        smtp_user="resend",
        smtp_password="re_secret_123456789",
        email_from="onboarding@resend.dev",
    )
    repr_str = repr(adapter)
    assert "re_secret_123456789" not in repr_str
    assert "smtp_password='***'" in repr_str


def test_smtp_email_adapter_missing_host_or_recipient() -> None:
    """Test SmtpEmailAdapter returns False when host or recipient email is missing."""
    adapter = SmtpEmailAdapter(smtp_host="", smtp_port=587)
    assert (
        adapter.send_task_assignment_notification(
            recipient_email="user@example.com",
            task_title="Test Task",
            task_status="TODO",
            task_link="http://localhost:3000/tasks/1",
            assigner_name="Bob",
        )
        is False
    )

    adapter2 = SmtpEmailAdapter(smtp_host="smtp.resend.com", smtp_port=587)
    assert (
        adapter2.send_task_assignment_notification(
            recipient_email="",
            task_title="Test Task",
            task_status="TODO",
            task_link="http://localhost:3000/tasks/1",
            assigner_name="Bob",
        )
        is False
    )


@patch("smtplib.SMTP")
def test_smtp_email_adapter_send_success(mock_smtp_class: MagicMock) -> None:
    """Test SmtpEmailAdapter sends email via SMTP with STARTTLS and auth credentials."""
    mock_server = MagicMock()
    mock_smtp_class.return_value.__enter__.return_value = mock_server

    adapter = SmtpEmailAdapter(
        smtp_host="smtp.resend.com",
        smtp_port=587,
        smtp_user="resend",
        smtp_password="re_123456789_secret",
        email_from="onboarding@resend.dev",
    )

    result = adapter.send_task_assignment_notification(
        recipient_email="user@example.com",
        task_title="Implement Resend SMTP",
        task_status="IN_PROGRESS",
        task_link="http://localhost:3000/tasks/abc-123",
        assigner_name="Charlie Editor",
    )

    assert result is True
    mock_smtp_class.assert_called_once_with("smtp.resend.com", 587, timeout=10)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("resend", "re_123456789_secret")
    mock_server.send_message.assert_called_once()

    # Inspect message content
    sent_msg = mock_server.send_message.call_args[0][0]
    assert sent_msg["To"] == "user@example.com"
    assert sent_msg["From"] == "onboarding@resend.dev"
    assert "Implement Resend SMTP" in sent_msg["Subject"]

    payload = sent_msg.get_payload()
    text_content = payload[0].get_payload(decode=True).decode("utf-8")
    assert "Implement Resend SMTP" in text_content
    assert "IN_PROGRESS" in text_content
    assert "http://localhost:3000/tasks/abc-123" in text_content
    assert "Charlie Editor" in text_content


@pytest.mark.parametrize(
    "exception_to_raise",
    [
        smtplib.SMTPAuthenticationError(535, "Authentication failed"),
        TimeoutError("Connection timed out"),
        OSError("Network unreachable"),
    ],
)
@patch("smtplib.SMTP")
def test_smtp_email_adapter_fail_safe(
    mock_smtp_class: MagicMock,
    exception_to_raise: Exception,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test SmtpEmailAdapter Fail-Safe pattern on SMTP errors."""
    mock_smtp_class.side_effect = exception_to_raise

    adapter = SmtpEmailAdapter(
        smtp_host="smtp.resend.com",
        smtp_port=587,
        smtp_user="resend",
        smtp_password="re_secret_password_never_log",
        email_from="onboarding@resend.dev",
    )

    with caplog.at_level(logging.WARNING):
        result = adapter.send_task_assignment_notification(
            recipient_email="fail@example.com",
            task_title="Failed Task",
            task_status="TODO",
            task_link="http://localhost:3000/tasks/fail",
            assigner_name="Dave",
        )

    assert result is False
    # Ensure secret is not in logs
    assert "re_secret_password_never_log" not in caplog.text
    assert "Failed to send email notification to fail@example.com" in caplog.text


def test_email_service_resolver_mock_mode() -> None:
    """Test EmailService resolves to MockEmailAdapter in dev/test/missing password modes."""
    dev_settings = Settings(
        ENVIRONMENT="development",
        SMTP_PASSWORD="re_123",
        DATABASE_URL="postgresql+asyncpg://u:p@h:5432/d",
        REDIS_URL="redis://localhost",
        JWT_SECRET_KEY="secret",
    )
    with patch("app.services.email.settings", dev_settings):
        service = EmailService()
        assert isinstance(service.adapter, MockEmailAdapter)

    test_settings = Settings(
        ENVIRONMENT="testing",
        SMTP_PASSWORD="re_123",
        DATABASE_URL="postgresql+asyncpg://u:p@h:5432/d",
        REDIS_URL="redis://localhost",
        JWT_SECRET_KEY="secret",
    )
    with patch("app.services.email.settings", test_settings):
        service = EmailService()
        assert isinstance(service.adapter, MockEmailAdapter)

    prod_testing_settings = Settings(
        ENVIRONMENT="production",
        TESTING=True,
        SMTP_PASSWORD="re_123",
        DATABASE_URL="postgresql+asyncpg://u:p@h:5432/d",
        REDIS_URL="redis://localhost",
        JWT_SECRET_KEY="secret",
    )
    with patch("app.services.email.settings", prod_testing_settings):
        service = EmailService()
        assert isinstance(service.adapter, MockEmailAdapter)

    no_pass_settings = Settings(
        ENVIRONMENT="production",
        SMTP_PASSWORD="",
        DATABASE_URL="postgresql+asyncpg://u:p@h:5432/d",
        REDIS_URL="redis://localhost",
        JWT_SECRET_KEY="secret",
    )
    with patch("app.services.email.settings", no_pass_settings):
        service = EmailService()
        assert isinstance(service.adapter, MockEmailAdapter)


def test_email_service_resolver_production_mode() -> None:
    """Test EmailService resolves to SmtpEmailAdapter in production mode with password set."""
    prod_settings = Settings(
        ENVIRONMENT="production",
        SMTP_PASSWORD="re_123456",
        DATABASE_URL="postgresql+asyncpg://u:p@h:5432/d",
        REDIS_URL="redis://localhost",
        JWT_SECRET_KEY="secret",
    )
    with patch("app.services.email.settings", prod_settings):
        service = EmailService()
        assert isinstance(service.adapter, SmtpEmailAdapter)


def test_email_service_custom_adapter_injection() -> None:
    """Test EmailService uses custom injected adapter."""
    mock_custom = MagicMock(spec=BaseEmailAdapter)
    mock_custom.send_task_assignment_notification.return_value = True

    service = EmailService(adapter=mock_custom)
    assert service.adapter == mock_custom

    res = service.send_task_assignment_notification(
        recipient_email="user@test.com",
        task_title="Custom Task",
        task_status="DONE",
        task_link="http://localhost:3000/tasks/custom",
        assigner_name="Admin",
    )
    assert res is True
    mock_custom.send_task_assignment_notification.assert_called_once_with(
        recipient_email="user@test.com",
        task_title="Custom Task",
        task_status="DONE",
        task_link="http://localhost:3000/tasks/custom",
        assigner_name="Admin",
    )
