import asyncio
import logging
import json
import os
import random
import string
import re
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# --- НАСТРОЙКИ ---
BOT_TOKEN = "9264454314:AAGu6P1Xp0_zJvWLh_NhpKM0mrGr6x93uRE"
MAIN_ADMIN_ID = 8941873700
SETTINGS_FILE = "settings.json"
DEALS_FILE = "deals.json"
USERS_FILE = "users.json"
BALANCES_FILE = "balances.json"
WITHDRAW_FILE = "withdraw_requests.json"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

LINK_PORTALS = "https://t.me/portals?startapp="
LINK_SUPPORT = "https://t.me/Portalldeal"
LINK_GIFTS = "https://t.me/GiftsforPortall" # Сюда кидает продавца при передаче

# --- ТЕКСТЫ ---
DEFAULT_TEXTS = {
    "welcome": "<b>Portals Guarant - #1 По трейдингу NFT подарков.</b>\n\nПокупайте и продавайте всё, что угодно — безопасно.\n\n👇 <b>Выберите раздел:</b>",
    "choose_method": "<b>Выберите метод оплаты:</b>",
    "amount_wallet": "<b>Введите сумму сделки в USDT или TON.</b>\n\nПример: 10.5 USDT или 4 TON",
    "amount_card": "<b>Введите сумму сделки в RUB или UAH.</b>\n\nПример: 1000 RUB или 500 UAH",
    "amount_stars": "<b>Введите сумму сделки в Stars.</b>\n\nПример: 150 Stars",
    "prompt_ton": "Введите адрес вашего TON кошелька:",
    "prompt_usdt": "Введите адрес вашего USDT кошелька:",
    "prompt_card": "Введите номер карты для получения:",
    "prompt_stars": "Введите свой @username для получения звезд:",
    "enter_nft": "<b>Ссылка на NFT</b>\n\nОтправьте ссылку (t.me/nft/...):",
    "deal_success": "<b>Сделка успешно создана!</b>\n\nНомер: <code>{deal_id}</code>\nСумма: {amount}\n\nРеквизиты: {details}\nПодарок: {nft_link}\n\nСсылка для покупателя:\n{deal_link}",
    "deal_offer": "<b>Вам предложена сделка!</b>\n\nНомер: <code>{deal_id}</code>\nСумма: {amount}\n\n<b>Реквизиты:</b>\n<code>{details}</code>\n\nПереведите сумму и нажмите кнопку.",
    
    # Тексты для статусов
    "buyer_paid": "<b>Вы оплатили сделку!</b>\n\nОжидайте передачу подарка менеджеру.\n\nВ случае не передачи подарка будет сделан возврат средств.",
    "seller_paid_notify": "<b>Покупатель оплатил сделку {deal_id}!</b>\n\nПередайте подарок менеджеру <b>@GiftsforPortall</b> для получения оплаты.",
    "seller_wait_confirm": "<b>Вы передали подарок!</b>\n\nОжидайте подтверждение от менеджера.",
    "seller_final_success": "<b>Сделка {deal_id} успешно завершена!</b>\n\nСредства зачислены на ваш баланс.",
    
    "buyer_final_success": "<b>Сделка {deal_id} успешно завершена!</b>\n\nСпасибо за использование нашего сервиса!",
    "seller_rejected": "<b>Сделка {deal_id} отклонена!</b>\n\nПодарок не был передан менеджеру. Средства возвращены покупателю.",
    "buyer_refunded": "<b>Сделка {deal_id} отклонена!</b>\n\nСредства возвращены на ваш счет.",
    
    "wallet_text": "<b>Ваш кошелек</b>\n\nБаланс: {balance}\n\nВ сделках: {in_deals}",
    "withdraw_amount": "Введите сумму для вывода (например: 10 USDT):",
    "withdraw_details": "Введите ваши реквизиты (кошелек или карту):",
    "withdraw_error_amount": "Недостаточно средств или неверный формат.",
    "withdraw_error_details": "Неверный формат реквизитов! Проверьте адрес/карту.",
    "withdraw_success": "✅ Заявка на вывод {amount} создана! Ожидайте выплаты от администратора.",
    "admin_new_deal": "<b>Новая сделка создана!</b>\n\nНомер: <code>{deal_id}</code>\nСумма: {amount}\n\n👤 Продавец: @{seller}\n👤 Покупатель: @{buyer}\n\nРеквизиты: <code>{details}</code>",
    "admin_delivered": "<b>Продавец передал подарок {deal_id}!</b>\n\nПроверьте поступление и выберите действие.",
}

