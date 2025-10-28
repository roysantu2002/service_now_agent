# email.py

import os
import smtplib
import logging
from jinja2 import Template
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")


class NotifyEmail:
    """
    Utility class for sending notification emails using Jinja2 HTML templates.
    """

    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.sender_email = os.getenv("SMTP_SENDER_EMAIL", "")
        self.sender_password = os.getenv("SMTP_SENDER_PASSWORD", "")
        self.default_recipient = os.getenv("SMTP_DEFAULT_RECIPIENT", "")
        self.template_dir = os.getenv("EMAIL_TEMPLATE_DIR", "/home/app/usecasedetails/templates/")

    def _load_template(self, template_name: str) -> Template:
        """Load and compile a Jinja2 HTML template."""
        try:
            template_path = os.path.join(self.template_dir, template_name)
            with open(template_path, "r") as file:
                template_str = file.read()
            return Template(template_str)
        except Exception as e:
            logging.error(f"Failed to load email template: {e}")
            raise

    def _send_email(self, subject: str, to: str, email_data: dict, template_name: str):
        """Render the email template and send the email."""
        try:
            # Prepare message
            jinja_template = self._load_template(template_name)
            email_content = jinja_template.render(email_data)

            msg = MIMEMultipart()
            msg["From"] = self.sender_email
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(email_content, "html"))

            # Connect and send
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                if self.sender_password:
                    server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, to.split(","), msg.as_string())

            logging.info(f"✅ Email sent successfully to {to}")

        except Exception as e:
            logging.error(f"❌ Failed to send email to {to}: {e}")

    def send_project_mail(self, project_name: str, project_id: str, git_url: str, git_branch: str,
                          aap_project_id: str, aap_template_id: str, to: str = None):
        """Send notification email for a successfully created project."""
        subject = f"CraftBot - Project Created: {project_name}"
        email_data = {
            "subject": subject,
            "greeting": "Hello,",
            "projectname": project_name,
            "projectid": project_id,
            "giturl": git_url,
            "git_branch": git_branch,
            "aap_project_id": aap_project_id,
            "aap_template_id": aap_template_id,
            "message": "Your Ansible project and job template were successfully created.",
            "sender_name": "Automation Team",
        }
        self._send_email(subject, to or self.default_recipient, email_data, "template.html")

    def send_fail_mail(self, project_name: str, project_id: str, error_message: str = "", to: str = None):
        """Send failure notification email."""
        subject = f"CraftBot - Failed to Create Project: {project_name}"
        email_data = {
            "subject": subject,
            "greeting": "Hello,",
            "projectname": project_name,
            "projectid": project_id,
            "message": f"An error occurred while processing your request: {error_message}",
            "sender_name": "Automation Team",
        }
        self._send_email(subject, to or self.default_recipient, email_data, "template.html")

    def send_entry_mail(self, usecase_id: str, usecase_name: str, category: str,
                        usecase_status: str, status: str, to: str = None):
        """Send notification email for a new automation request entry."""
        subject = f"CraftBot - New Automation Request: {usecase_name}"
        email_data = {
            "subject": subject,
            "greeting": "Hello,",
            "projectname": usecase_name,
            "projectid": usecase_id,
            "category": category,
            "usecasestatus": usecase_status,
            "status": status,
            "message": "Successfully added a new entry for automation request.",
            "sender_name": "Automation Team",
        }
        self._send_email(subject, to or self.default_recipient, email_data, "template.html")


if __name__ == "__main__":
    # Example test run (for dev)
    notifier = NotifyEmail()
    notifier.send_project_mail(
        project_name="DemoProject",
        project_id="1234",
        git_url="https://github.com/example/demo.git",
        git_branch="main",
        aap_project_id="5678",
        aap_template_id="91011",
    )
