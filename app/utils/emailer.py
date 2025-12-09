import smtplib
import ssl
from email.message import EmailMessage
from typing import Iterable, List


def send_email_smtp(
    host: str,
    port: int,
    username: str,
    password: str,
    use_tls: bool,
    sender: str,
    recipients: Iterable[str],
    subject: str,
    body: str,
) -> None:
    """
    Send a plain-text email via SMTP.
    """
    to_list: List[str] = list(recipients)
    if not to_list:
        raise ValueError("No recipients provided")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(to_list)
    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=30) as server:
        if use_tls:
            server.starttls(context=context)
        if username and password:
            server.login(username, password)
        server.send_message(msg)
