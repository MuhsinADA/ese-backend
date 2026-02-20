"""
Reusable email utilities powered by SendGrid.

Centralises all outbound email logic so views stay thin and the
integration is easy to swap, mock, or extend.
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Low-level send helper
# ---------------------------------------------------------------------------

def _send_email(*, to_email, subject, html_content):
    """
    Send a single transactional email via the SendGrid Web API.

    Returns ``True`` on success, ``False`` if the key is missing or the
    API call fails.  Failures are logged but never raise — callers
    decide how to surface errors.
    """
    api_key = getattr(settings, "SENDGRID_API_KEY", "")
    if not api_key:
        logger.warning("SENDGRID_API_KEY not configured — email not sent.")
        return False

    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    message = Mail(
        from_email=getattr(
            settings,
            "DEFAULT_FROM_EMAIL",
            "noreply@esetaskmanager.com",
        ),
        to_emails=to_email,
        subject=subject,
        html_content=html_content,
    )

    try:
        client = SendGridAPIClient(api_key)
        response = client.send(message)
        logger.info(
            "Email sent to %s — status %s", to_email, response.status_code,
        )
        return True
    except Exception as exc:
        logger.error("SendGrid send failed for %s: %s", to_email, exc)
        return False


# ---------------------------------------------------------------------------
# Domain-specific email templates
# ---------------------------------------------------------------------------

def send_password_reset_email(user, reset_url):
    """
    Send a password-reset email with a one-time link.

    Parameters
    ----------
    user : User
        The user requesting the reset.
    reset_url : str
        Fully-qualified URL the user clicks to confirm the reset.

    Returns
    -------
    bool
        ``True`` if the email was handed off to SendGrid successfully.
    """
    display_name = user.first_name or user.username
    html = (
        f"<div style='font-family:sans-serif;max-width:600px;margin:auto'>"
        f"<h2 style='color:#1e293b'>Password Reset</h2>"
        f"<p>Hi {display_name},</p>"
        f"<p>You requested a password reset for your ESE Task Manager "
        f"account. Click the button below to set a new password:</p>"
        f"<p style='text-align:center;margin:32px 0'>"
        f"<a href='{reset_url}' style='background:#2563eb;color:#fff;"
        f"padding:12px 32px;border-radius:6px;text-decoration:none;"
        f"font-weight:600'>Reset Password</a></p>"
        f"<p style='font-size:13px;color:#64748b'>Or copy and paste this "
        f"link into your browser:</p>"
        f"<p style='font-size:13px;word-break:break-all'>{reset_url}</p>"
        f"<hr style='border:none;border-top:1px solid #e2e8f0;margin:24px 0'>"
        f"<p style='font-size:12px;color:#94a3b8'>This link expires in "
        f"1 hour. If you did not request this, you can safely ignore "
        f"this email.</p>"
        f"</div>"
    )
    return _send_email(
        to_email=user.email,
        subject="Password Reset — ESE Task Manager",
        html_content=html,
    )


def send_welcome_email(user):
    """
    Send a welcome email after successful registration.

    Parameters
    ----------
    user : User
        The newly registered user.

    Returns
    -------
    bool
        ``True`` if the email was handed off to SendGrid successfully.
    """
    display_name = user.first_name or user.username
    frontend_url = getattr(settings, "FRONTEND_BASE_URL", "")
    html = (
        f"<div style='font-family:sans-serif;max-width:600px;margin:auto'>"
        f"<h2 style='color:#1e293b'>Welcome to ESE Task Manager!</h2>"
        f"<p>Hi {display_name},</p>"
        f"<p>Your account has been created successfully. You can start "
        f"organising your tasks right away.</p>"
        f"<p style='text-align:center;margin:32px 0'>"
        f"<a href='{frontend_url}/login' style='background:#2563eb;"
        f"color:#fff;padding:12px 32px;border-radius:6px;"
        f"text-decoration:none;font-weight:600'>Go to Dashboard</a></p>"
        f"<p style='font-size:12px;color:#94a3b8'>If you did not create "
        f"this account, please ignore this email.</p>"
        f"</div>"
    )
    return _send_email(
        to_email=user.email,
        subject="Welcome to ESE Task Manager",
        html_content=html,
    )