BTN_TEXTS = {
    "btn_create": "Создать сделку", "btn_wallet": "Кошелек", "btn_my_deals": "Мои сделки",
    "btn_market": "Portals Market", "btn_lang": "Язык", "btn_support": "Поддержка",
    "btn_back": "Назад", "btn_main": "В главное меню", "btn_pay": "Я оплатил",
    "btn_delivered": "Передать NFT", "btn_admin_confirm": "Подтвердить получение",
    "btn_admin_reject": "Отклонить сделку", "btn_withdraw": "Вывести средства",
    "method_wallet": "Кошелек (USDT, TON)", "method_card": "Карта (RUB, UAH)", "method_stars": "Звезды (Stars)"
}

class DealStates(StatesGroup):
    entering_amount = State()
    entering_details = State()
    entering_nft_link = State()
    entering_withdraw_amount = State()
    entering_withdraw_details = State()

class AdminStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_media = State()

def get_json(filename, default):
    if not os.path.exists(filename): return default
    with open(filename, "r", encoding="utf-8") as f: return json.load(f)

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

def get_settings(): return get_json(SETTINGS_FILE, {"texts": {}, "images": {}, "entities": {}, "admins": []})
def save_settings(d): save_json(SETTINGS_FILE, d)

def get_balances(): return get_json(BALANCES_FILE, {})
def save_balances(b): save_json(BALANCES_FILE, b)

def add_balance(user_id, currency, amount):
    b = get_balances()
    uid = str(user_id)
    if uid not in b: b[uid] = {}
    if currency not in b[uid]: b[uid][currency] = 0.0
    b[uid][currency] += amount
    save_json(BALANCES_FILE, b)

def deduct_balance(user_id, currency, amount):
    b = get_balances()
    uid = str(user_id)
    if uid in b and currency in b[uid] and b[uid][currency] >= amount:
        b[uid][currency] -= amount
        save_json(BALANCES_FILE, b)
        return True
    return False

def is_admin(uid): return uid == MAIN_ADMIN_ID or uid in get_settings().get("admins", [])
def get_deals(): return get_json(DEALS_FILE, [])
def save_deals(d): save_json(DEALS_FILE, d)
def generate_deal_id(): return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(7))

def find_deal(did):
    for d in get_deals():
        if d["deal_id"] == did: return d
    return None

def update_deal(did, updates):
    deals = get_deals()
    for d in deals:
        if d["deal_id"] == did:
            d.update(updates)
            break
    save_deals(deals)

async def send_screen(chat_id, text_key, reply_markup, edit_message=None, **kwargs):
    settings = get_settings()
    raw_text = settings.get("texts", {}).get(text_key, DEFAULT_TEXTS.get(text_key, "Текст не задан"))
    text = raw_text.format(**kwargs) if kwargs else raw_text
    
    photo = settings.get("images", {}).get(text_key)
    entities = settings.get("entities", {}).get(text_key)

    if edit_message:
        try: await edit_message.delete()
        except: pass

    if photo:
        try:
            if entities: await bot.send_photo(chat_id=chat_id, photo=photo, caption=text, caption_entities=entities, reply_markup=reply_markup)
            else: await bot.send_photo(chat_id=chat_id, photo=photo, caption=text, parse_mode="HTML", reply_markup=reply_markup)
            return 
        except Exception as e:
            logging.error(f"Ошибка картинки {text_key}: {e}")
            del settings["images"][text_key]
            save_settings(settings)

    if entities: await bot.send_message(chat_id=chat_id, text=text, entities=entities, reply_markup=reply_markup)
    else: await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=reply_markup)

