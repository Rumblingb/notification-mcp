#!/usr/bin/env python3
"""Notification MCP — Send alerts via Slack, Discord, Email, and webhooks."""

import json, os, smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from mcp.server.lowlevel import Server, stdio_server
import httpx

server = Server("notification-mcp")

@server.tool(
    name="notify_slack",
    description="Send a message to a Slack channel via webhook.",
    input_schema={
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Message text to send"},
            "webhook_url": {"type": "string", "description": "Slack webhook URL (or set env SLACK_WEBHOOK_URL)"}
        },
        "required": ["message"]
    }
)
async def notify_slack(message: str, webhook_url: str = "") -> str:
    try:
        url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL", "")
        if not url:
            return json.dumps({"error": "No Slack webhook URL provided. Set SLACK_WEBHOOK_URL env var or pass webhook_url.", "isError": True}, indent=2)
        
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={"text": message})
            resp.raise_for_status()
            return json.dumps({"status": "sent", "channel": "Slack"}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "isError": True}, indent=2)

@server.tool(
    name="notify_discord",
    description="Send a message to a Discord channel via webhook.",
    input_schema={
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Message text to send"},
            "webhook_url": {"type": "string", "description": "Discord webhook URL (or set env DISCORD_WEBHOOK_URL)"},
            "username": {"type": "string", "description": "Override bot username", "default": ""}
        },
        "required": ["message"]
    }
)
async def notify_discord(message: str, webhook_url: str = "", username: str = "") -> str:
    try:
        url = webhook_url or os.environ.get("DISCORD_WEBHOOK_URL", "")
        if not url:
            return json.dumps({"error": "No Discord webhook URL. Set DISCORD_WEBHOOK_URL env var or pass webhook_url.", "isError": True}, indent=2)
        
        payload = {"content": message}
        if username:
            payload["username"] = username
        
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return json.dumps({"status": "sent", "channel": "Discord"}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "isError": True}, indent=2)

@server.tool(
    name="notify_email",
    description="Send an email via SMTP.",
    input_schema={
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient email address"},
            "subject": {"type": "string", "description": "Email subject"},
            "body": {"type": "string", "description": "Email body text"},
            "cc": {"type": "string", "description": "CC recipients (comma-separated)", "default": ""}
        },
        "required": ["to", "subject", "body"]
    }
)
async def notify_email(to: str, subject: str, body: str, cc: str = "") -> str:
    try:
        smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        email_addr = os.environ.get("EMAIL_ADDRESS", "")
        email_pass = os.environ.get("EMAIL_PASSWORD", "")
        
        if not email_addr or not email_pass:
            return json.dumps({"error": "Email not configured. Set EMAIL_ADDRESS and EMAIL_PASSWORD env vars.", "isError": True}, indent=2)
        
        msg = MIMEMultipart()
        msg["From"] = email_addr
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        msg.attach(MIMEText(body, "plain"))
        
        all_recipients = [to] + ([c.strip() for c in cc.split(",") if c.strip()] if cc else [])
        
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(email_addr, email_pass)
            server.sendmail(email_addr, all_recipients, msg.as_string())
        
        return json.dumps({"status": "sent", "to": to, "cc": cc or "none", "via": smtp_server}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "isError": True}, indent=2)

@server.tool(
    name="notify_webhook",
    description="Send a generic webhook POST request with custom payload.",
    input_schema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Webhook URL"},
            "payload_json": {"type": "string", "description": "JSON payload to send"},
            "method": {"type": "string", "enum": ["POST", "PUT"], "default": "POST"}
        },
        "required": ["url", "payload_json"]
    }
)
async def notify_webhook(url: str, payload_json: str, method: str = "POST") -> str:
    try:
        payload = json.loads(payload_json)
        async with httpx.AsyncClient(timeout=10) as client:
            if method == "PUT":
                resp = await client.put(url, json=payload)
            else:
                resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return json.dumps({"status": "sent", "url": url, "status_code": resp.status_code}, indent=2)
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON payload", "isError": True}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "isError": True}, indent=2)

def main():
    import anyio
    async def run():
        async with stdio_server() as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())
    anyio.run(run)

if __name__ == "__main__":
    main()
