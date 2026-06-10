import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.settings import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    async def send_otp_email(to_email: str, otp: str) -> None:
        """
        Send an OTP email to the user.
        """
        try:
            if not settings.SMTP_HOST or not settings.SMTP_USER:
                logger.warning(f"SMTP not configured, would send OTP {otp} to {to_email}")
                print(f"OTP for {to_email}: {otp}")  # Fallback for development
                return

            subject = "Password Reset OTP"
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="background: linear-gradient(135deg, #ff6b35 0%, #ff8c5a 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                        <h1 style="color: white; margin: 0;">Siara Restaurant</h1>
                    </div>
                    <div style="padding: 30px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 10px 10px;">
                        <h2 style="color: #333;">Password Reset Request</h2>
                        <p style="color: #666; line-height: 1.6;">
                            We received a request to reset your password. Use the OTP below to proceed:
                        </p>
                        <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0;">
                            <h3 style="color: #ff6b35; font-size: 32px; margin: 0; letter-spacing: 4px;">{otp}</h3>
                        </div>
                        <p style="color: #999; font-size: 14px;">
                            This OTP will expire in 10 minutes. If you didn't request this, you can ignore this email.
                        </p>
                    </div>
                </body>
            </html>
            """

            msg = MIMEMultipart("alternative")
            msg["From"] = settings.SMTP_FROM
            msg["To"] = to_email
            msg["Subject"] = subject

            msg.attach(MIMEText(html_content, "html"))

            if settings.SMTP_PORT == 465:
                # Use SSL for port 465
                with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.send_message(msg)
            else:
                # Use STARTTLS for other ports (587)
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                    server.starttls()
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.send_message(msg)

            logger.info(f"Successfully sent OTP email to {to_email}")

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            print(f"OTP for {to_email}: {otp}")  # Fallback for development
