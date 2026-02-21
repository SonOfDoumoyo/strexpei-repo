from fastapi_mail import FastMail, ConnectionConfig, MessageSchema, MessageType
from .config import Config
import ssl
import certifi
from pathlib import Path
from typing import List


BASE_DIR = Path(__file__).resolve().parent

mail_config = ConnectionConfig(
    MAIL_USERNAME = Config.MAIL_USERNAME,
    MAIL_PASSWORD = Config.MAIL_PASSWORD,
    MAIL_FROM = Config.MAIL_FROM,
    MAIL_PORT = 587,
    MAIL_SERVER = Config.MAIL_SERVER,
    MAIL_FROM_NAME =Config.MAIL_FROM_NAME,
    MAIL_STARTTLS = True,
    MAIL_SSL_TLS = False,
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True,
    TEMPLATE_FOLDER = Path(BASE_DIR , 'templates')
)

mail = FastMail(
    config=mail_config
)

#Force SSL context to use certifi
mail_config._ssl_context = ssl.create_default_context(cafile=certifi.where())


def create_message(recipients: List[str], subject: str, body: str):
    
    message = MessageSchema(
        recipients=recipients,
        subject=subject,
        body=body,
        subtype=MessageType.html
    )
    
    return message