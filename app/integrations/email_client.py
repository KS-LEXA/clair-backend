from __future__ import annotations

"""
이메일 발송 공용 클라이언트 (fastapi-mail 기반).

모든 메일은 이 모듈을 통해서만 발송한다.
서비스 레이어는 send_email()만 호출하고, SMTP 세부사항·템플릿 렌더링은 여기서 처리.

사용 예:
    await send_email(
        to="user@example.com",
        subject="비밀번호 재설정 안내",
        template="password_reset.html",
        context={"nickname": "홍길동", "reset_url": "..."},
    )
"""
from pathlib import Path
from typing import Optional
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from app.core.config import settings


# 템플릿 디렉토리 — app/templates/emails/
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"


_conf = ConnectionConfig(
    MAIL_USERNAME=settings.smtp_user,
    MAIL_PASSWORD=settings.smtp_password,
    MAIL_FROM=settings.mail_from or settings.smtp_user,
    MAIL_FROM_NAME=settings.mail_from_name,
    MAIL_PORT=settings.smtp_port,
    MAIL_SERVER=settings.smtp_host,
    MAIL_STARTTLS=True,        # Gmail 587 포트는 STARTTLS
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
    TEMPLATE_FOLDER=_TEMPLATE_DIR,
)

_fm = FastMail(_conf)


async def send_email(
    to: str,
    subject: str,
    template: str,
    context: Optional[dict] = None,
) -> None:
    """
    이메일 1통 발송.

    to:       수신자 이메일
    subject:  메일 제목
    template: app/templates/emails/ 안 HTML 파일명 (예: "password_reset.html")
    context:  템플릿에 주입할 변수 dict
    """
    message = MessageSchema(
        subject=subject,
        recipients=[to],
        template_body=context or {},
        subtype=MessageType.html,
    )
    await _fm.send_message(message, template_name=template)