def get_main_keyboard(uid):
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=BTN_TEXTS["btn_create"], callback_data="create_deal"))
    b.row(InlineKeyboardButton(text=BTN_TEXTS["btn_wallet"], callback_data="wallet"), InlineKeyboardButton(text=BTN_TEXTS["btn_my_deals"], callback_data="my_deals"))
    b.row(InlineKeyboardButton(text=BTN_TEXTS["btn_market"], url=LINK_PORTALS))
    b.row(InlineKeyboardButton(text=BTN_TEXTS["btn_lang"], callback_data="language_menu"))
    b.row(InlineKeyboardButton(text=BTN_TEXTS["btn_support"], url=LINK_SUPPORT))
    if is_admin(uid): b.row(InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel"))
    return b.as_markup()

def get_methods_keyboard():
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=BTN_TEXTS["method_wallet"], callback_data="method_wallet"))
    b.row(InlineKeyboardButton(text=BTN_TEXTS["method_card"], callback_data="method_card"))
    b.row(InlineKeyboardButton(text=BTN_TEXTS["method_stars"], callback_data="method_stars"))
    b.row(InlineKeyboardButton(text=BTN_TEXTS["btn_back"], callback_data="back_to_main"))
    return b.as_markup()

# --- СТАРТ И ОСНОВНЫЕ ОБРАБОТЧИКИ ---
@dp.message(CommandStart(deep_link=True))
async def cmd_start_deep_link(message: types.Message, command: CommandObject, state: FSMContext):
    await state.clear()
    if command.args:
        deal = find_deal(command.args)
        if deal and deal["status"] == "Ожидает оплаты":
            update_deal(command.args, {"buyer_id": message.from_user.id, "buyer_username": message.from_user.username or "Нет"})
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=BTN_TEXTS["btn_pay"], callback_data=f"pay_{deal['deal_id']}")], [InlineKeyboardButton(text=BTN_TEXTS["btn_main"], callback_data="back_to_main")]])
            await send_screen(message.chat.id, "deal_offer", kb, deal_id=deal['deal_id'], amount=deal['amount'], details=deal['details'])
            return
    await send_screen(message.chat.id, "welcome", get_main_keyboard(message.from_user.id))

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await send_screen(message.chat.id, "welcome", get_main_keyboard(message.from_user.id))

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await send_screen(callback.message.chat.id, "welcome", get_main_keyboard(callback.from_user.id), edit_message=callback.message)
    await callback.answer()

# --- СОЗДАНИЕ СДЕЛКИ ---
@dp.callback_query(F.data == "create_deal")
async def start_deal(callback: types.CallbackQuery, state: FSMContext):
    await state.clear() 
    await send_screen(callback.message.chat.id, "choose_method", get_methods_keyboard(), edit_message=callback.message)
    await callback.answer()

@dp.callback_query(F.data.in_({"method_wallet", "method_card", "method_stars"}))
async def choose_method(callback: types.CallbackQuery, state: FSMContext):
    method = callback.data.replace("method_", "")
    await state.update_data(method=method)
    text_key = "amount_wallet" if method == "wallet" else "amount_card" if method == "card" else "amount_stars"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=BTN_TEXTS["btn_back"], callback_data="create_deal")]])
    await send_screen(callback.message.chat.id, text_key, kb, edit_message=callback.message)
    await state.set_state(DealStates.entering_amount)
    await callback.answer()

def parse_amount(text, method):
    text = text.lower().replace(",", ".")
    match = re.search(r'([\d\.]+)\s*([a-zа-яё$]*)?', text)
    if not match: return None, None
    try: amount = float(match.group(1))
    except: return None, None
    c = match.group(2) if match.group(2) else ""
    if method == "wallet":
        if "ton" in c: return amount, "TON"
        elif "usdt" in c or "$" in c or not c: return amount, "USDT"
    elif method == "card":
        if "rub" in c or "р" in c or not c: return amount, "RUB"
        elif "uah" in c or "грн" in c: return amount, "UAH"
    elif method == "stars":
        if "star" in c or "звезд" in c or "зір" in c or not c: return amount, "Stars"
    return None, None

