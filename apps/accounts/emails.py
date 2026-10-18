import logging
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

def get_luxury_email_wrapper(title: str, content_html: str) -> str:
    """
    Renders standard luxury brand HTML email wrapper.
    """
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #FAF8F3; margin: 0; padding: 20px 10px; color: #222426; }}
    .container {{ max-width: 560px; margin: 0 auto; background-color: #ffffff; border: 1px solid #E6E1D8; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.04); }}
    .header {{ background-color: #11663C; padding: 28px 24px; text-align: center; color: #FAF8F3; }}
    .header h1 {{ margin: 0; font-size: 20px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; }}
    .header p {{ margin: 4px 0 0 0; font-size: 11px; opacity: 0.85; letter-spacing: 1.5px; text-transform: uppercase; }}
    .body {{ padding: 32px 28px; line-height: 1.6; font-size: 14px; color: #2D3134; }}
    .otp-box {{ background-color: #FAF8F3; border: 1px solid #16894F; border-radius: 6px; padding: 18px; margin: 24px 0; text-align: center; }}
    .otp-code {{ font-size: 32px; font-weight: 700; letter-spacing: 6px; color: #11663C; font-family: monospace; }}
    .button {{ display: inline-block; background-color: #16894F; color: #ffffff !important; text-decoration: none; padding: 14px 28px; border-radius: 4px; font-weight: 600; font-size: 13px; letter-spacing: 1px; text-transform: uppercase; margin: 20px 0; }}
    .footer {{ background-color: #F4F1E9; padding: 20px 24px; text-align: center; font-size: 11px; color: #6E7479; border-top: 1px solid #E6E1D8; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Modiecommers</h1>
      <p>Fine Jewellery & Solitaires</p>
    </div>
    <div class="body">
      {content_html}
    </div>
    <div class="footer">
      <p>&copy; 2026 Modiecommers Fine Jewellery. All rights reserved.</p>
      <p>This is an automated security transmission. Please do not reply directly to this email.</p>
    </div>
  </div>
</body>
</html>"""

def send_verification_otp_email(user, otp_code: str):
    """
    Sends time-limited 6-digit OTP verification email to user.
    Returns (success: bool, error_message: str | None).
    """
    subject = f"Your Modiecommers Verification Code: {otp_code}"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@modiecommers.com')
    recipient_list = [user.email]

    display_name = user.profile.display_name if hasattr(user, 'profile') else user.email.split('@')[0]
    expiry_minutes = getattr(settings, 'EMAIL_OTP_EXPIRY_SECONDS', 600) // 60

    content_html = f"""
      <h2 style="font-size: 18px; color: #11663C; margin-top: 0;">Verify Your Email Address</h2>
      <p>Dear {display_name},</p>
      <p>Welcome to <strong>Modiecommers</strong>. To activate your patron account and begin exploring our bespoke solitaires and handcrafted fine jewellery, please use the verification code below:</p>
      
      <div class="otp-box">
        <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #6E7479; margin-bottom: 6px;">Your One-Time Password (OTP)</div>
        <div class="otp-code">{otp_code}</div>
        <div style="font-size: 11px; color: #6E7479; margin-top: 6px;">Valid for {expiry_minutes} minutes</div>
      </div>

      <p style="font-size: 12px; color: #6E7479;">If you did not initiate this registration request, please disregard this email. Your email address remains secure.</p>
    """

    html_message = get_luxury_email_wrapper("Modiecommers Patron Email Verification", content_html)
    plain_message = f"""Modiecommers Fine Jewellery & Solitaires

Dear {display_name},

Welcome to Modiecommers. Your account verification code is:

{otp_code}

This code is valid for {expiry_minutes} minutes.
If you did not create an account, please ignore this email.
"""

    import time
    for attempt in range(2):
        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=plain_message,
                from_email=from_email,
                to=recipient_list
            )
            msg.attach_alternative(html_message, "text/html")
            msg.send(fail_silently=False)
            return True, None
        except Exception as exc:
            if attempt == 0:
                time.sleep(0.5)
                continue
            logger.error("Failed to send OTP verification email to %s: %s", user.email, str(exc))
            return False, f"Could not send email: {str(exc)}"


def send_password_reset_email(user, reset_url: str):
    """
    Sends password reset link email to user.
    Returns (success: bool, error_message: str | None).
    """
    subject = "Reset Your Modiecommers Account Password"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@modiecommers.com')
    recipient_list = [user.email]

    display_name = user.profile.display_name if hasattr(user, 'profile') else user.email.split('@')[0]
    timeout_minutes = getattr(settings, 'PASSWORD_RESET_TIMEOUT', 3600) // 60

    content_html = f"""
      <h2 style="font-size: 18px; color: #11663C; margin-top: 0;">Password Reset Request</h2>
      <p>Dear {display_name},</p>
      <p>We received a request to reset the password for your Modiecommers account. Click the button below to establish a new password:</p>
      
      <div style="text-align: center; margin: 28px 0;">
        <a href="{reset_url}" class="button" target="_blank" rel="noopener noreferrer">Reset Password</a>
      </div>

      <p style="font-size: 12px; color: #6E7479;">
        Or paste this link into your browser: <br>
        <a href="{reset_url}" style="color: #16894F; word-break: break-all;">{reset_url}</a>
      </p>

      <p style="font-size: 12px; color: #6E7479; margin-top: 20px;">
        This password reset link will expire in {timeout_minutes} minutes and can only be used once.<br>
        If you did not request this change, you can safely disregard this message; your current password remains protected.
      </p>
    """

    html_message = get_luxury_email_wrapper("Modiecommers Password Reset", content_html)
    plain_message = f"""Modiecommers Fine Jewellery & Solitaires

Dear {display_name},

We received a request to reset your Modiecommers password. Use the link below to choose a new password:

{reset_url}

This link is valid for {timeout_minutes} minutes.
If you did not request this, please ignore this email.
"""

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=from_email,
            to=recipient_list
        )
        msg.attach_alternative(html_message, "text/html")
        msg.send(fail_silently=False)
        return True, None
    except Exception as exc:
        logger.error("Failed to send password reset email to %s: %s", user.email, str(exc))
        return False, f"Could not send email: {str(exc)}"


def send_password_reset_otp_email(user, otp_code: str):
    """
    Sends time-limited 6-digit password recovery OTP to user.
    Returns (success: bool, error_message: str | None).
    """
    subject = f"Your Modiecommers Password Recovery Code: {otp_code}"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@modiecommers.com')
    recipient_list = [user.email]

    display_name = user.profile.display_name if hasattr(user, 'profile') else user.email.split('@')[0]
    expiry_minutes = getattr(settings, 'EMAIL_OTP_EXPIRY_SECONDS', 600) // 60

    content_html = f"""
      <h2 style="font-size: 18px; color: #11663C; margin-top: 0;">Password Recovery Code</h2>
      <p>Dear {display_name},</p>
      <p>We received a request to reset the password for your Modiecommers fine jewellery account. Use the 6-digit security code below to proceed with resetting your password:</p>
      
      <div class="otp-box">
        <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #6E7479; margin-bottom: 6px;">Your Password Recovery OTP</div>
        <div class="otp-code">{otp_code}</div>
        <div style="font-size: 11px; color: #6E7479; margin-top: 6px;">Valid for {expiry_minutes} minutes</div>
      </div>

      <p style="font-size: 12px; color: #6E7479;">
        This code is single-use and will expire in {expiry_minutes} minutes.<br>
        If you did not request this recovery code, your account remains secure and no action is required.
      </p>
    """

    html_message = get_luxury_email_wrapper("Modiecommers Password Recovery", content_html)
    plain_message = f"""Modiecommers Fine Jewellery & Solitaires

Dear {display_name},

We received a request to reset your Modiecommers password. Your password recovery OTP is:

{otp_code}

This code is valid for {expiry_minutes} minutes.
If you did not request this, please ignore this email.
"""

    import time
    for attempt in range(2):
        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=plain_message,
                from_email=from_email,
                to=recipient_list
            )
            msg.attach_alternative(html_message, "text/html")
            msg.send(fail_silently=False)
            return True, None
        except Exception as exc:
            if attempt == 0:
                time.sleep(0.5)
                continue
            logger.error("Failed to send password recovery OTP to %s: %s", user.email, str(exc))
            return False, f"Could not send email: {str(exc)}"

