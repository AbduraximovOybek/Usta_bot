import asyncio
import os

from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    KeyboardButton,
    ReplyKeyboardMarkup
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import BOT_TOKEN, ADMIN_ID
from database import (
    init_db,
    add_user,
    get_user,
    add_master,
    find_masters,
    create_order,
    get_master_by_telegram_id,
    get_statistics
)


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================
# KLAVIATURALAR
# =========================

def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔧 Usta bo‘laman"),
                KeyboardButton(text="🔎 Usta qidiraman")
            ],
            [
                KeyboardButton(text="📋 Buyurtma berish"),
                KeyboardButton(text="👤 Profil")
            ],
            [
                KeyboardButton(text="ℹ️ Yordam")
            ]
        ],
        resize_keyboard=True
    )


def master_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📋 Mening profilim"),
                KeyboardButton(text="📦 Buyurtmalar")
            ],
            [
                KeyboardButton(text="🏠 Bosh menyu")
            ]
        ],
        resize_keyboard=True
    )


# =========================
# STATES
# =========================

class MasterRegistration(StatesGroup):
    service = State()
    description = State()
    price = State()
    experience = State()
    phone = State()
    city = State()


class SearchMaster(StatesGroup):
    service = State()


class CreateOrder(StatesGroup):
    service = State()
    description = State()
    address = State()


# =========================
# START
# =========================

@dp.message(CommandStart())
async def start_handler(message: Message):
    add_user(
        telegram_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username
    )

    await message.answer(
        f"Assalomu alaykum, {message.from_user.full_name}! 👋\n\n"
        "🔧 Usta Botga xush kelibsiz!\n\n"
        "Bu bot orqali:\n"
        "• Usta sifatida ro‘yxatdan o‘tishingiz\n"
        "• Kerakli ustani topishingiz\n"
        "• Buyurtma berishingiz mumkin.",
        reply_markup=main_keyboard()
    )


# =========================
# USTA RO‘YXATDAN O‘TISH
# =========================

@dp.message(F.text == "🔧 Usta bo‘laman")
async def become_master(message: Message, state: FSMContext):
    await state.set_state(MasterRegistration.service)

    await message.answer(
        "🔧 Qaysi xizmatni ko‘rsatasiz?\n\n"
        "Masalan:\n"
        "Elektrik\n"
        "Santexnik\n"
        "Konditsioner ustasi\n"
        "Mebel ustasi"
    )


@dp.message(MasterRegistration.service)
async def master_service(message: Message, state: FSMContext):
    await state.update_data(service=message.text)

    await state.set_state(MasterRegistration.description)

    await message.answer(
        "📝 Xizmatingiz haqida qisqacha ma’lumot yozing."
    )


@dp.message(MasterRegistration.description)
async def master_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)

    await state.set_state(MasterRegistration.price)

    await message.answer(
        "💰 Xizmatingiz narxini yozing.\n\n"
        "Masalan: 50 000 so‘mdan"
    )


@dp.message(MasterRegistration.price)
async def master_price(message: Message, state: FSMContext):
    await state.update_data(price=message.text)

    await state.set_state(MasterRegistration.experience)

    await message.answer(
        "👨‍🔧 Necha yil tajribangiz bor?\n\n"
        "Masalan: 5"
    )


@dp.message(MasterRegistration.experience)
async def master_experience(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Iltimos, faqat raqam yozing. Masalan: 5")
        return

    await state.update_data(
        experience=int(message.text)
    )

    await state.set_state(MasterRegistration.phone)

    await message.answer(
        "📞 Telefon raqamingizni yuboring.\n\n"
        "Masalan: +998901234567"
    )


@dp.message(MasterRegistration.phone)
async def master_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)

    await state.set_state(MasterRegistration.city)

    await message.answer(
        "📍 Qaysi shahar/tumanda ishlaysiz?\n\n"
        "Masalan: Samarqand"
    )


@dp.message(MasterRegistration.city)
async def master_city(message: Message, state: FSMContext):
    data = await state.get_data()

    city = message.text

    add_user(
        telegram_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username,
        phone=data["phone"],
        role="master",
        city=city
    )

    add_master(
        telegram_id=message.from_user.id,
        service=data["service"],
        description=data["description"],
        price=data["price"],
        experience=data["experience"]
    )

    await state.clear()

    await message.answer(
        "✅ Tabriklaymiz!\n\n"
        "Siz Usta Botda usta sifatida ro‘yxatdan o‘tdingiz.",
        reply_markup=master_keyboard()
    )


# =========================
# USTA QIDIRISH
# =========================

