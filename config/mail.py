from fastapi_mail import ConnectionConfig
import os

email_conf = ConnectionConfig(
    MAIL_USERNAME =os.getenv("EMAIL_USERNAME"),
    MAIL_PASSWORD = os.getenv("EMAIL_PASSWORD"),
    MAIL_FROM = os.getenv("EMAIL_ID_FROM"),
    MAIL_PORT = 465,
    MAIL_SERVER = "mail server",
    MAIL_STARTTLS = False,
    MAIL_SSL_TLS = True,
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)