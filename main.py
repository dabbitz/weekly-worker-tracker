import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from dotenv import load_dotenv

from app.services.ai_service import WorkUpdateExtractor
from app.services.date_normalizer import (
    normalize_eta_date,
    EtaResolutionStatus,
)
from app.schemas.work_update import WorkStatus


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


dp = Dispatcher()

extractor: WorkUpdateExtractor | None = None


STATUS_LABELS = {
    WorkStatus.COMPLETED: "Tamamlandı",
    WorkStatus.IN_PROGRESS: "Devam ediyor",
    WorkStatus.BLOCKED: "Engellendi",
    WorkStatus.NOT_STARTED: "Henüz başlanmadı",
    WorkStatus.UNKNOWN: "Belirsiz",
}


@dp.message(CommandStart())
async def start_handler(message: Message):

    await message.answer(
        "Merhaba!\n\n"
        "Haftalık İş Takip Sistemi demo botuna hoş geldin.\n\n"
        "İş güncellemelerini doğal dilde gönderebilirsin. "
        "Yapay zekâ mesajlarını analiz ederek yapılandırılmış "
        "iş güncellemelerine dönüştürecek."
    )


@dp.message(Command("help"))
async def help_handler(message: Message):

    await message.answer(
        "İş güncellemelerini doğal dilde gönderebilirsin.\n\n"
        "/start - Botu başlat\n"
        "/help - Yardım mesajını göster"
    )


@dp.message(Command("myid"))
async def myid_handler(message: Message):

    if message.from_user is None:
        return

    await message.answer(
        f"Telegram User ID: {message.from_user.id}"
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
        # 1. Extract structured information using Gemini

        result = await extractor.extract(message.text)

        # 2. Normalize the expected completion date
        # using the original Telegram message timestamp.

        eta_result = normalize_eta_date(
            eta_text=result.reported_eta_text,
            reference_datetime=message.date,
        )

        # 3. Build the response

        lines = [
            "İŞ GÜNCELLEMESİ ANALİZİ",
            "",
            f"İş: {result.task_reference_text or 'Belirtilmedi'}",
            f"Durum: {STATUS_LABELS.get(result.status, 'Belirsiz')}",
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

        # 4. Display normalized ETA

        lines.append("")

        if eta_result.status == EtaResolutionStatus.RESOLVED:

            normalized_date = eta_result.normalized_date

            lines.append(
                f"Çalışanın bitiş ifadesi: {result.reported_eta_text}"
            )

            lines.append(
                "Normalize edilmiş tahmini bitiş: "
                f"{normalized_date.strftime('%d.%m.%Y')}"
            )

        elif eta_result.status == EtaResolutionStatus.MISSING:

            lines.append(
                "Tahmini bitiş: Çalışan tarafından belirtilmedi."
            )

        else:

            lines.append(
                f"Çalışanın bitiş ifadesi: "
                f"{result.reported_eta_text}"
            )

            lines.append(
                "Tahmini bitiş tarihi netleştirilmeli."
            )

        # 5. Summary

        lines.extend([
            "",
            "ÖZET",
            result.summary,
            "",
            "Bu analiz henüz veritabanına kaydedilmedi."
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