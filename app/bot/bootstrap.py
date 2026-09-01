from aiogram import Bot, Dispatcher

from app.bot.handlers import router


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher


def create_bot(token: str) -> Bot:
    return Bot(token=token)