@dp.message(DealStates.entering_amount)
async def process_amount(message: types.Message, state: FSMContext):
    data = await state.get_data()
    method = data.get("method")
    amount, currency = parse_amount(message.text, method)
    if amount is None: return await message.answer("Ошибка. Введите корректную сумму.")
    await state.update_data(amount=amount, currency=currency)
    
    prompt_key = "prompt_ton" if currency=="TON" else "prompt_usdt" if currency=="USDT" else "prompt_card" if currency in ["RUB","UAH"] else "prompt_stars"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=BTN_TEXTS["btn_back"], callback_data="create_deal")]])
    await send_screen(message.chat.id, prompt_key, kb)
    await state.set_state(DealStates.entering_details)

# --- ПРОВЕРКА РЕКВИЗИТОВ (ВАЛИДАЦИЯ) ---
@dp.message(DealStates.entering_details)
async def process_details(message: types.Message, state: FSMContext):
    data = await state.get_data()
    currency = data.get("currency")
    details = message.text.strip()
    
    valid = False
    error_msg = ""

    if currency == "USDT":
        # USDT (TRC20): начинается с 'T', 34 символа
        if re.match(r'^T[a-zA-Z0-9]{33}$', details): valid = True
        else: error_msg = "❌ Неверный адрес USDT (TRC20).\n\nАдрес должен начинаться с 'T' и содержать 34 символа."
    elif currency == "TON":
        # TON: начинается с 'EQ' или 'UQ', 48 символов
        if re.match(r'^(EQ|UQ)[a-zA-Z0-9_-]{46}$', details): valid = True
        else: error_msg = "❌ Неверный адрес TON.\n\nАдрес должен начинаться с 'EQ' или 'UQ' и содержать 48 символов."
    elif currency in ["RUB", "UAH"]:
        # Карта: 16-19 цифр без пробелов
        if re.match(r'^\d{16,19}$', details): valid = True
        else: error_msg = "❌ Неверный номер карты.\n\nВведите 16-19 цифр без пробелов."
    elif currency == "Stars":
        # Юзернейм: начинается с @, от 4 до 32 символов
        if re.match(r'^@[a-zA-Z0-9_]{4,32}$', details): valid = True
        else: error_msg = "❌ Неверный юзернейм.\n\nОн должен начинаться с '@' (например, @username)."

    if not valid:
        return await message.answer(error_msg)

    await state.update_data(details=details)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=BTN_TEXTS["btn_back"], callback_data="create_deal")]])
    await send_screen(message.chat.id, "enter_nft", kb)
    await state.set_state(DealStates.entering_nft_link)

@dp.message(DealStates.entering_nft_link)
async def process_nft_link(message: types.Message, state: FSMContext):
    if "t.me/nft/" not in message.text: return await message.answer("Отправьте корректную ссылку (t.me/nft/...).")
    data = await state.get_data()
    did = generate_deal_id()
    bot_info = await bot.get_me()
    deal_link = f"https://t.me/{bot_info.username}?start={did}"
    amount_str = f"{data['amount']} {data['currency']}"
    
    deal_data = {
        "deal_id": did, "user_id": message.from_user.id, "user_name": message.from_user.full_name,
        "seller_username": message.from_user.username or "Нет",
        "amount": amount_str, "currency": data["currency"], "details": data["details"],
        "nft_link": message.text, "status": "Ожидает оплаты", "date": datetime.now().strftime("%Y-%m-%d %H:%M"), 
        "buyer_id": None, "buyer_username": "Неизвестно"
    }
    deals = get_deals()
    deals.append(deal_data)
    save_deals(deals)
    await state.clear()
    
    await send_screen(message.chat.id, "deal_success", InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=BTN_TEXTS["btn_main"], callback_data="back_to_main")]]), deal_id=did, amount=amount_str, details=data["details"], nft_link=message.text, deal_link=deal_link)
    
    try:
        admin_text = DEFAULT_TEXTS["admin_new_deal"].format(deal_id=did, amount=amount_str, seller=deal_data['seller_username'], buyer="Ожидает...", details=data['details'])
        await bot.send_message(MAIN_ADMIN_ID, admin_text, parse_mode="HTML")
    except: pass

