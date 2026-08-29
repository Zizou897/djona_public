import logging
import socket
import after_response
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

@after_response.enable
def send_customize_email(subject: str, receivers: list, template: str, context: dict) -> bool:
    try:
        html_message = render_to_string(template, context)
        send_mail(subject, '', settings.EMAIL_HOST_USER, receivers, html_message=html_message)
        return True
    except Exception as e:
        logger.error(f"Email error: {e}")
        return False

def get_ip() -> str:
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return '127.0.0.1'
