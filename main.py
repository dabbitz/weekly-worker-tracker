import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from dotenv import load_dotenv

from app.services.ai_service import WorkUpdateExtractor
from app.schemas.work_update import WorkStatus


# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite"
)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing.")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing.")


# Initialize dispatcher
dp = Dispatcher()

# AI service will be initialized when the bot starts
extractor: WorkUpdateExtractor | None = None


STATUS_LABELS = {
    WorkStatus.COMPLETED: "Tamamlandı",
    WorkStatus.IN_PROGRESS: "Devam ediyor",
    WorkStatus.BLOCKED: "Engellendi",
    WorkStatus.NOT_STARTED: "Henüz başlanmadı",
    WorkStatus.UNKNOWN: "Belirsiz"
}


@dp.message(CommandStart())
async def start_handler(message: Message):

    await message.answer(
        "Merhaba!\n\n"
        "Haftalık İş Takip Sistemi demo botuna hoş geldin.\n\n"
        "Artık gönderdiğin iş güncellemelerini "
        "yapay zekâ ile analiz edebilirim.\n\n"
        "Örneğin:\n"
        "\"Elektrik tesisatının %70'ini tamamladık. "
        "Malzeme eksikliği nedeniyle kalan kısmı bitiremedik.\""
    )


@dp.message(Command("help"))
async def help_handler(message: Message):

    await message.answer(
        "İş güncellemelerini doğal dilde gönderebilirsin.\n\n"
        "/start - Botu başlat\n"
        "/help - Yardım mesajını göster"
    )


@dp.message(F.text)
async def text_handler(message: Message):

    if extractor is None:
        await message.answer(
            "Yapay zekâ servisi henüz hazır değil."
        )
        return

    await message.answer(
        "Mesajını inceliyorum..."
    )

    try:
        result = await extractor.extract(message.text)

        status_label = STATUS_LABELS.get(
            result.status,
            "Belirsiz"
        )

        lines = [
            "İŞ GÜNCELLEMESİ ANALİZİ",
            "",
            f"İş: {result.task_name or 'Belirtilmedi'}",
            f"Durum: {status_label}",
        ]

        if result.completion_percentage is not None:
            lines.append(
                f"Gerçekleşme: %{result.completion_percentage}"
            )

        if result.blocker:
            lines.append(f"Engel: {result.blocker}")

        if result.delay_reason:
            lines.append(
                f"Gecikme nedeni: {result.delay_reason}"
            )

        if result.next_step:
            lines.append(
                f"Sonraki adım: {result.next_step}"
            )

        if result.expected_completion:
            lines.append(
                f"Tahmini tamamlanma: {result.expected_completion}"
            )

        lines.extend([
            "",
            "ÖZET",
            result.summary,
            "",
            "Bu, yapay zekâ tarafından oluşturulmuş "
            "bir analizdir."
        ])

        await message.answer("\n".join(lines))

    except Exception:
        logging.exception("Work update analysis failed.")

        await message.answer(
            "Mesajını analiz ederken bir hata oluştu. "
            "Lütfen biraz sonra tekrar dene."
        )


@dp.message()
async def unsupported_handler(message: Message):

    await message.answer(
        "Şimdilik yalnızca metin mesajlarını destekliyorum."
    )


async def main():

    global extractor

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    extractor = WorkUpdateExtractor(
        api_key=GEMINI_API_KEY,
        model=GEMINI_MODEL
    )

    try:
        async with Bot(token=BOT_TOKEN) as bot:

            logging.info("Telegram bot is starting...")
            logging.info("AI model: %s", GEMINI_MODEL)

            await dp.start_polling(bot)

    finally:
        await extractor.close()
        logging.info("AI service closed.")


if __name__ == "__main__":
    asyncio.run(main())