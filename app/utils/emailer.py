# SMTP functionality disabled (VPN use / no outbound mail). Intentionally no-op.
def send_email_smtp(
    host: str,
    port: int,
    username: str,
    password: str,
    use_tls: bool,
    sender: str,
    recipients,
    subject: str,
    body: str,
) -> None:
    return None
