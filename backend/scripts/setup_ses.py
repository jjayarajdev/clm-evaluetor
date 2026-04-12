"""Configure AWS SES as the email provider.

Usage:
    # Using IAM credentials:
    uv run python -m scripts.setup_ses \
        --region us-east-1 \
        --access-key AKIAIOSFODNN7EXAMPLE \
        --secret-key wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY \
        --from-email notifications@evaluetor.com \
        --from-name "Evaluetor CLM"

    # Using EC2 instance role (no credentials needed):
    uv run python -m scripts.setup_ses \
        --region us-east-1 \
        --from-email notifications@evaluetor.com \
        --use-instance-role

    # Test sending:
    uv run python -m scripts.setup_ses --test --to test@example.com
"""

import argparse
import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.integration import (
    IntegrationConfig,
    IntegrationSystem,
    IntegrationStatus,
)


async def setup_ses(
    region: str,
    from_email: str,
    from_name: str,
    access_key: str | None = None,
    secret_key: str | None = None,
    configuration_set: str | None = None,
) -> None:
    """Create or update SES integration config."""
    async with async_session_maker() as db:
        # Deactivate any existing demo sendgrid config
        result = await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.system == IntegrationSystem.sendgrid,
                IntegrationConfig.is_demo == True,
                IntegrationConfig.is_active == True,
            )
        )
        for demo in result.scalars().all():
            demo.is_active = False
            print(f"  Deactivated demo SendGrid config: {demo.name}")

        # Check for existing SES config
        result = await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.system == IntegrationSystem.aws_ses,
            )
        )
        existing = result.scalar_one_or_none()

        credentials = {"region": region}
        if access_key and secret_key:
            credentials["aws_access_key_id"] = access_key
            credentials["aws_secret_access_key"] = secret_key

        config_data = {
            "from_email": from_email,
            "from_name": from_name,
        }
        if configuration_set:
            config_data["configuration_set"] = configuration_set

        if existing:
            existing.credentials = credentials
            existing.config = config_data
            existing.is_active = True
            existing.is_demo = False
            existing.health_status = IntegrationStatus.unknown
            print(f"  Updated existing SES config: {existing.id}")
        else:
            ses_config = IntegrationConfig(
                system=IntegrationSystem.aws_ses,
                name="AWS SES Email",
                description="AWS Simple Email Service for transactional emails",
                base_url="",
                auth_type="aws_iam",
                credentials=credentials,
                config=config_data,
                is_active=True,
                is_default=True,
                is_demo=False,
                health_status=IntegrationStatus.unknown,
            )
            db.add(ses_config)
            print(f"  Created new SES config")

        await db.commit()
        print(f"  AWS SES configured: region={region}, from={from_email}")


async def test_ses(to_email: str) -> None:
    """Send a test email through the configured SES integration."""
    async with async_session_maker() as db:
        from app.integrations.email import EmailService

        email_svc = EmailService(db)
        result = await email_svc.send_email(
            to_email=to_email,
            subject="Evaluetor CLM - Test Email",
            body="""<html><body style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
<div style="border-bottom: 3px solid #7c3aed; padding-bottom: 16px; margin-bottom: 24px;">
  <h1 style="margin: 0; color: #7c3aed;">Evaluetor</h1>
</div>
<p>This is a test email from your Evaluetor CLM platform.</p>
<p>If you received this, your AWS SES email integration is working correctly.</p>
<div style="border-top: 1px solid #e5e7eb; margin-top: 32px; padding-top: 16px; color: #9ca3af; font-size: 12px;">
  Sent by Evaluetor CLM
</div>
</body></html>""",
            is_html=True,
        )

        if result.get("mock"):
            print("  WARNING: Email sent via MOCK (no real email provider configured)")
            print("  Run setup_ses first to configure AWS SES")
        else:
            print(f"  Test email sent to {to_email}")
            if result.get("message_id"):
                print(f"  SES Message ID: {result['message_id']}")


def main():
    parser = argparse.ArgumentParser(description="Configure AWS SES email integration")
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")
    parser.add_argument("--access-key", help="AWS access key ID")
    parser.add_argument("--secret-key", help="AWS secret access key")
    parser.add_argument("--from-email", default="notifications@evaluetor.com", help="Sender email")
    parser.add_argument("--from-name", default="Evaluetor CLM", help="Sender name")
    parser.add_argument("--configuration-set", help="SES configuration set name")
    parser.add_argument("--use-instance-role", action="store_true", help="Use EC2 instance role")
    parser.add_argument("--test", action="store_true", help="Send test email")
    parser.add_argument("--to", help="Test email recipient")

    args = parser.parse_args()

    if args.test:
        if not args.to:
            print("Error: --to required with --test")
            sys.exit(1)
        print("Sending test email...")
        asyncio.run(test_ses(args.to))
    else:
        if not args.use_instance_role and not (args.access_key and args.secret_key):
            print("Error: Provide --access-key and --secret-key, or use --use-instance-role")
            sys.exit(1)

        print("Configuring AWS SES...")
        asyncio.run(setup_ses(
            region=args.region,
            from_email=args.from_email,
            from_name=args.from_name,
            access_key=args.access_key,
            secret_key=args.secret_key,
            configuration_set=args.configuration_set,
        ))

    print("Done.")


if __name__ == "__main__":
    main()
