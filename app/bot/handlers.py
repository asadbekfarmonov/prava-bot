from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from app.config import get_settings

router = Router()


@router.message(CommandStart())
async def start(message: Message) -> None:
    """Thin bot: /start -> welcome + a button that opens the Mini App."""
    settings = get_settings()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Ilovani ochish", web_app=WebAppInfo(url=settings.mini_app_url)
                )
            ]
        ]
    )
    await message.answer(
        "prava-bot — Yo'l harakati qoidalari (YHQ) nazariy imtihoniga tayyorgarlik. "
        "Mashq qilish uchun ilovani oching.",
        reply_markup=keyboard,
    )
