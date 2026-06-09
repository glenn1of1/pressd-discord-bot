import asyncio

from bot import ValoPresserBot


async def main() -> None:
    bot = ValoPresserBot()
    async with bot:
        await bot.start_bot()


if __name__ == "__main__":
    asyncio.run(main())