@dp.message(F.text == "🔎 Usta qidiraman")
async def search_master_start(message: Message, state: FSMContext):
    await state.set_state(SearchMaster.service)

    await message.answer(
        "🔎 Qanday usta kerak?\n\n"
        "Masalan:\n"
        "• Elektrik\n"
        "• Santexnik\n"
        "• Konditsioner\n"
        "• Mebel"
    )


@dp.message(SearchMaster.service)
async def search_master(message: Message, state: FSMContext):
    service = message.text

    masters = find_masters(service)

    await state.clear()

    if not masters:
        await message.answer(
            "😔 Afsuski, bu xizmat bo‘yicha hozircha usta topilmadi."
        )
        return

    text = "🔎 Topilgan ustalar:\n\n"

    for index, master in enumerate(masters, start=1):
        text += (
            f"🔧 <b>{index}. {master['full_name']}</b>\n"
            f"🛠 Xizmat: {master['service']}\n"
            f"📍 Shahar: {master['city'] or 'Ko‘rsatilmagan'}\n"
            f"💰 Narx: {master['price']}\n"
            f"👨‍🔧 Tajriba: {master['experience']} yil\n"
            f"⭐ Reyting: {master['rating']}\n"
        )

        if master["phone"]:
            text += f"📞 Tel: {master['phone']}\n"

        text += "\n"

    await message.answer(
        text,
        parse_mode="HTML"
    )


# =========================
# BUYURTMA
# =========================

@dp.message(F.text == "📋 Buyurtma berish")
async def order_start(message: Message, state: FSMContext):
    await state.set_state(CreateOrder.service)

    await message.answer(
        "📋 Buyurtma yaratamiz.\n\n"
        "Qanday xizmat kerak?"
    )


@dp.message(CreateOrder.service)
async def order_service(message: Message, state: FSMContext):
    await state.update_data(service=message.text)

    await state.set_state(CreateOrder.description)

    await message.answer(
        "📝 Muammoni batafsil tushuntiring."
    )


@dp.message(CreateOrder.description)
async def order_description(message: Message, state: FSMContext):
    await state.update_data(
        description=message.text
    )

    await state.set_state(CreateOrder.address)

    await message.answer(
        "📍 Manzilingizni yozing."
    )


@dp.message(CreateOrder.address)
async def order_address(message: Message, state: FSMContext):
    data = await state.get_data()

    order_id = create_order(
        customer_telegram_id=message.from_user.id,
        service=data["service"],
        description=data["description"],
        address=message.text
    )

    await state.clear()

    if not order_id:
        await message.answer(
            "❌ Buyurtma yaratishda xatolik yuz berdi."
        )
        return

    await message.answer(
        f"✅ Buyurtmangiz qabul qilindi!\n\n"
        f"📋 Buyurtma №{order_id}\n"
        f"🛠 Xizmat: {data['service']}\n"
        f"📍 Manzil: {message.text}\n\n"
        "Ustalar buyurtmangizni ko‘rib chiqishadi."
    )


# =========================
# PROFIL
# =========================

@dp.message(F.text == "👤 Profil")
async def profile(message: Message):
    user = get_user(message.from_user.id)

    if not user:
        await message.answer(
            "Avval /start buyrug‘ini bosing."
        )
        return

    role = user["role"] or "Mijoz"

    await message.answer(
        "👤 <b>Sizning profilingiz</b>\n\n"
        f"👨 Ism: {user['full_name']}\n"
        f"📱 Username: @{user['username'] or 'yo‘q'}\n"
        f"📞 Telefon: {user['phone'] or 'yo‘q'}\n"
        f"👤 Rol: {role}\n"
        f"📍 Shahar: {user['city'] or 'yo‘q'}",
        parse_mode="HTML"
    )


# =========================
# USTA PROFILI
# =========================

@dp.message(F.text == "📋 Mening profilim")
async def master_profile(message: Message):
    master = get_master_by_telegram_id(
        message.from_user.id
    )

    if not master:
        await message.answer(
            "Siz hali usta sifatida ro‘yxatdan o‘tmagansiz."
        )
        return

    await message.answer(
        "🔧 <b>Usta profilingiz</b>\n\n"
        f"👨‍🔧 Ism: {master['full_name']}\n"
        f"🛠 Xizmat: {master['service']}\n"
        f"📝 {master['description']}\n"
        f"💰 Narx: {master['price']}\n"
        f"📍 Shahar: {master['city']}\n"
        f"👨‍🔧 Tajriba: {master['experience']} yil\n"
        f"⭐ Reyting: {master['rating']}",
        parse_mode="HTML"
    )


