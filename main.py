import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.filters.command import CommandObject
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from dotenv import load_dotenv

from app.bot.handlers import (
    register_report_handlers,
    set_extractor,
)
from app.services.ai_service import WorkUpdateExtractor

from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from app.services.employee_service import (
    create_registration_request,
    mark_registration_notified,
    review_registration_request,
)


load_dotenv()

ADMIN_TELEGRAM_ID_RAW = os.getenv("ADMIN_TELEGRAM_ID")

ADMIN_TELEGRAM_ID = (
    int(ADMIN_TELEGRAM_ID_RAW)
    if ADMIN_TELEGRAM_ID_RAW
    else None
)
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


dp = Dispatcher(storage=MemoryStorage())


@dp.message(CommandStart())
async def start_handler(message: Message):

    await message.answer(
        "Merhaba!\n\n"
        "WorkTrack Haftalık İş Takip Sistemine hoş geldin.\n\n"
        "Görevlerini görmek ve çalışma raporu göndermek için "
        "/gorevlerim komutunu kullanabilirsin. "
        "Kayıt için /register İsim Soyisim komutunu kullan."
    )


@dp.message(Command("help"))
async def help_handler(message: Message):

    await message.answer(
        "Çalışma raporlarını seçtiğin görevle ilişkilendirerek "
        "gönderebilirsin.\n\n"
        "/start - Botu başlat\n"
        "/help - Yardım mesajını göster\n"
        "/gorevlerim - Görevlerini listele ve rapor gönder\n"
        "/rapor - /gorevlerim ile aynı işlev\n"
        "/register İsim Soyisim - Kayıt talebi oluştur\n"
    )


@dp.message(Command("myid"))
async def myid_handler(message: Message):

    if message.from_user is None:
        return

    await message.answer(
        f"Telegram User ID: {message.from_user.id}"
    )


# ==========================================
# EMPLOYEE REGISTRATION
# ==========================================

@dp.message(Command("register"))
async def register_handler(
    message: Message,
    command: CommandObject
):

    if message.chat.type != "private":
        await message.answer(
            "Lütfen kayıt işlemini botla özel sohbet üzerinden yap."
        )
        return

    if message.from_user is None:
        return

    if ADMIN_TELEGRAM_ID is None:
        await message.answer(
            "Kayıt sistemi henüz yapılandırılmamış."
        )
        logging.error("ADMIN_TELEGRAM_ID is missing.")
        return

    full_name = " ".join(
        (command.args or "").split()
    )

    if len(full_name.split()) < 2:
        await message.answer(
            "Lütfen adını ve soyadını gir.\n\n"
            "Kullanım:\n"
            "/register İsim Soyisim"
        )
        return

    if len(full_name) > 150:
        await message.answer(
            "İsim ve soyisim toplamda 150 karakteri aşamaz."
        )
        return

    try:

        request, state = await create_registration_request(
            telegram_user_id=message.from_user.id,
            telegram_chat_id=message.chat.id,
            full_name=full_name,
        )

        if state == "already_registered":

            await message.answer(
                "Bu Telegram hesabı zaten kayıtlı ve aktif."
            )
            return

        if request is None:
            await message.answer(
                "Kayıt talebi oluşturulamadı."
            )
            return

        if request.notification_sent_at is None:

            username = (
                f"@{message.from_user.username}"
                if message.from_user.username
                else "Belirtilmedi"
            )

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Onayla",
                            callback_data=f"reg:approve:{request.id}"
                        ),
                        InlineKeyboardButton(
                            text="Reddet",
                            callback_data=f"reg:reject:{request.id}"
                        )
                    ]
                ]
            )

            admin_message = (
                "YENİ ÇALIŞAN KAYIT TALEBİ\n\n"
                f"Başvuru No: #{request.id}\n"
                f"Ad Soyad: {request.requested_full_name}\n"
                f"Telegram ID: {request.telegram_user_id}\n"
                f"Kullanıcı adı: {username}\n\n"
                "Bu kişinin sisteme katılmasını onaylıyor musunuz?"
            )

            try:

                await message.bot.send_message(
                    chat_id=ADMIN_TELEGRAM_ID,
                    text=admin_message,
                    reply_markup=keyboard
                )

                await mark_registration_notified(request.id)

            except Exception:

                logging.exception(
                    "Could not notify administrator about registration."
                )

                await message.answer(
                    "Kayıt talebin oluşturuldu ancak yöneticiye "
                    "bildirim gönderilemedi.\n\n"
                    "Lütfen daha sonra /register komutunu tekrar dene."
                )
                return

            await message.answer(
                "Kayıt talebin yöneticiye gönderildi!\n\n"
                "Yönetici onayını bekliyorsun. "
                "Onaylandığında sana Telegram üzerinden "
                "bilgi vereceğiz."
            )

        else:

            await message.answer(
                "Kayıt talebin zaten beklemede. ⏳\n\n"
                "Yönetici onayını beklemelisin."
            )

    except Exception:

        logging.exception("Registration request failed.")

        await message.answer(
            "Kayıt talebi oluşturulurken bir hata oluştu."
        )