# --- ОПЛАТА И ПЕРЕДАЧА ---
@dp.callback_query(F.data.startswith("pay_") & ~F.data.in_({"pay_wallet", "pay_card", "pay_stars"}))
async def process_payment(callback: types.CallbackQuery):
    did = callback.data.replace("pay_", "")
    deal = find_deal(did)
    if not deal or deal["status"] != "Ожидает оплаты": return await callback.answer("Сделка не найдена или оплачена!")
    
    update_deal(did, {"status": "Оплачено", "buyer_id": callback.from_user.id, "buyer_username": callback.from_user.username or "Нет"})
    
    await send_screen(callback.message.chat.id, "buyer_paid", InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=BTN_TEXTS["btn_main"], callback_data="back_to_main")]]), edit_message=callback.message)
    
    kb_seller = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BTN_TEXTS["btn_delivered"], url=LINK_GIFTS)],
        [InlineKeyboardButton(text="✅ Я передал(а) NFT", callback_data=f"delivered_{did}")]
    ])
    try:
        seller_text = DEFAULT_TEXTS["seller_paid_notify"].format(deal_id=did)
        await bot.send_message(deal["user_id"], seller_text, reply_markup=kb_seller, parse_mode="HTML")
    except: pass
    
    try:
        admin_text = f"<b>Сделка {did} оплачена!</b>\n\n👤 Продавец: @{deal['seller_username']}\n👤 Покупатель: @{callback.from_user.username or 'Нет'}"
        await bot.send_message(MAIN_ADMIN_ID, admin_text, parse_mode="HTML")
    except: pass
    
    await callback.answer()

@dp.callback_query(F.data.startswith("delivered_"))
async def process_delivered(callback: types.CallbackQuery):
    did = callback.data.replace("delivered_", "")
    deal = find_deal(did)
    if not deal: return await callback.answer("Сделка не найдена.")
    update_deal(did, {"status": "На проверке"})
    
    await send_screen(callback.message.chat.id, "seller_wait_confirm", InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=BTN_TEXTS["btn_main"], callback_data="back_to_main")]]), edit_message=callback.message)
    
    kb_admin = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BTN_TEXTS["btn_admin_confirm"], callback_data=f"admin_confirm_{did}")],
        [InlineKeyboardButton(text=BTN_TEXTS["btn_admin_reject"], callback_data=f"admin_reject_{did}")]
    ])
    try: await bot.send_message(MAIN_ADMIN_ID, f"<b>Продавец подтвердил передачу подарка {did}!</b>\n\nПроверьте поступление.", reply_markup=kb_admin, parse_mode="HTML")
    except: pass

@dp.callback_query(F.data.startswith("admin_confirm_"))
async def admin_confirm(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    did = callback.data.replace("admin_confirm_", "")
    deal = find_deal(did)
    if not deal or deal["status"] != "На проверке": return
    update_deal(did, {"status": "Завершено"})
    
    add_balance(deal["user_id"], deal["currency"], float(deal["amount"].split()[0]))
    
    await callback.message.edit_text(f"✅ Сделка {did} успешно подтверждена. Средства начислены.")
    try: await bot.send_message(deal["user_id"], DEFAULT_TEXTS["seller_final_success"].format(deal_id=did), parse_mode="HTML")
    except: pass
    if deal.get("buyer_id"):
        try: await bot.send_message(deal["buyer_id"], DEFAULT_TEXTS["buyer_final_success"].format(deal_id=did), parse_mode="HTML")
        except: pass

@dp.callback_query(F.data.startswith("admin_reject_"))
async def admin_reject(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    did = callback.data.replace("admin_reject_", "")
    deal = find_deal(did)
    if not deal or deal["status"] != "На проверке": return
    update_deal(did, {"status": "Отклонено"})
    
    await callback.message.edit_text(f"❌ Сделка {did} отклонена.")
    try: await bot.send_message(deal["user_id"], DEFAULT_TEXTS["seller_rejected"].format(deal_id=did), parse_mode="HTML")
    except: pass
    if deal.get("buyer_id"):
        try: await bot.send_message(deal["buyer_id"], DEFAULT_TEXTS["buyer_refunded"].format(deal_id=did), parse_mode="HTML")
        except: pass

# --- ВЫВОД СРЕДСТВ ---
@dp.callback_query(F.data == "wallet")
async def wallet_menu(callback: types.CallbackQuery):
    uid = callback.from_user.id
    bal = get_balances().get(str(uid), {})
    bal_str = ", ".join([f"{v:.2f} {k}" for k, v in bal.items()]) if bal else "0.00"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=BTN_TEXTS["btn_withdraw"], callback_data="withdraw_money")], [InlineKeyboardButton(text=BTN_TEXTS["btn_main"], callback_data="back_to_main")]])
    await send_screen(callback.message.chat.id, "wallet_text", kb, edit_message=callback.message, balance=bal_str, in_deals="0.00")

