import os
import logging

import httpx

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, EmailStr


# ==========================================================
# LOAD ENV
# ==========================================================




# ==========================================================
# CONFIG
# ==========================================================

AUTH_TOKEN = os.getenv("AUTH_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

TELEGRAM_CHAT_GREEN = os.getenv("TELEGRAM_CHAT_GREEN")
TELEGRAM_CHAT_BLUE = os.getenv("TELEGRAM_CHAT_BLUE")
TELEGRAM_CHAT_PINK = os.getenv("TELEGRAM_CHAT_PINK")


# ==========================================================
# VALIDATE CONFIG
# ==========================================================

required_config = {
    "AUTH_TOKEN": AUTH_TOKEN,
    "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
    "TELEGRAM_CHAT_GREEN": TELEGRAM_CHAT_GREEN,
    "TELEGRAM_CHAT_BLUE": TELEGRAM_CHAT_BLUE,
    "TELEGRAM_CHAT_PINK": TELEGRAM_CHAT_PINK,
}

missing_config = [
    key for key, value in required_config.items()
    if not value
]

if missing_config:
    raise RuntimeError(
        f"Missing environment variables: {', '.join(missing_config)}"
    )


# ==========================================================
# TEAM -> TELEGRAM CHAT ID
# ==========================================================

TEAM_CHAT_IDS = {
    "green": TELEGRAM_CHAT_GREEN,
    "blue": TELEGRAM_CHAT_BLUE,
    "pink": TELEGRAM_CHAT_PINK,
}


# ==========================================================
# LOGGING
# ==========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# ==========================================================
# FASTAPI
# ==========================================================

app = FastAPI(
    title="Lead Telegram Webhook",
    version="1.0.0"
)


# ==========================================================
# REQUEST MODEL
# ==========================================================

class Lead(BaseModel):
    email: EmailStr
    subid: str
    buyer: str
    team: str


# ==========================================================
# HEALTH CHECK
# ==========================================================

@app.get("/")
async def root():
    return {
        "success": True,
        "service": "Lead Telegram Webhook"
    }


# ==========================================================
# WEBHOOK
# ==========================================================

@app.post("/webhook")
async def webhook(
    lead: Lead,
    x_auth_token: str | None = Header(default=None)
):

    # ------------------------------------------------------
    # AUTH
    # ------------------------------------------------------

    if not x_auth_token:
        raise HTTPException(
            status_code=401,
            detail="Authorization token is missing"
        )

    if x_auth_token != AUTH_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization token"
        )

    # ------------------------------------------------------
    # NORMALIZE TEAM
    # ------------------------------------------------------

    team = lead.team.strip().lower()

    # ------------------------------------------------------
    # FIND TELEGRAM CHAT
    # ------------------------------------------------------

    if team not in TEAM_CHAT_IDS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown team: {team}. "
                f"Allowed values: green, blue, pink"
            )
        )

    chat_id = TEAM_CHAT_IDS[team]

    # ------------------------------------------------------
    # TELEGRAM MESSAGE
    # ------------------------------------------------------

    message = (
        "📩 <b>New Lead</b>\n\n"
        f"📧 <b>Email:</b> {lead.email}\n"
        f"🔗 <b>SubID:</b> {lead.subid}\n"
        f"👤 <b>Buyer:</b> {lead.buyer}\n"
        f"👥 <b>Team:</b> {team}"
    )

    # ------------------------------------------------------
    # TELEGRAM API
    # ------------------------------------------------------

    telegram_url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    telegram_data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:

            response = await client.post(
                telegram_url,
                data=telegram_data
            )

    except httpx.RequestError as e:

        logger.error(
            "Telegram connection error: %s",
            str(e)
        )

        raise HTTPException(
            status_code=502,
            detail="Failed to connect to Telegram"
        )

    # ------------------------------------------------------
    # TELEGRAM RESPONSE
    # ------------------------------------------------------

    try:
        telegram_response = response.json()
    except Exception:
        telegram_response = {}

    if (
        response.status_code != 200
        or telegram_response.get("ok") is not True
    ):

        logger.error(
            "Telegram API error: %s",
            telegram_response
        )

        raise HTTPException(
            status_code=502,
            detail="Telegram API error"
        )

    # ------------------------------------------------------
    # SUCCESS
    # ------------------------------------------------------

    logger.info(
        "Lead sent successfully | team=%s | subid=%s",
        team,
        lead.subid
    )

    return {
        "success": True,
        "message": "Lead successfully sent to Telegram",
        "team": team
    }