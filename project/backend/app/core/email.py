import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings


def send_verification_email(email: str, code: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "[ESG] 이메일 인증 코드"
    msg["From"] = settings.gmail_user
    msg["To"] = email

    html = (
        f"<p>안녕하세요!</p>"
        f"<p>ESG 기숙사 세탁기 예약 서비스 인증 코드입니다.</p>"
        f"<p>인증 코드: <strong style='font-size:24px'>{code}</strong></p>"
        f"<p>10분 이내에 입력해주세요.</p>"
    )
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(settings.gmail_user, settings.gmail_app_password)
        server.sendmail(settings.gmail_user, email, msg.as_string())
