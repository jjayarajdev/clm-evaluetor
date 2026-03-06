"""Test script for Microsoft Teams Power Automate webhook.

Usage:
    python -m scripts.test_teams_webhook <POWER_AUTOMATE_URL>

Example:
    python -m scripts.test_teams_webhook "https://prod-xx.westus.logic.azure.com:443/workflows/..."
"""

import asyncio
import sys
from datetime import datetime

import httpx


def build_adaptive_card(
    title: str,
    message: str,
    severity: str = "info",
) -> dict:
    """Build an Adaptive Card for Teams."""
    severity_icons = {
        "info": "ℹ️",
        "success": "✅",
        "warning": "⚠️",
        "error": "🚨",
    }
    icon = severity_icons.get(severity, "ℹ️")

    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "size": "Large",
                "weight": "Bolder",
                "text": f"{icon} {title}",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": message,
                "wrap": True,
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": "Source", "value": "CLM Platform"},
                    {"title": "Type", "value": "Test Notification"},
                    {"title": "Timestamp", "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")},
                ],
            },
            {
                "type": "TextBlock",
                "text": f"Sent at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                "size": "Small",
                "isSubtle": True,
            },
        ],
    }


async def test_webhook(url: str) -> bool:
    """Test the Power Automate webhook with a sample notification."""
    print(f"\n🔗 Testing webhook URL...")
    print(f"   URL: {url[:60]}...")

    card = build_adaptive_card(
        title="CLM Test Notification",
        message="This is a test notification from the Contract Lifecycle Management platform. "
                "If you see this message in your Teams channel, the integration is working correctly!",
        severity="success",
    )

    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": card,
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            print("\n📤 Sending test notification...")
            response = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            print(f"\n📥 Response:")
            print(f"   Status: {response.status_code}")

            if response.status_code in (200, 202):
                print(f"\n✅ SUCCESS! Check your Teams channel for the notification.")
                return True
            else:
                print(f"   Body: {response.text[:500]}")
                print(f"\n❌ FAILED: Unexpected status code {response.status_code}")
                return False

    except httpx.ConnectError as e:
        print(f"\n❌ Connection Error: {e}")
        print("   Make sure the URL is correct and accessible.")
        return False
    except httpx.TimeoutException:
        print(f"\n❌ Timeout: Request took too long")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    url = sys.argv[1]

    print("=" * 60)
    print("Microsoft Teams Power Automate Webhook Test")
    print("=" * 60)

    success = await test_webhook(url)

    print("\n" + "=" * 60)
    if success:
        print("Integration test PASSED!")
        print("\nNext steps:")
        print("1. Create a Teams integration in CLM Admin")
        print("2. Use this URL as the base_url")
        print("3. Test notifications from the CLM platform")
    else:
        print("Integration test FAILED!")
        print("\nTroubleshooting:")
        print("1. Verify the Power Automate workflow is enabled")
        print("2. Check the URL is correctly copied (including all parameters)")
        print("3. Ensure the workflow has 'When a HTTP request is received' trigger")
    print("=" * 60)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