# =========================
# YORDAM
# =========================

@dp.message(F.text == "ℹ️ Yordam")
async def help_handler(message: Message):
    await message.answer(
        "ℹ️ <b>Usta Bot yordam</b>\n\n"
        "🔧 Usta bo‘lish — xizmatlaringizni botga joylashtiradi.\n"
        "🔎 Usta qidirish — kerakli mutaxassisni topadi.\n"
        "📋 Buyurtma berish — usta chaqirish uchun buyurtma yaratadi.\n"
        "👤 Profil — hisob ma’lumotlaringizni ko‘rsatadi.",
        parse_mode="HTML"
    )


# =========================
# ADMIN
# =========================

@dp.message(Command("admin"))
async def admin_handler(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Siz admin emassiz.")
        return

    stats = get_statistics()

    await message.answer(
        "👨‍💼 <b>ADMIN PANEL</b>\n\n"
        f"👥 Foydalanuvchilar: {stats['users']}\n"
        f"🔧 Ustalar: {stats['masters']}\n"
        f"📋 Buyurtmalar: {stats['orders']}\n"
        f"✅ Qabul qilingan: {stats['accepted_orders']}",
        parse_mode="HTML"
    )


# =========================
# BOSH MENYU
# =========================

@dp.message(F.text == "🏠 Bosh menyu")
async def home(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "🏠 Bosh menyu",
        reply_markup=main_keyboard()
    )


# =========================
# UNKNOWN
# =========================

@dp.message()
async def unknown(message: Message):
    await message.answer(
        "🤔 Bu buyruqni tushunmadim.\n\n"
        "Menyudan kerakli bo‘limni tanlang.",
        reply_markup=main_keyboard()
    )


# =========================
# LOCAL + RENDER
# =========================

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "10000"))

WEBHOOK_PATH = "/webhook"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "usta-bot-secret")

# Render o'zining RENDER_EXTERNAL_URL qiymatini beradi.
# Agar kerak bo'lsa WEBHOOK_URL ni ham qo'lda berish mumkin.
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not WEBHOOK_URL and RENDER_EXTERNAL_URL:
    WEBHOOK_URL = f"{RENDER_EXTERNAL_URL.rstrip('/')}{WEBHOOK_PATH}"


# =========================
# RENDER STARTUP
# =========================

async def on_startup(bot: Bot):
    init_db()

    if not WEBHOOK_URL:
        raise RuntimeError(
            "Render uchun RENDER_EXTERNAL_URL yoki WEBHOOK_URL topilmadi!"
        )

    await bot.set_webhook(
        url=WEBHOOK_URL,
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=True
    )

    print("🤖 Usta Bot ishga tushdi!")
    print(f"🌐 Webhook: {WEBHOOK_URL}")


# =========================
# RENDER SHUTDOWN
# =========================

async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    await bot.session.close()

    print("🛑 Usta Bot to‘xtadi.")


# =========================
# HEALTH CHECK
# =========================

async def health(request: web.Request):
    return web.Response(
        text="🤖 Usta Bot ishlayapti!"
    )


# =========================
# RENDER WEBHOOK
# =========================

def run_render():

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()

    # Render health check
    app.router.add_get(
        "/",
        health
    )

    # Telegram webhook
    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET
    )

    webhook_handler.register(
        app,
        path=WEBHOOK_PATH
    )

    setup_application(
        app,
        dp,
        bot=bot
    )

    print("☁️ RENDER rejimi")
    print(f"🌐 Port: {PORT}")

    web.run_app(
        app,
        host=HOST,
        port=PORT
    )


# =========================
# LOCAL POLLING
# =========================

async def run_local():

    init_db()

    # Lokal ishlaganda webhookni o‘chirib qo‘yamiz.
    # Shunda Telegram xabarlarni polling orqali yuboradi.
    await bot.delete_webhook(
        drop_pending_updates=True
    )

    print("💻 LOCAL rejimi")
    print("🤖 Usta Bot ishga tushdi!")
    print("📡 Polling ishlayapti...")
    print("Telegram'da /start bosing.")

    try:
        await dp.start_polling(
            bot
        )
    finally:
        await bot.session.close()


# =========================
# MAIN
# =========================

def main():

    # Render'da RENDER_EXTERNAL_URL mavjud bo‘ladi.
    # Lokal kompyuterda esa u bo‘lmaydi.
    if RENDER_EXTERNAL_URL or os.getenv("RENDER") == "true":

        run_render()

    else:

        asyncio.run(
            run_local()
        )


if __name__ == "__main__":
    main()
