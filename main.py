import asyncio

from bot import ValoPresserBot, setup_logging


async def main() -> None:
    setup_logging()
    bot = ValoPresserBot()
    async with bot:
        await bot.start_bot()


if __name__ == "__main__":
    asyncio.run(main())
