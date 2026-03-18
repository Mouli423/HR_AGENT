import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from src.hr_agent.core.state import GraphState
from src.hr_agent.config.settings import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
from src.hr_agent.tools.logger import get_logger


def _send_email(to_email: str, subject: str, body: str, log):
    if not SMTP_USER or not SMTP_PASSWORD:
        print(f"\n{'='*60}")
        print(f"[EMAIL PREVIEW]")
        print(f"To      : {to_email}")
        print(f"Subject : {subject}")
        print(f"{'='*60}")
        print(body)
        print(f"{'='*60}\n")
        log.info("email_preview", to=to_email, subject=subject, mode="preview")
        return

    try:
        msg            = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = SMTP_USER
        msg["To"]      = to_email
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())

        print(f"[EMAIL SENT → {to_email}]")
        log.info("email_sent", to=to_email, subject=subject, mode="smtp")

    except Exception as e:
        print(f"[EMAIL ERROR: {e}]")
        log.error("email_failed", to=to_email, subject=subject,
                  error_type=e.__class__.__name__, error=str(e))


def send_acceptance_email(state: GraphState) -> dict:
    print("--- EMAIL: Acceptance ---")
    log       = get_logger("email_nodes")
    candidate = state.get("candidate_name", "")

    log.info("sending_acceptance_email",
        candidate=candidate,
        role=state.get("applied_role", ""),
    )

    _send_email(
        to_email = state.get("candidate_email", ""),
        subject  = f"🎉 Next Steps — {state.get('applied_role', '')}",
        body     = (
            f"Dear {state.get('candidate_name', 'Candidate')},\n\n"
            f"{state.get('next_steps', '')}\n\n"
            f"Warm regards,\nTalent Acquisition Team"
        ),
        log=log,
    )
    return {"email_sent": True}


def send_rejection_email(state: GraphState) -> dict:
    print("--- EMAIL: Rejection ---")
    log       = get_logger("email_nodes")
    candidate = state.get("candidate_name", "")

    log.info("sending_rejection_email",
        candidate=candidate,
        role=state.get("applied_role", ""),
    )

    _send_email(
        to_email = state.get("candidate_email", ""),
        subject  = f"Your Application — {state.get('applied_role', '')}",
        body     = (
            f"Dear {state.get('candidate_name', 'Candidate')},\n\n"
            f"{state.get('rejection_reason', '')}\n\n"
            f"Kind regards,\nTalent Acquisition Team"
        ),
        log=log,
    )
    return {"email_sent": True}