# ==========================================
# ADMIN REGISTRATION DECISION
# ==========================================

@dp.callback_query(F.data.startswith("reg:"))
async def registration_decision_handler(
    callback: CallbackQuery
):

    # Verify administrator identity.
    # Never trust the callback button alone.

    if (
        ADMIN_TELEGRAM_ID is None
        or callback.from_user.id != ADMIN_TELEGRAM_ID
    ):

        await callback.answer(
            "Bu işlem için yetkiniz yok.",
            show_alert=True
        )
        return

    try:

        parts = (callback.data or "").split(":")

        if len(parts) != 3:
            await callback.answer(
                "Geçersiz işlem.",
                show_alert=True
            )
            return

        action = parts[1]

        try:
            request_id = int(parts[2])
        except ValueError:
            await callback.answer(
                "Geçersiz başvuru numarası.",
                show_alert=True
            )
            return

        if action not in ("approve", "reject"):
            await callback.answer(
                "Geçersiz işlem.",
                show_alert=True
            )
            return

        request, employee, state = await review_registration_request(
            request_id=request_id,
            admin_telegram_user_id=callback.from_user.id,
            approve=(action == "approve"),
        )

        if state == "not_found":

            await callback.answer(
                "Başvuru bulunamadı.",
                show_alert=True
            )
            return

        if state == "already_reviewed":

            await callback.answer(
                "Bu başvuru daha önce değerlendirilmiş.",
                show_alert=True
            )
            return

        if state == "approved":

            admin_text = (
                f"Başvuru #{request.id} ONAYLANDI.\n\n"
                f"Çalışan: {employee.full_name}\n"
                f"Çalışan ID: {employee.id}"
            )

            applicant_text = (
                "Kayıt talebin onaylandı!\n\n"
                f"Çalışan: {employee.full_name}\n"
                f"Çalışan ID: {employee.id}\n"
                "Hesap durumu: Aktif\n\n"
                "Artık iş güncellemelerini bot üzerinden gönderebilirsin."
            )

        else:

            admin_text = (
                f"Başvuru #{request.id} REDDEDİLDİ.\n\n"
                f"Başvuran: {request.requested_full_name}"
            )

            applicant_text = (
                "Kayıt talebin maalesef reddedildi.\n\n"
                "Daha fazla bilgi için sistem yöneticisiyle "
                "iletişime geçebilirsin."
            )

        # Remove the decision buttons from the admin message.

        if callback.message is not None:

            try:

                await callback.bot.edit_message_text(
                    chat_id=ADMIN_TELEGRAM_ID,
                    message_id=callback.message.message_id,
                    text=admin_text,
                )

            except Exception:

                logging.exception(
                    "Could not update administrator notification."
                )

        # Notify the applicant about the decision.

        try:

            await callback.bot.send_message(
                chat_id=request.telegram_chat_id,
                text=applicant_text,
            )

        except Exception:

            logging.exception(
                "Could not notify applicant about registration decision."
            )

        await callback.answer(
            "İşlem başarıyla tamamlandı."
        )

    except Exception:

        logging.exception(
            "Registration decision failed."
        )

        await callback.answer(
            "İşlem sırasında bir hata oluştu.",
            show_alert=True
        )


# Employee text reporting handlers are registered after the existing
# registration handlers so commands and callbacks keep priority over the
# general F.text handler.

register_report_handlers(dp)


async def main():

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    extractor = WorkUpdateExtractor(
        api_key=GEMINI_API_KEY,
        model=GEMINI_MODEL
    )

    set_extractor(extractor)

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