@dp.callback_query(F.data == "withdraw_money")
async def start_withdraw(callback: types.CallbackQuery, state: FSMContext):
    bal = get_balances().get(str(callback.from_user.id), {})
    if not bal: return await callback.answer("У вас нет средств.", show_alert=True)
    await callback.message.edit_text(DEFAULT_TEXTS["withdraw_amount"])
    await state.set_state(DealStates.entering_withdraw_amount)
    await callback.answer()

@dp.message(DealStates.entering_withdraw_amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    text = message.text.lower().replace(",", ".")
    match = re.search(r'([\d\.]+)\s*([a-zа-яё]*)?', text)
    if not match: return await message.answer(DEFAULT_TEXTS["withdraw_error_amount"])
    
    amount = float(match.group(1))
    currency = match.group(2).upper() if match.group(2) else "USDT"
    
    bal = get_balances().get(str(uid), {})
    if currency not in bal or bal[currency] < amount:
        return await message.answer(DEFAULT_TEXTS["withdraw_error_amount"])
        
    await state.update_data(amount=amount, currency=currency)
    await message.answer(DEFAULT_TEXTS["withdraw_details"])
    await state.set_state(DealStates.entering_withdraw_details)

@dp.message(DealStates.entering_withdraw_details)
async def process_withdraw_details(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    details = message.text.strip()
    data = await state.get_data()
    currency = data['currency']
    amount = data['amount']
    
    valid = False
    if currency == "USDT":
        if re.match(r'^T[a-zA-Z0-9]{33}$', details): valid = True
    elif currency == "TON":
        if re.match(r'^(EQ|UQ)[a-zA-Z0-9_-]{46}$', details): valid = True
    elif currency in ["RUB", "UAH"]:
        if re.match(r'^\d{16,19}$', details): valid = True
    elif currency == "Stars":
        if details.startswith('@'): valid = True

    if not valid:
        return await message.answer(DEFAULT_TEXTS["withdraw_error_details"])
    
    if deduct_balance(uid, currency, amount):
        reqs = get_json(WITHDRAW_FILE, [])
        req_id = generate_deal_id()
        reqs.append({
            "req_id": req_id, "user_id": uid, "user_name": message.from_user.full_name, 
            "amount": f"{amount} {currency}", "details": details, "status": "Ожидает выплаты"
        })
        save_json(WITHDRAW_FILE, reqs)
        
        await message.answer(DEFAULT_TEXTS["withdraw_success"].format(amount=f"{amount} {currency}"), reply_markup=get_main_keyboard(uid))
        
        admin_text = f"<b>🔔 Новая заявка на вывод!</b>\n\nПользователь: {message.from_user.full_name} (@{message.from_user.username})\nСумма: {amount} {currency}\nРеквизиты: <code>{details}</code>"
        kb_admin = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Выплачено", callback_data=f"admin_payout_{req_id}")], [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_withdraw_{req_id}")]])
        try: await bot.send_message(MAIN_ADMIN_ID, admin_text, reply_markup=kb_admin, parse_mode="HTML")
        except: pass
    
    await state.clear()

