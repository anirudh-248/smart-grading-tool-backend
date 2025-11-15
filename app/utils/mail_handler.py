import resend, logging
import anyio, anyio.to_thread
from env import env
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

resend.api_key = env.RESEND_API_KEY

# Custom exception for email sending failures
class EmailSendingError(Exception):
    pass

# Async send_mail function with retry mechanism
@retry(
    stop=stop_after_attempt(3),  # Retry up to 3 times
    wait=wait_fixed(30),         # Wait 30 seconds between retries
    retry=retry_if_exception_type(Exception),  # Retry on any exception
    before=lambda retry_state: logging.warning(
        "Retrying email send attempt %d...", retry_state.attempt_number
    ),
    after=lambda retry_state: logging.error(
        "Failed after %d attempts", retry_state.attempt_number
    ) if retry_state.outcome.failed else None
)
async def send_mail(contacts: list, subject: str, message: str) -> resend.Email:
    """
    Asynchronously send an email with retry mechanism.
    Raises EmailSendingError if all retries fail.
    """
    params: resend.Emails.SendParams = {
        "from": "SmartGrader <hello@smartgrader.online>",
        "to": contacts,
        "subject": subject,
        "html": message,
    }
    try:
        # Run synchronous resend.Emails.send in a thread
        email: resend.Email = await anyio.to_thread.run_sync(lambda: resend.Emails.send(params))
        logging.info("Email sent successfully to %s", contacts)
        return email
    except Exception as e:
        logging.error("Failed to send email to %s: %s", contacts, str(e))
        raise EmailSendingError(f"Failed to send email: {str(e)}")
