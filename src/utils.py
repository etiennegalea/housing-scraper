import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

def notifify_email(func):
    def wrapper():
        # Note: This decorator seems incomplete as it doesn't call func or have content/to_email
        # But I will update it to at least use the correct settings variables
        message = Mail(
            from_email = settings.EMAIL_SEND_FROM,
            to_emails = settings.EMAIL_SEND_TO,
            subject = "Housing Scraper Notification",
            html_content = "Check the logs/output for details."
        )
        try:
            sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
            response = sg.send(message)
            return response.status_code
        except Exception:
            return None
    return wrapper