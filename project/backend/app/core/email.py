import resend
from app.config import settings


def send_verification_email(email: str, code: str) -> None:
    resend.api_key = settings.resend_api_key
    resend.Emails.send({
        "from": "ESG 세탁기 예약 <onboarding@resend.dev>",
        "to": email,
        "subject": "[ESG] 이메일 인증 코드",
        "html": (
            f"<p>안녕하세요!</p>"
            f"<p>ESG 기숙사 세탁기 예약 서비스 인증 코드입니다.</p>"
            f"<p>인증 코드: <strong style='font-size:24px'>{code}</strong></p>"
            f"<p>10분 이내에 입력해주세요.</p>"
        ),
    })
