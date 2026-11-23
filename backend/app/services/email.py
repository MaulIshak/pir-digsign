import logging
import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage

from app.config import get_settings

logger = logging.getLogger("digsign.email")


class EmailProvider(ABC):
    @abstractmethod
    def send_email(self, to_email: str, subject: str, body_text: str) -> None:
        raise NotImplementedError


class ConsoleEmailProvider(EmailProvider):
    """Provider email development: mencetak isi & tautan email ke log server."""

    def send_email(self, to_email: str, subject: str, body_text: str) -> None:
        logger.info(
            "\n"
            "================ [DEV EMAIL CONSOLE] ================\n"
            "To     : %s\n"
            "Subject: %s\n"
            "-----------------------------------------------------\n"
            "%s\n"
            "=====================================================\n",
            to_email,
            subject,
            body_text,
        )


class SmtpEmailProvider(EmailProvider):
    def __init__(self, host: str, port: int, user: str, password: str, from_addr: str, use_tls: bool = True):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_addr = from_addr
        self.use_tls = use_tls

    def send_email(self, to_email: str, subject: str, body_text: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = to_email
        msg.set_content(body_text)

        with smtplib.SMTP(self.host, self.port, timeout=15) as server:
            if self.use_tls:
                server.starttls()
            if self.user and self.password:
                server.login(self.user, self.password)
            server.send_message(msg)


def get_email_provider() -> EmailProvider:
    settings = get_settings()
    if settings.EMAIL_PROVIDER.lower() == "smtp" and settings.SMTP_HOST:
        return SmtpEmailProvider(
            host=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            user=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            from_addr=settings.SMTP_FROM,
            use_tls=settings.SMTP_USE_TLS,
        )
    return ConsoleEmailProvider()
