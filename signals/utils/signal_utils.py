import asyncio
import logging

from telegram import Bot

# Suppress HTTP request logs that contain the bot token
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)


async def send_message_async(chat_id: str, message: str, token: str):
    bot = Bot(token=token)
    await bot.send_message(chat_id=chat_id, text=message)


def send_message(chat_id: str, message: str, token: str):
    """
    Send a message to a Telegram chat (synchronous wrapper of the async send_message_async)

    Args:
        chat_id: The Telegram chat ID to send the message to
        message: The message text to send
        token: The Telegram bot token
    """
    asyncio.run(send_message_async(chat_id, message, token))