@dp.callback_query(F.data.startswith("admin_payout_") | F.data.startswith("admin_reject_withdraw_"))
async def process_admin_withdraw(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return await callback.answer("Нет доступа.", show_alert=True)
    action = "payout" if "payout" in callback.data else "reject"
    req_id = callback.data.split("_")[-1]
    
    reqs = get_json(WITHDRAW_FILE, [])
    for r in reqs:
        if r["req_id"] == req_id and r["status"] == "Ожидает выплаты":
            if action == "payout":
                r["status"] = "Выплачено"; save_json(WITHDRAW_FILE, reqs)
                await callback.message.edit_text(f"✅ Заявка {req_id} выплачена.")
                try: await bot.send_message(r["user_id"], f"✅ Ваша заявка на вывод {r['amount']} одобрена и выплачена!")
                except: pass
            else:
                r["status"] = "Отклонено"; save_json(WITHDRAW_FILE, reqs)
                amt_str = r["amount"].split()
                add_balance(r["user_id"], amt_str[1], float(amt_str[0]))
                await callback.message.edit_text(f"❌ Заявка {req_id} отклонена. Средства возвращены.")
                try: await bot.send_message(r["user_id"], f"❌ Ваша заявка на вывод {r['amount']} отклонена. Средства возвращены на баланс.")
                except: pass
            return
    await callback.answer("Заявка уже обработана.", show_alert=True)

# --- АДМИН ПАНЕЛЬ ---
@dp.callback_query(F.data == "admin_panel")
async def admin_panel_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return await callback.answer("Нет доступа.")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="66. Вы оплатили сделку (Покупатель)", callback_data="edit_buyer_paid")],
        [InlineKeyboardButton(text="67. Покупатель оплатил (Продавцу)", callback_data="edit_seller_paid_notify")],
        [InlineKeyboardButton(text="68. Вы передали подарок (Продавцу)", callback_data="edit_seller_wait_confirm")],
        [InlineKeyboardButton(text="69. Сделка завершена (Продавцу)", callback_data="edit_seller_final_success")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")]
    ])
    await callback.message.edit_text("Выбери, что менять:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("edit_"))
async def admin_edit_screen(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    key = callback.data.replace("edit_", "")
    await state.update_data(key=key)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Изменить текст", callback_data="change_text")],
        [InlineKeyboardButton(text="🖼 Изменить картинку", callback_data="change_photo")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
    ])
    await callback.message.edit_text(f"Что меняем в экране <b>{key}</b>?", reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "change_text")
async def admin_change_text(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Отправь новый текст:")
    await state.set_state(AdminStates.waiting_for_text)
    await callback.answer()

@dp.message(AdminStates.waiting_for_text)
async def admin_save_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    key = data.get("key")
    settings = get_settings()
    settings["texts"][key] = message.html_text
    if message.entities:
        settings["entities"][key] = [e.model_dump() for e in message.entities]
    save_settings(settings)
    await message.answer("✅ Текст сохранен!")
    await state.clear()

@dp.callback_query(F.data == "change_photo")
async def admin_change_photo(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Отправь новую картинку:")
    await state.set_state(AdminStates.waiting_for_media)
    await callback.answer()

@dp.message(AdminStates.waiting_for_media)
async def admin_save_photo(message: types.Message, state: FSMContext):
    if not message.photo: return await message.answer("Это не фото.")
    data = await state.get_data()
    key = data.get("key")
    settings = get_settings()
    settings["images"][key] = message.photo[-1].file_id
    save_settings(settings)
    await message.answer("✅ Картинка сохранена!")
    await state.clear()

@dp.callback_query(F.data == "my_deals")
async def my_deals(callback: types.CallbackQuery):
    await callback.answer("Раздел в разработке.", show_alert=True)

@dp.callback_query(F.data == "language_menu")
async def language_menu(callback: types.CallbackQuery):
    await callback.answer("Только русский.", show_alert=True)

@dp.callback_query(F.data == "stub")
async def stub(callback: types.CallbackQuery):
    await callback.answer("В разработке", show_alert=True)

# --- ЗАПУСК ---
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
