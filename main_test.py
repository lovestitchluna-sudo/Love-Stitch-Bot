import json
import os
import time
from datetime import datetime, timedelta

import requests

from rubibot import RubiBot
from rubibot.types import (
    ChatKeypad,
    KeypadRow,
    KeypadSimpleButton
)


# =========================================================
# SETTINGS
# =========================================================

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = "u0KNMhm07ba2376f545d81e75453c8c9"

API_URL = f"https://botapi.rubika.ir/v3/{TOKEN}"

bot = RubiBot(TOKEN)

USERS_FILE = "users.json"
CODES_FILE = "codes.json"
OFFSET_FILE = "offset.json"

# طبق توافق: ۱۰ PT برای هر کشتن (نه هر آسیب). اگه می‌خوای عدد
# دیگه‌ای باشه، فقط همین رو عوض کن.
KILL_REWARD_PT = 10


# =========================================================
# JSON FUNCTIONS
# =========================================================

def load_json(filename, default):
    if not os.path.exists(filename):
        return default

    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        print(f"❌ خطا در خواندن {filename}:")
        print(e)
        return default


def save_json(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=4
            )

        return True

    except Exception as e:
        print(f"❌ خطا در ذخیره {filename}:")
        print(e)
        return False


# =========================================================
# USERS
# =========================================================

users = load_json(USERS_FILE, {})


def save_users():
    save_json(USERS_FILE, users)


# =========================================================
# CODES
# =========================================================

codes = load_json(CODES_FILE, {})


def save_codes():
    save_json(CODES_FILE, codes)


# =========================================================
# OFFSET
# =========================================================

def load_offset():
    if not os.path.exists(OFFSET_FILE):
        return None

    try:
        with open(OFFSET_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("offset_id")

    except Exception as e:
        print("❌ خطا در خواندن offset:")
        print(e)
        return None


def save_offset(offset_id):
    try:
        with open(OFFSET_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {"offset_id": offset_id},
                f,
                ensure_ascii=False,
                indent=4
            )

        print("💾 Offset ذخیره شد:", offset_id)

    except Exception as e:
        print("❌ خطا در ذخیره offset:")
        print(e)


offset_id = load_offset()

print("📌 Offset فعلی:", offset_id)


# =========================================================
# USER STATES
# =========================================================

user_states = {}


# =========================================================
# ADMIN STATES
# =========================================================

admin_states = {}


# =========================================================
# SHOP STORAGE
# =========================================================
# اینجا هیچ فایل جداگانه‌ای (مثل characters.json یا shop_settings.json)
# ساخته نمی‌شه. شخصیت‌ها و تنظیمات شاپ زیر دو کلید مخصوص، داخل همون
# دیکشنری users (و در نتیجه همون users.json) نگه داشته می‌شن.
# characters و shop_settings فقط اشاره (reference) به همون دیکشنری‌های
# داخل users هستن، پس هر تغییری روشون با save_users() ذخیره می‌شه.
#
# نکته: process_kill_log هر چرخه users رو از فایل دوباره می‌خونه
# (reload_users). چون اون کار دیکشنری‌های داخلی رو عوض می‌کنه،
# بعد از هر reload باید bind_shop_storage() دوباره صدا زده بشه تا
# characters و shop_settings به نسخهٔ جدید اشاره کنن.

CHAR_KEY = "_shop_characters"
SETTINGS_KEY = "_shop_settings"

characters = {}
shop_settings = {}


def bind_shop_storage():
    global characters, shop_settings

    if not isinstance(users.get(CHAR_KEY), dict):
        users[CHAR_KEY] = {}

    if not isinstance(users.get(SETTINGS_KEY), dict):
        users[SETTINGS_KEY] = {"characters_locked": False}

    characters = users[CHAR_KEY]
    shop_settings = users[SETTINGS_KEY]


bind_shop_storage()


def save_characters():
    save_users()


def save_settings():
    save_users()


def is_locked():
    return shop_settings.get("characters_locked", False)


# =========================================================
# NETWORK ERROR HELPER
# =========================================================
# قطعی موقت شبکه (مثلاً روشن/خاموش کردن وی‌پی‌ان) باعث میشه
# درخواست‌های requests با این نوع خطاها مواجه بشن. این تابع
# کمک می‌کنه توی لاگ‌ها بفهمیم خطا از جنس قطعی شبکه‌ست یا چیز دیگه.

NETWORK_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)


def is_network_error(e):
    return isinstance(e, NETWORK_ERRORS)


# =========================================================
# GET CHAT INFO
# =========================================================

def get_chat_info(chat_id):
    try:
        response = requests.post(
            f"{API_URL}/getChat",
            json={"chat_id": chat_id},
            timeout=15
        )

        try:
            result = response.json()

        except ValueError:
            # جواب سرور اصلاً JSON نبود (مثلاً خالی، یا یه صفحهٔ خطا).
            # این اطلاعات کمک می‌کنه بفهمیم دقیقاً چی برگشته.
            print("❌ جواب getChat قابل‌خواندن (JSON) نبود:")
            print("کد وضعیت HTTP:", response.status_code)
            print("متن خام جواب:", response.text[:300])
            return None

        if result.get("status") != "OK":
            print("❌ خطای getChat:")
            print(result)
            return None

        chat = result.get("data", {}).get("chat")

        if not chat:
            return None

        return chat

    except Exception as e:
        if is_network_error(e):
            print("📡 قطعی موقت شبکه در getChat (مثلاً تغییر وی‌پی‌ان):", e)
        else:
            print("❌ خطا در getChat:")
            print(e)
        return None


# =========================================================
# UPDATE USER INFO
# =========================================================

def update_user_info(chat_id, sender_id):

    chat = get_chat_info(chat_id)

    if not chat:
        return None

    user_id = str(sender_id)

    username = chat.get("username") or ""

    first_name = chat.get("first_name") or ""
    last_name = chat.get("last_name") or ""

    display_name = f"{first_name} {last_name}".strip()

    if user_id not in users:

        users[user_id] = {
            "id": user_id,
            "chat_id": chat_id,
            "username": username,
            "display_name": display_name,
            "pt": 0,
            "used_codes": [],
            "characters": [],
            "selected_character": None
        }

        print("👤 کاربر جدید ثبت شد:", user_id)

    else:

        users[user_id]["chat_id"] = chat_id
        users[user_id]["username"] = username
        users[user_id]["display_name"] = display_name

        if "pt" not in users[user_id]:
            users[user_id]["pt"] = 0

        if "used_codes" not in users[user_id]:
            users[user_id]["used_codes"] = []

        if "characters" not in users[user_id]:
            users[user_id]["characters"] = []

        if "selected_character" not in users[user_id]:
            users[user_id]["selected_character"] = None

    return user_id

# =========================================================
# SEND MESSAGE
# =========================================================

def send_message(chat_id, text, keypad=None):

    try:

        if keypad is not None:

            result = bot.send_message(
                chat_id,
                text,
                chat_keypad=keypad
            )

        else:

            result = bot.send_message(
                chat_id,
                text
            )

        print("📥 SEND RESULT:")
        print(result)

        return result

    except Exception as e:

        if is_network_error(e):
            print("📡 قطعی موقت شبکه در send_message (مثلاً تغییر وی‌پی‌ان):", e)
        else:
            print("❌ SEND MESSAGE ERROR:")
            print(e)

        return None


# =========================================================
# USER KEYBOARD
# =========================================================

def user_keyboard():

    row1 = KeypadRow().add(
        KeypadSimpleButton(
            "💰 موجودی",
            "balance"
        )
    )

    row2 = KeypadRow().add(
        KeypadSimpleButton(
            "🎁 کد جایزه",
            "gift"
        )
    )

    row3 = KeypadRow().add(
        KeypadSimpleButton(
            "🛒 شاپ",
            "shop"
        )
    )

    row4 = KeypadRow().add(
        KeypadSimpleButton(
            "ℹ️ راهنما",
            "help"
        )
    )

    return (
        ChatKeypad(resize_keyboard=True)
        .add(row1)
        .add(row2)
        .add(row3)
        .add(row4)
    )


# =========================================================
# ADMIN KEYBOARD
# =========================================================

def admin_keyboard():

    row1 = KeypadRow().add(
        KeypadSimpleButton(
            "👥 کاربران",
            "admin_users"
        )
    ).add(
        KeypadSimpleButton(
            "💰 مدیریت PT",
            "admin_pt"
        )
    )

    row2 = KeypadRow().add(
        KeypadSimpleButton(
            "📊 آمار",
            "admin_stats"
        )
    ).add(
        KeypadSimpleButton(
            "🎟 ساخت کد",
            "admin_newcode"
        )
    )

    row3 = KeypadRow().add(
        KeypadSimpleButton(
            "📋 کدها",
            "admin_codes"
        )
    ).add(
        KeypadSimpleButton(
            "❌ حذف کد",
            "admin_deletecode"
        )

    )

    row4 = KeypadRow().add(
        KeypadSimpleButton(
            "🎭 مدیریت شاپ",
            "shop_admin_menu"
        )
    )

    return (
        ChatKeypad(resize_keyboard=True)
        .add(row1)
        .add(row2)
        .add(row3)
        .add(row4)
    )


# =========================================================
# PT KEYBOARD
# =========================================================

def pt_action_keyboard():

    row = KeypadRow().add(
        KeypadSimpleButton(
            "➕ اضافه کردن PT",
            "pt_add"
        )
    ).add(
        KeypadSimpleButton(
            "➖ کم کردن PT",
            "pt_remove"
        )
    )

    return (
        ChatKeypad(resize_keyboard=True)
        .add(row)
    )


# =========================================================
# ADMIN USERS
# =========================================================

def show_users(chat_id):

    if not users:

        send_message(
            chat_id,
            "👥 هنوز هیچ کاربری ثبت نشده.",
            admin_keyboard()
        )

        return

    text = "👥 کاربران ربات:\n\n"

    for user_id, data in users.items():

        if user_id.startswith("_"):
            continue

        name = data.get(
            "display_name",
            "بدون نام"
        )

        username = data.get(
            "username",
            ""
        )

        pt = data.get(
            "pt",
            0
        )

        if username:
            username_text = f"@{username}"
        else:
            username_text = "بدون یوزرنیم"

        text += (
            f"👤 {name}\n"
            f"🔹 {username_text}\n"
            f"💰 {pt} PT\n\n"
        )

    send_message(
        chat_id,
        text,
        admin_keyboard()
    )


# =========================================================
# ADMIN STATS
# =========================================================

def show_stats(chat_id):

    # کلیدهای داخلی (_shop_characters / _shop_settings / _kill_log)
    # کاربر نیستن؛ _kill_log لیسته و .get نداره، پس ردشون می‌کنیم.
    total_users = 0

    total_pt = 0

    for user_id, data in users.items():

        if user_id.startswith("_") or not isinstance(data, dict):
            continue

        total_users += 1

        total_pt += data.get(
            "pt",
            0
        )

    total_codes = len(codes)

    send_message(
        chat_id,
        f"""📊 آمار ربات

👥 تعداد کاربران:
{total_users}

💰 مجموع PT کاربران:
{total_pt} PT

🎟 تعداد کدهای جایزه:
{total_codes}""",
        admin_keyboard()
    )


# =========================================================
# FIND USER BY USERNAME
# =========================================================

def find_user_by_username(username):

    username = username.strip()

    if username.startswith("@"):
        username = username[1:]

    username = username.lower()

    for user_id, data in users.items():

        if user_id.startswith("_") or not isinstance(data, dict):
            continue

        saved_username = data.get(
            "username",
            ""
        ).lower()

        if saved_username == username:
            return user_id

    return None


# =========================================================
# PT MANAGEMENT
# =========================================================

def start_pt_management(chat_id, admin_id):

    admin_states[admin_id] = {
        "state": "waiting_username"
    }

    send_message(
        chat_id,
        "💰 مدیریت PT\n\n"
        "یوزرنیم کاربر را بفرست.\n\n"
        "مثلاً:\n"
        "@username"
    )


# =========================================================
# HANDLE PT ADMIN STATE
# =========================================================

def handle_pt_state(
    chat_id,
    admin_id,
    text,
    button_id=None
):

    state_data = admin_states.get(
        admin_id
    )

    if not state_data:
        return False

    state = state_data.get(
        "state"
    )

    # -----------------------------------------------------
    # USERNAME
    # -----------------------------------------------------

    if state == "waiting_username":

        target_id = find_user_by_username(
            text
        )

        if not target_id:

            send_message(
                chat_id,
                "❌ کاربری با این یوزرنیم پیدا نشد.\n\n"
                "دوباره یوزرنیم را بفرست:"
            )

            return True

        target = users[target_id]

        admin_states[admin_id] = {
            "state": "choose_action",
            "target_id": target_id
        }

        username = target.get(
            "username",
            ""
        )

        name = target.get(
            "display_name",
            "بدون نام"
        )

        pt = target.get(
            "pt",
            0
        )

        send_message(
            chat_id,
            f"""👤 کاربر پیدا شد!

👤 نام:
{name}

🔹 یوزرنیم:
@{username}

💰 موجودی:
{pt} PT

یکی از عملیات زیر را انتخاب کن:""",
            pt_action_keyboard()
        )

        return True

    # -----------------------------------------------------
    # CHOOSE ACTION
    # -----------------------------------------------------

    if state == "choose_action":

        target_id = state_data.get(
            "target_id"
        )

        if (
            button_id == "pt_add"
            or text == "➕ اضافه کردن PT"
        ):

            admin_states[admin_id] = {
                "state": "waiting_amount",
                "target_id": target_id,
                "action": "add"
            }

            send_message(
                chat_id,
                "➕ مقدار PT برای اضافه کردن را بفرست.\n\n"
                "مثلاً:\n"
                "500"
            )

            return True

        if (
            button_id == "pt_remove"
            or text == "➖ کم کردن PT"
        ):

            admin_states[admin_id] = {
                "state": "waiting_amount",
                "target_id": target_id,
                "action": "remove"
            }

            send_message(
                chat_id,
                "➖ مقدار PT برای کم کردن را بفرست.\n\n"
                "مثلاً:\n"
                "500"
            )

            return True

        send_message(
            chat_id,
            "❌ شناسایی نشد!\n\n"
            "لطفاً یکی از دکمه‌های زیر را انتخاب کنید.",
            pt_action_keyboard()
        )

        return True

    # -----------------------------------------------------
    # AMOUNT
    # -----------------------------------------------------

    if state == "waiting_amount":

        try:

            amount = int(
                text.strip()
            )

        except ValueError:

            send_message(
                chat_id,
                "❌ مقدار باید فقط عدد باشد.\n\n"
                "مثلاً:\n"
                "500"
            )

            return True

        if amount <= 0:

            send_message(
                chat_id,
                "❌ مقدار باید بیشتر از صفر باشد."
            )

            return True

        target_id = state_data.get(
            "target_id"
        )

        action = state_data.get(
            "action"
        )

        if target_id not in users:

            admin_states.pop(
                admin_id,
                None
            )

            send_message(
                chat_id,
                "❌ کاربر دیگر پیدا نشد.",
                admin_keyboard()
            )

            return True

        current_pt = users[target_id].get(
            "pt",
            0
        )

        # -------------------------------------------------
        # ADD
        # -------------------------------------------------

        if action == "add":

            new_pt = current_pt + amount

            users[target_id]["pt"] = new_pt

            save_users()

            send_message(
                chat_id,
                "✅ واریز موفق بود!",
                admin_keyboard()
            )

            target_chat_id = users[target_id].get(
                "chat_id"
            )

            if target_chat_id:

                send_message(
                    target_chat_id,
                    f"""🥳 تبریک! 🎉

{amount} PT به حسابت واریز شد! 💰

💰 موجودی جدیدت: {new_pt} PT""",
                    user_keyboard()
                )

            else:

                print(
                    "⚠️ chat_id کاربر برای ارسال پیام پیدا نشد."
                )

            admin_states.pop(
                admin_id,
                None
            )

            return True

        # -------------------------------------------------
        # REMOVE
        # -------------------------------------------------

        if action == "remove":

            if amount > current_pt:

                send_message(
                    chat_id,
                    f"""❌ موجودی کاربر کافی نیست!

💰 موجودی فعلی:
{current_pt} PT

➖ مقدار درخواستی:
{amount} PT""",
                    admin_keyboard()
                )

                admin_states.pop(
                    admin_id,
                    None
                )

                return True

            new_pt = current_pt - amount

            users[target_id]["pt"] = new_pt

            save_users()

            send_message(
                chat_id,
                "✅ برداشت موفق بود!",
                admin_keyboard()
            )

            # کاربر در برداشت هیچ پیامی نمی‌گیرد

            admin_states.pop(
                admin_id,
                None
            )

            return True

    return False


# =========================================================
# REWARD CODE - EXPIRATION
# =========================================================

def is_code_expired(code_data):

    expires_at = code_data.get(
        "expires_at"
    )

    if not expires_at:
        return False

    try:

        expire_time = datetime.strptime(
            expires_at,
            "%Y-%m-%d %H:%M"
        )

        return datetime.now() >= expire_time

    except Exception as e:

        print(
            "❌ خطا در بررسی تاریخ کد:"
        )

        print(e)

        return True


# =========================================================
# CREATE EXPIRATION
# =========================================================

def make_expiration(hours):

    expire_time = (
        datetime.now()
        + timedelta(hours=hours)
    )

    return expire_time.strftime(
        "%Y-%m-%d %H:%M"
    )


# =========================================================
# CREATE REWARD CODE
# =========================================================

def create_reward_code(
    code,
    pt,
    hours
):

    code = code.strip()

    if not code:

        return False, "کد خالی است."

    if code in codes:

        return False, "این کد از قبل وجود دارد."

    if pt <= 0:

        return False, "مقدار PT باید بیشتر از صفر باشد."

    if hours <= 0:

        return False, "زمان انقضا باید بیشتر از صفر باشد."

    expires_at = make_expiration(
        hours
    )

    codes[code] = {
        "pt": pt,
        "expires_at": expires_at,
        "used_by": []
    }

    save_codes()

    return True, expires_at


# =========================================================
# USE REWARD CODE
# =========================================================

def use_reward_code(
    user_id,
    code
):

    code = code.strip()

    if not code:

        return False, "❌ کد خالی است."

    if code not in codes:

        return False, (
            "❌ این کد وجود ندارد "
            "یا اشتباه وارد شده."
        )

    code_data = codes[code]

    if is_code_expired(code_data):

        return False, "⏰ این کد منقضی شده است."

    used_by = code_data.get(
        "used_by",
        []
    )

    if user_id in used_by:

        return False, (
            "🚫 شما قبلاً از این کد "
            "استفاده کرده‌اید."
        )

    reward = int(
        code_data.get(
            "pt",
            0
        )
    )

    if reward <= 0:

        return False, (
            "❌ این کد جایزهٔ معتبری ندارد."
        )

    if user_id not in users:

        return False, (
            "❌ اطلاعات کاربر پیدا نشد."
        )

    old_pt = users[user_id].get(
        "pt",
        0
    )

    new_pt = old_pt + reward

    users[user_id]["pt"] = new_pt

    used_by.append(
        user_id
    )

    code_data["used_by"] = used_by

    # برای هماهنگی با ساختار users
    if "used_codes" not in users[user_id]:
        users[user_id]["used_codes"] = []

    if code not in users[user_id]["used_codes"]:
        users[user_id]["used_codes"].append(code)

    save_users()
    save_codes()

    return True, {
        "reward": reward,
        "new_pt": new_pt
    }


# =========================================================
# HANDLE USER REWARD CODE
# =========================================================

def handle_user_reward_code(
    chat_id,
    user_id,
    text
):

    result, data = use_reward_code(
        user_id,
        text
    )

    if not result:

        send_message(
            chat_id,
            data,
            user_keyboard()
        )

        return

    reward = data["reward"]
    new_pt = data["new_pt"]

    send_message(
        chat_id,
        f"""🥳 تبریک! 🎉

{reward} PT به حسابت نشست! 💰

💰 موجودی جدیدت: {new_pt} PT""",
        user_keyboard()
    )


# =========================================================
# SHOW CODES
# =========================================================

def show_codes(chat_id):

    if not codes:

        send_message(
            chat_id,
            "📋 هنوز هیچ کدی ساخته نشده.",
            admin_keyboard()
        )

        return

    text = "📋 کدهای جایزه:\n\n"

    for code, data in codes.items():

        pt = data.get(
            "pt",
            0
        )

        expires_at = data.get(
            "expires_at",
            "نامشخص"
        )

        used_count = len(
            data.get(
                "used_by",
                []
            )
        )

        text += (
            f"🎟 {code}\n"
            f"💰 جایزه: {pt} PT\n"
            f"⏰ انقضا: {expires_at}\n"
            f"👥 استفاده شده: {used_count} نفر\n\n"
        )

    send_message(
        chat_id,
        text,
        admin_keyboard()
    )


# =========================================================
# DELETE CODE
# =========================================================

def delete_code(
    chat_id,
    code
):

    code = code.strip()

    if code not in codes:

        send_message(
            chat_id,
            "❌ چنین کدی پیدا نشد.",
            admin_keyboard()
        )

        return

    del codes[code]

    save_codes()

    send_message(
        chat_id,
        f"✅ کد {code} با موفقیت حذف شد.",
        admin_keyboard()
    )


# =========================================================
# ADMIN CODE CREATION STATE
# =========================================================

def handle_admin_code_state(
    chat_id,
    admin_id,
    text
):

    state_data = admin_states.get(
        admin_id
    )

    if not state_data:
        return False

    state = state_data.get(
        "state"
    )

    # -----------------------------------------------------
    # CODE NAME
    # -----------------------------------------------------

    if state == "newcode_name":

        code = text.strip()

        if not code:

            send_message(
                chat_id,
                "❌ کد نمی‌تواند خالی باشد."
            )

            return True

        if code in codes:

            send_message(
                chat_id,
                "❌ این کد از قبل وجود دارد.\n\n"
                "یک کد دیگر بفرست:"
            )

            return True

        admin_states[admin_id] = {
            "state": "newcode_pt",
            "code": code
        }

        send_message(
            chat_id,
            f"""🎟 کد انتخاب شد:

{code}

💰 حالا مقدار PT جایزه را بفرست.

مثلاً:
500"""
        )

        return True

    # -----------------------------------------------------
    # PT
    # -----------------------------------------------------

    if state == "newcode_pt":

        try:

            pt = int(
                text.strip()
            )

        except ValueError:

            send_message(
                chat_id,
                "❌ مقدار PT باید فقط عدد باشد.\n\n"
                "مثلاً:\n500"
            )

            return True

        if pt <= 0:

            send_message(
                chat_id,
                "❌ مقدار PT باید بیشتر از صفر باشد."
            )

            return True

        admin_states[admin_id] = {
            "state": "newcode_hours",
            "code": state_data["code"],
            "pt": pt
        }

        send_message(
            chat_id,
            """⏰ کد چند ساعت اعتبار داشته باشد؟

مثلاً:
24

یعنی کد ۲۴ ساعت اعتبار دارد."""
        )

        return True

    # -----------------------------------------------------
    # HOURS
    # -----------------------------------------------------

    if state == "newcode_hours":

        try:

            hours = int(
                text.strip()
            )

        except ValueError:

            send_message(
                chat_id,
                "❌ زمان باید فقط عدد باشد.\n\n"
                "مثلاً:\n24"
            )

            return True

        if hours <= 0:

            send_message(
                chat_id,
                "❌ زمان انقضا باید بیشتر از صفر باشد."
            )

            return True

        code = state_data["code"]
        pt = state_data["pt"]

        success, result = create_reward_code(
            code,
            pt,
            hours
        )

        if not success:

            send_message(
                chat_id,
                f"❌ {result}",
                admin_keyboard()
            )

            admin_states.pop(
                admin_id,
                None
            )

            return True

        expires_at = result

        admin_states.pop(
            admin_id,
            None
        )

        send_message(
            chat_id,
            f"""✅ کد با موفقیت ساخته شد! 🎉

🎟 کد:
{code}

💰 جایزه:
{pt} PT

⏰ انقضا:
{expires_at}

♾️ ظرفیت:
نامحدود

👤 هر کاربر فقط یک‌بار می‌تواند از این کد استفاده کند.""",
            admin_keyboard()
        )

        return True

    # -----------------------------------------------------
    # DELETE CODE
    # -----------------------------------------------------

    if state == "delete_code":

        delete_code(
            chat_id,
            text
        )

        admin_states.pop(
            admin_id,
            None
        )

        return True

    return False


# =========================================================
# =========================================================
#                      SHOP MODULE
#        (قبلاً در shop.py بود؛ اینجا یکپارچه شده)
# =========================================================
# =========================================================


# =========================================================
# SHOP: KEYBOARDS
# =========================================================

def yes_no_keyboard():
    row = KeypadRow().add(
        KeypadSimpleButton("✅ بله", "shop_confirm_yes")
    ).add(
        KeypadSimpleButton("❌ نه", "shop_confirm_no")
    )
    return ChatKeypad(resize_keyboard=True).add(row)


def back_keyboard():
    row = KeypadRow().add(
        KeypadSimpleButton("🔙 برگشتن", "shop_back_main")
    )
    return ChatKeypad(resize_keyboard=True).add(row)


def shop_main_keyboard():
    row1 = KeypadRow().add(
        KeypadSimpleButton("🆕 شخصیت جدید", "shop_new_character")
    )
    row2 = KeypadRow().add(
        KeypadSimpleButton("🎭 شخصیت موجود", "shop_my_characters")
    )
    row3 = KeypadRow().add(
        KeypadSimpleButton("🔙 برگشتن", "shop_back_main")
    )
    return (
        ChatKeypad(resize_keyboard=True)
        .add(row1)
        .add(row2)
        .add(row3)
    )


def shop_admin_menu_keyboard():
    lock_label = "🔓 باز کردن انتخاب شخصیت" if is_locked() else "🔒 بستن انتخاب شخصیت"

    row1 = KeypadRow().add(
        KeypadSimpleButton("➕ افزودن شخصیت", "shop_admin_add")
    ).add(
        KeypadSimpleButton("📋 لیست شخصیت‌ها", "shop_admin_list")
    )
    row2 = KeypadRow().add(
        KeypadSimpleButton("❌ حذف شخصیت", "shop_admin_delete")
    ).add(
        KeypadSimpleButton(lock_label, "shop_admin_toggle_lock")
    )
    row3 = KeypadRow().add(
        KeypadSimpleButton("🔙 بازگشت به پنل", "shop_admin_back")
    )
    return (
        ChatKeypad(resize_keyboard=True)
        .add(row1)
        .add(row2)
        .add(row3)
    )


def characters_keyboard(owned_codes):
    kb = ChatKeypad(resize_keyboard=True)
    row = KeypadRow()
    count = 0
    for code in owned_codes:
        ch = characters.get(code)
        if not ch:
            continue
        row.add(KeypadSimpleButton(ch["name"], f"shop_select_{code}"))
        count += 1
        if count % 2 == 0:
            kb.add(row)
            row = KeypadRow()
    if count % 2 != 0:
        kb.add(row)
    kb.add(KeypadRow().add(KeypadSimpleButton("🔙 برگشتن", "shop_back_main")))
    return kb


def class_keyboard():
    row1 = KeypadRow().add(
        KeypadSimpleButton("🧍 Player", "class_player")
    ).add(
        KeypadSimpleButton("👶 Mini Huggy", "class_mini_huggy")
    )
    row2 = KeypadRow().add(
        KeypadSimpleButton("👹 Boss", "class_boss")
    )
    return ChatKeypad(resize_keyboard=True).add(row1).add(row2)


def ability_type_keyboard():
    row1 = KeypadRow().add(
        KeypadSimpleButton("😵 بیهوش/فلج‌کننده", "ability_type_stun")
    )
    row2 = KeypadRow().add(
        KeypadSimpleButton("💥 یک‌بار مصرف", "ability_type_onetime")
    )
    row3 = KeypadRow().add(
        KeypadSimpleButton("🗡 دمیج عادی", "ability_type_damage")
    )
    return ChatKeypad(resize_keyboard=True).add(row1).add(row2).add(row3)


# =========================================================
# SHOP: CHARACTER HELPERS
# =========================================================

def find_character_by_code(code):
    code = code.strip()
    return characters.get(code)


CLASS_LABELS = {
    "player": "🧍 Player",
    "mini_huggy": "👶 Mini Huggy",
    "boss": "👹 Boss"
}


def format_ability(a):
    t = a.get("type")

    if t == "stun":
        return f"😵 {a['name']} — بیهوش/فلج‌کننده ({a['turns']} نوبت)"

    if t == "onetime":
        return f"💥 {a['name']} — یک‌بار مصرف (کل HP، روی باس نصف HP)"

    if t == "damage":
        return f"🗡 {a['name']} — دمیج {a['amount']}"

    return f"❔ {a.get('name', '?')}"


def format_character(ch):
    abilities = ch.get("abilities", [])

    if abilities:
        abilities_text = "\n".join(f"  - {format_ability(a)}" for a in abilities)
    else:
        abilities_text = "  بدون قابلیت"

    class_text = CLASS_LABELS.get(ch.get("class"), "نامشخص")

    return (
        f"🎭 نام: {ch['name']}\n"
        f"❤️ HP: {ch['hp']}\n"
        f"💰 قیمت: {ch['price']} PT\n"
        f"🏷 کلاس: {class_text}\n"
        f"✨ قابلیت‌ها:\n{abilities_text}"
    )


# =========================================================
# SHOP - ADMIN: ADD CHARACTER FLOW
# =========================================================

def start_add_character(chat_id, admin_id):
    admin_states[admin_id] = {"state": "shop_newchar_name"}

    send_message(
        chat_id,
        "➕ افزودن شخصیت جدید\n\n"
        "اسم شخصیت را وارد کن.\n\n"
        "مثلاً:\n"
        "Huggy Wuggy"
    )


def handle_admin_state(chat_id, admin_id, text):
    """
    وضعیت‌های چندمرحله‌ایِ مربوط به شاپ را مدیریت می‌کند.
    اگر متعلق به شاپ نبود False برمی‌گرداند تا handle_message ادامه بدهد.
    """

    state_data = admin_states.get(admin_id)

    if not state_data:
        return False

    state = state_data.get("state")

    if not state or not state.startswith("shop_"):
        return False

    # -----------------------------------------------------
    # NAME
    # -----------------------------------------------------

    if state == "shop_newchar_name":

        name = text.strip()

        if not name:
            send_message(chat_id, "❌ اسم نمی‌تواند خالی باشد.")
            return True

        admin_states[admin_id] = {
            "state": "shop_newchar_hp",
            "name": name
        }

        send_message(
            chat_id,
            f"🎭 نام ثبت شد: {name}\n\n"
            "❤️ حالا HP شخصیت را وارد کن.\n\n"
            "مثلاً:\n50"
        )

        return True

    # -----------------------------------------------------
    # HP
    # -----------------------------------------------------

    if state == "shop_newchar_hp":

        try:
            hp = int(text.strip())
        except ValueError:
            send_message(chat_id, "❌ HP باید فقط عدد باشد.\n\nمثلاً:\n50")
            return True

        if hp <= 0:
            send_message(chat_id, "❌ HP باید بیشتر از صفر باشد.")
            return True

        state_data["state"] = "shop_newchar_code"
        state_data["hp"] = hp

        send_message(
            chat_id,
            "🔢 کد چهار رقمی شخصیت را وارد کن.\n\n"
            "مثلاً:\n5665"
        )

        return True

    # -----------------------------------------------------
    # CODE
    # -----------------------------------------------------

    if state == "shop_newchar_code":

        code = text.strip()

        if not code.isdigit() or len(code) != 4:
            send_message(chat_id, "❌ کد باید دقیقاً ۴ رقم باشد.\n\nمثلاً:\n5665")
            return True

        if code in characters:
            send_message(
                chat_id,
                "❌ این کد قبلاً برای شخصیت دیگری استفاده شده.\n\n"
                "یک کد دیگر وارد کن:"
            )
            return True

        state_data["state"] = "shop_newchar_pt"
        state_data["code"] = code

        send_message(
            chat_id,
            "💰 مقدار PT (قیمت خرید) شخصیت را وارد کن.\n\n"
            "مثلاً:\n1000"
        )

        return True

    # -----------------------------------------------------
    # PT
    # -----------------------------------------------------

    if state == "shop_newchar_pt":

        try:
            price = int(text.strip())
        except ValueError:
            send_message(chat_id, "❌ مقدار PT باید فقط عدد باشد.\n\nمثلاً:\n1000")
            return True

        if price <= 0:
            send_message(chat_id, "❌ مقدار PT باید بیشتر از صفر باشد.")
            return True

        state_data["state"] = "shop_newchar_class"
        state_data["price"] = price

        send_message(
            chat_id,
            "🏷 کلاس این شخصیت چیه؟",
            class_keyboard()
        )

        return True

    # -----------------------------------------------------
    # CLASS (fallback متنی؛ دکمه‌ها در handle_admin_button مدیریت می‌شن)
    # -----------------------------------------------------

    if state == "shop_newchar_class":

        cls = _parse_class(text)

        if not cls:
            send_message(
                chat_id,
                "❌ یکی از دکمه‌های زیر را انتخاب کن.",
                class_keyboard()
            )
            return True

        _proceed_to_ability_count(chat_id, admin_id, state_data, cls)
        return True

    # -----------------------------------------------------
    # ABILITY COUNT
    # -----------------------------------------------------

    if state == "shop_newchar_ability_count":

        try:
            n = int(text.strip())
        except ValueError:
            send_message(chat_id, "❌ فقط عدد بفرست (بین ۱ تا ۵).")
            return True

        if not (1 <= n <= 5):
            send_message(chat_id, "❌ تعداد قابلیت باید بین ۱ تا ۵ باشد.")
            return True

        state_data["state"] = "shop_newchar_ability_name"
        state_data["ability_count"] = n
        state_data["abilities"] = []

        send_message(
            chat_id,
            f"✨ قابلیت ۱ از {n}:\n\n"
            "اسم این قابلیت را بگو.\n\n"
            "مثلاً:\nسیلی زدن"
        )

        return True

    # -----------------------------------------------------
    # ABILITY NAME
    # -----------------------------------------------------

    if state == "shop_newchar_ability_name":

        name = text.strip()

        if not name:
            send_message(chat_id, "❌ اسم قابلیت نمی‌تواند خالی باشد.")
            return True

        state_data["state"] = "shop_newchar_ability_type"
        state_data["pending_ability"] = {"name": name}

        send_message(
            chat_id,
            f"🔧 نوع قابلیت «{name}» چیه؟",
            ability_type_keyboard()
        )

        return True

    # -----------------------------------------------------
    # ABILITY TYPE (fallback متنی؛ دکمه‌ها در handle_admin_button مدیریت می‌شن)
    # -----------------------------------------------------

    if state == "shop_newchar_ability_type":

        t = _parse_ability_type(text)

        if not t:
            send_message(
                chat_id,
                "❌ یکی از دکمه‌های زیر را انتخاب کن.",
                ability_type_keyboard()
            )
            return True

        _set_ability_type(chat_id, admin_id, state_data, t)
        return True

    # -----------------------------------------------------
    # ABILITY - STUN TURNS
    # -----------------------------------------------------

    if state == "shop_newchar_ability_stun_turns":

        try:
            turns = int(text.strip())
        except ValueError:
            send_message(chat_id, "❌ فقط عدد بفرست.")
            return True

        if turns <= 0:
            send_message(chat_id, "❌ عدد باید بیشتر از صفر باشد.")
            return True

        state_data["pending_ability"]["turns"] = turns
        _finish_ability(chat_id, admin_id, state_data)
        return True

    # -----------------------------------------------------
    # ABILITY - DAMAGE AMOUNT
    # -----------------------------------------------------

    if state == "shop_newchar_ability_damage":

        try:
            amount = int(text.strip())
        except ValueError:
            send_message(chat_id, "❌ فقط عدد بفرست.")
            return True

        if amount <= 0:
            send_message(chat_id, "❌ عدد باید بیشتر از صفر باشد.")
            return True

        state_data["pending_ability"]["amount"] = amount
        _finish_ability(chat_id, admin_id, state_data)
        return True

    # -----------------------------------------------------
    # CONFIRM (as free text fallback; button handled separately)
    # -----------------------------------------------------

    if state == "shop_newchar_confirm":

        if text.strip() in ("✅ بله", "بله"):
            _save_new_character(chat_id, admin_id, state_data)
            return True

        if text.strip() in ("❌ نه", "نه"):
            admin_states.pop(admin_id, None)
            send_message(chat_id, "🚫 ساخت شخصیت لغو شد.", shop_admin_menu_keyboard())
            return True

        send_message(
            chat_id,
            "❌ متوجه نشدم. یکی از دکمه‌های زیر را انتخاب کن.",
            yes_no_keyboard()
        )
        return True

    # -----------------------------------------------------
    # DELETE CHARACTER (waiting for code)
    # -----------------------------------------------------

    if state == "shop_delete_character":

        code = text.strip()

        ch = characters.pop(code, None)

        admin_states.pop(admin_id, None)

        if not ch:
            send_message(
                chat_id,
                "❌ شخصیتی با این کد پیدا نشد.",
                shop_admin_menu_keyboard()
            )
            return True

        save_characters()

        send_message(
            chat_id,
            f"✅ شخصیت «{ch['name']}» حذف شد.\n\n"
            "توجه: کاربرانی که قبلاً این شخصیت را خریده بودند، همچنان "
            "مالکش حساب می‌شوند، ولی دیگر کسی نمی‌تواند آن را بخرد.",
            shop_admin_menu_keyboard()
        )

        return True

    return False


def _parse_class(text):
    val = text.strip().lower()

    mapping = {
        "player": "player",
        "🧍 player": "player",
        "پلیر": "player",
        "mini huggy": "mini_huggy",
        "👶 mini huggy": "mini_huggy",
        "مینی هاگی": "mini_huggy",
        "مینی‌هاگی": "mini_huggy",
        "boss": "boss",
        "👹 boss": "boss",
        "باس": "boss"
    }

    return mapping.get(val)


def _parse_ability_type(text):
    val = text.strip()

    mapping = {
        "😵 بیهوش/فلج‌کننده": "stun",
        "بیهوش": "stun",
        "فلج‌کننده": "stun",
        "فلج کننده": "stun",
        "💥 یک‌بار مصرف": "onetime",
        "یک‌بار مصرف": "onetime",
        "یک بار مصرف": "onetime",
        "🗡 دمیج عادی": "damage",
        "دمیج عادی": "damage"
    }

    return mapping.get(val)


def _proceed_to_ability_count(chat_id, admin_id, state_data, cls):

    state_data["state"] = "shop_newchar_ability_count"
    state_data["class"] = cls

    send_message(
        chat_id,
        "✨ این شخصیت چند تا قابلیت داره؟ (بین ۱ تا ۵)"
    )


def _set_ability_type(chat_id, admin_id, state_data, t):

    pending = state_data["pending_ability"]
    pending["type"] = t

    if t == "stun":
        state_data["state"] = "shop_newchar_ability_stun_turns"
        send_message(
            chat_id,
            f"😵 «{pending['name']}» چند نوبت طرف رو بیهوش/فلج می‌کنه؟\n\n"
            "یه عدد بفرست."
        )

    elif t == "damage":
        state_data["state"] = "shop_newchar_ability_damage"
        send_message(
            chat_id,
            f"🗡 «{pending['name']}» چقدر دمیج بزنه؟\n\n"
            "یه عدد بفرست."
        )

    else:  # onetime — چیز دیگه‌ای لازم نیست
        _finish_ability(chat_id, admin_id, state_data)


def _finish_ability(chat_id, admin_id, state_data):

    ability = state_data.pop("pending_ability")
    state_data["abilities"].append(ability)

    done = len(state_data["abilities"])
    total = state_data["ability_count"]

    if done < total:

        state_data["state"] = "shop_newchar_ability_name"

        send_message(
            chat_id,
            f"✅ قابلیت «{ability['name']}» ثبت شد.\n\n"
            f"✨ قابلیت {done + 1} از {total}:\n\n"
            "اسم این قابلیت را بگو."
        )

    else:

        state_data["state"] = "shop_newchar_confirm"

        preview = {
            "name": state_data["name"],
            "hp": state_data["hp"],
            "price": state_data["price"],
            "code": state_data["code"],
            "class": state_data["class"],
            "abilities": state_data["abilities"]
        }

        send_message(
            chat_id,
            "🔎 لطفاً اطلاعات شخصیت را بررسی کن:\n\n"
            f"{format_character(preview)}\n\n"
            "آیا مطمئنی؟",
            yes_no_keyboard()
        )


def _save_new_character(chat_id, admin_id, state_data):

    code = state_data["code"]

    characters[code] = {
        "name": state_data["name"],
        "hp": state_data["hp"],
        "price": state_data["price"],
        "class": state_data["class"],
        "abilities": state_data["abilities"]
    }

    save_characters()

    admin_states.pop(admin_id, None)

    send_message(
        chat_id,
        "✅ شخصیت با موفقیت ثبت شد. 🎉\n\n"
        f"{format_character(characters[code])}",
        shop_admin_menu_keyboard()
    )


# =========================================================
# SHOP - ADMIN: BUTTON-LEVEL MENU
# =========================================================

def handle_admin_button(chat_id, admin_id, text, button_id):
    """
    دکمه‌های سطح منوی شاپ (نه وضعیت‌های چندمرحله‌ای) را مدیریت می‌کند.
    """

    if button_id == "shop_admin_menu" or text == "🎭 مدیریت شاپ":
        admin_states.pop(admin_id, None)
        send_message(
            chat_id,
            "🎭 مدیریت شاپ Love Stitch Bot",
            shop_admin_menu_keyboard()
        )
        return True

    if button_id == "shop_admin_back" or text == "🔙 بازگشت به پنل":
        admin_states.pop(admin_id, None)
        send_message(chat_id, "👑 پنل مدیریت Love Stitch Bot", admin_keyboard())
        return True

    if button_id == "shop_admin_add" or text == "➕ افزودن شخصیت":
        start_add_character(chat_id, admin_id)
        return True

    if button_id == "shop_admin_list" or text == "📋 لیست شخصیت‌ها":
        admin_states.pop(admin_id, None)
        _show_character_list(chat_id)
        return True

    if button_id == "shop_admin_delete" or text == "❌ حذف شخصیت":
        admin_states[admin_id] = {"state": "shop_delete_character"}
        send_message(chat_id, "🔢 کد شخصیتی که می‌خواهی حذف کنی را بفرست:")
        return True

    # کلاس شخصیت (Player / Mini Huggy / Boss) هنگام ساخت شخصیت
    if button_id in ("class_player", "class_mini_huggy", "class_boss"):
        state_data = admin_states.get(admin_id)
        if state_data and state_data.get("state") == "shop_newchar_class":
            cls = button_id.split("class_", 1)[1]
            _proceed_to_ability_count(chat_id, admin_id, state_data, cls)
            return True

    # نوع قابلیت (بیهوش / یک‌بار مصرف / دمیج) هنگام ساخت شخصیت
    if button_id in ("ability_type_stun", "ability_type_onetime", "ability_type_damage"):
        state_data = admin_states.get(admin_id)
        if state_data and state_data.get("state") == "shop_newchar_ability_type":
            t = button_id.split("ability_type_", 1)[1]
            _set_ability_type(chat_id, admin_id, state_data, t)
            return True

    if button_id == "shop_admin_toggle_lock" or text in (
        "🔒 بستن انتخاب شخصیت", "🔓 باز کردن انتخاب شخصیت"
    ):
        shop_settings["characters_locked"] = not is_locked()
        save_settings()

        status = "بسته شد 🔒" if is_locked() else "باز شد 🔓"

        send_message(
            chat_id,
            f"✅ امکان انتخاب/تغییر شخصیت توسط کاربران {status}.",
            shop_admin_menu_keyboard()
        )
        return True

    # دکمه‌های بله/نه ممکن است هنگام تایید ساخت شخصیت هم برسند
    if button_id in ("shop_confirm_yes", "shop_confirm_no"):
        state_data = admin_states.get(admin_id)
        if state_data and state_data.get("state") == "shop_newchar_confirm":
            if button_id == "shop_confirm_yes":
                _save_new_character(chat_id, admin_id, state_data)
            else:
                admin_states.pop(admin_id, None)
                send_message(chat_id, "🚫 ساخت شخصیت لغو شد.", shop_admin_menu_keyboard())
            return True

    return False


def _show_character_list(chat_id):

    if not characters:
        send_message(
            chat_id,
            "📋 هنوز هیچ شخصیتی ساخته نشده.",
            shop_admin_menu_keyboard()
        )
        return

    text = "📋 شخصیت‌های شاپ:\n\n"

    for code, ch in characters.items():
        text += f"🔢 کد: {code}\n{format_character(ch)}\n\n"

    send_message(chat_id, text, shop_admin_menu_keyboard())


# =========================================================
# SHOP - USER: ENTER SHOP
# =========================================================

def enter_shop(chat_id, user_id):
    user_states.pop(user_id, None)

    send_message(
        chat_id,
        "🛒 به شاپ Love Stitch Bot خوش آمدید.\n\n"
        "از گزینه‌های زیر انتخاب کنید:",
        shop_main_keyboard()
    )


# =========================================================
# SHOP - USER: BUTTON-LEVEL (شخصیت جدید / شخصیت موجود / برگشتن / انتخاب)
# =========================================================

def handle_user_button(chat_id, user_id, text, button_id):

    if button_id == "shop_back_main" or text == "🔙 برگشتن":
        user_states.pop(user_id, None)
        send_message(chat_id, "👋 به منوی اصلی برگشتی.", user_keyboard())
        return True

    if button_id == "shop_new_character" or text == "🆕 شخصیت جدید":
        user_states[user_id] = {"state": "shop_buy_code"}
        send_message(chat_id, "🔢 کد شخصیت را وارد کنید.")
        return True

    if button_id == "shop_my_characters" or text == "🎭 شخصیت موجود":
        user_states.pop(user_id, None)
        _show_characters(chat_id, user_id)
        return True

    if button_id and button_id.startswith("shop_select_"):
        code = button_id.split("shop_select_", 1)[1]
        _select_character(chat_id, user_id, code)
        return True

    if button_id in ("shop_confirm_yes", "shop_confirm_no"):
        state_data = user_states.get(user_id)
        if state_data and state_data.get("state") == "shop_buy_confirm":
            if button_id == "shop_confirm_yes":
                _finalize_purchase(chat_id, user_id, state_data)
            else:
                user_states.pop(user_id, None)
                send_message(chat_id, "🚫 خرید لغو شد.", shop_main_keyboard())
            return True

    return False


def _show_characters(chat_id, user_id):

    owned = users.get(user_id, {}).get("characters", [])

    if not owned:
        send_message(
            chat_id,
            "🎭 هنوز هیچ شخصیتی نخریدی.",
            shop_main_keyboard()
        )
        return

    send_message(
        chat_id,
        "🎭 شخصیت‌های شما:",
        characters_keyboard(owned)
    )


def _select_character(chat_id, user_id, code):

    if is_locked():
        send_message(
            chat_id,
            "🔒 در حال حاضر امکان انتخاب یا تغییر شخصیت بسته است.",
            shop_main_keyboard()
        )
        return

    owned = users.get(user_id, {}).get("characters", [])

    if code not in owned:
        send_message(
            chat_id,
            "❌ این شخصیت جزو شخصیت‌های خریداری‌شدهٔ تو نیست.",
            shop_main_keyboard()
        )
        return

    ch = characters.get(code)

    if not ch:
        send_message(
            chat_id,
            "❌ اطلاعات این شخصیت دیگر در دسترس نیست.",
            shop_main_keyboard()
        )
        return

    users[user_id]["selected_character"] = code
    save_users()

    send_message(
        chat_id,
        f"🥳 تبریک! شخصیت شما با موفقیت انتخاب شد: {ch['name']}",
        back_keyboard()
    )


# =========================================================
# SHOP - USER: MULTI-STEP STATES (کد خرید / تایید خرید)
# =========================================================

def _handle_buy_code_input(chat_id, user_id, code):
    """
    منطق مشترک «کد شخصیت رسید»: هم وقتی توی حالت shop_buy_code هستیم
    صداش می‌زنیم، هم وقتی کاربر بدون زدن دکمه مستقیم کد فرستاده
    (try_bare_code). اگه کدی پیدا نشد False برمی‌گردونه.
    """

    ch = find_character_by_code(code)

    if not ch:
        return False

    owned = users.get(user_id, {}).get("characters", [])

    if code in owned:
        user_states.pop(user_id, None)
        send_message(
            chat_id,
            f"ℹ️ تو قبلاً شخصیت «{ch['name']}» را خریده‌ای.",
            shop_main_keyboard()
        )
        return True

    user_states[user_id] = {
        "state": "shop_buy_confirm",
        "code": code
    }

    send_message(
        chat_id,
        f"✅ شخصیت پیدا شد: {ch['name']}\n\n"
        f"{format_character(ch)}\n\n"
        "آیا می‌خواهید خریداری کنید؟",
        yes_no_keyboard()
    )

    return True


def try_bare_code(chat_id, user_id, text):
    """
    اگه کاربر بدون زدن دکمهٔ «🆕 شخصیت جدید»، مستقیم یه کد ۴رقمی
    معتبر بفرسته، بازم روند خرید شروع بشه (به‌جای پیام «متوجه نشدم»).
    handle_message این رو درست قبل از پیام fallback صدا می‌زنه.
    """

    code = text.strip()

    if not (code.isdigit() and len(code) == 4):
        return False

    return _handle_buy_code_input(chat_id, user_id, code)


def handle_user_state(chat_id, user_id, text):

    state_data = user_states.get(user_id)

    if not state_data:
        return False

    state = state_data.get("state")

    if not state or not state.startswith("shop_"):
        return False

    # -----------------------------------------------------
    # BUY: WAITING FOR CODE
    # -----------------------------------------------------

    if state == "shop_buy_code":

        code = text.strip()

        if _handle_buy_code_input(chat_id, user_id, code):
            return True

        send_message(
            chat_id,
            "❌ شخصیتی با این کد پیدا نشد.\n\n"
            "دوباره کد را وارد کن، یا برای بازگشت «🔙 برگشتن» را بزن.",
            back_keyboard()
        )

        return True

    # -----------------------------------------------------
    # BUY: CONFIRM (متنی، برای وقتی دکمه کار نکرد)
    # -----------------------------------------------------

    if state == "shop_buy_confirm":

        if text.strip() in ("✅ بله", "بله"):
            _finalize_purchase(chat_id, user_id, state_data)
            return True

        if text.strip() in ("❌ نه", "نه"):
            user_states.pop(user_id, None)
            send_message(chat_id, "🚫 خرید لغو شد.", shop_main_keyboard())
            return True

        send_message(
            chat_id,
            "❌ متوجه نشدم. یکی از دکمه‌های زیر را انتخاب کن.",
            yes_no_keyboard()
        )
        return True

    return False


def _finalize_purchase(chat_id, user_id, state_data):

    code = state_data.get("code")
    ch = characters.get(code)

    user_states.pop(user_id, None)

    if not ch:
        send_message(
            chat_id,
            "❌ این شخصیت دیگر در دسترس نیست.",
            shop_main_keyboard()
        )
        return

    if user_id not in users:
        send_message(
            chat_id,
            "❌ اطلاعات کاربری تو پیدا نشد.",
            shop_main_keyboard()
        )
        return

    user = users[user_id]
    current_pt = user.get("pt", 0)
    price = ch["price"]

    if current_pt < price:
        send_message(
            chat_id,
            f"❌ موجودی کافی نیست!\n\n"
            f"💰 موجودی فعلی: {current_pt} PT\n"
            f"💸 قیمت شخصیت: {price} PT",
            shop_main_keyboard()
        )
        return

    owned = user.setdefault("characters", [])

    if code in owned:
        send_message(
            chat_id,
            f"ℹ️ تو قبلاً شخصیت «{ch['name']}» را خریده‌ای.",
            shop_main_keyboard()
        )
        return

    user["pt"] = current_pt - price
    owned.append(code)

    save_users()

    send_message(
        chat_id,
        f"✅ شخصیت «{ch['name']}» خریداری شد.\n\n"
        f"💰 موجودی جدید: {user['pt']} PT",
        back_keyboard()
    )


# =========================================================
# KILL LOG (از هارلی سویر) — واریز PT برای کشتن
# =========================================================
# هارلی سویر (بات ۲) توی همین users.json، زیر کلید _kill_log،
# هر کشتن رو ثبت می‌کنه. اینجا هر چرخهٔ حلقهٔ اصلی چک می‌کنیم و
# اگه رکورد پردازش‌نشده‌ای بود، PT رو واریز و به قاتل خبر می‌دیم.

def reload_users():

    # اگه فایل نبود، یا نیمه‌نوشته/خراب بود (مثلاً همزمان با نوشتن بات ۲)،
    # حافظهٔ فعلی رو دست‌نخورده نگه می‌داریم؛ وگرنه یه خطای لحظه‌ای
    # می‌تونست کل users رو خالی کنه و بعد با save_users روی فایل بنویسه.
    if not os.path.exists(USERS_FILE):
        return

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    except Exception as e:
        print("⚠️ خواندن users.json در reload ناموفق بود؛ حافظهٔ فعلی حفظ شد:")
        print(e)
        return

    if not isinstance(data, dict):
        print("⚠️ ساختار users.json معتبر نیست؛ حافظهٔ فعلی حفظ شد.")
        return

    users.clear()
    users.update(data)

    # دیکشنری‌های شاپ با reload عوض شدن؛ دوباره بهشون وصل می‌شیم.
    bind_shop_storage()


def process_kill_log():

    reload_users()

    log = users.get("_kill_log", [])
    changed = False

    for entry in log:

        if entry.get("processed"):
            continue

        killer_id = entry.get("killer_id")

        if killer_id in users and isinstance(users[killer_id], dict):

            users[killer_id]["pt"] = users[killer_id].get("pt", 0) + KILL_REWARD_PT

            killer_chat_id = users[killer_id].get("chat_id")

            if killer_chat_id:
                send_message(
                    killer_chat_id,
                    f"🥳 تبریک! تو یه حریف رو توی فایت کشتی و {KILL_REWARD_PT} PT گرفتی. 🎉\n\n"
                    f"💰 موجودی جدید: {users[killer_id]['pt']} PT",
                    user_keyboard()
                )

        entry["processed"] = True
        changed = True

    if changed:
        save_users()


# =========================================================
# HANDLE MESSAGE
# =========================================================

def handle_message(update):

    new_message = update.get(
        "new_message",
        {}
    )

    chat_id = update.get(
        "chat_id"
    )

    text = new_message.get(
        "text",
        ""
    ).strip()

    sender_id = new_message.get(
        "sender_id"
    )

    aux_data = new_message.get(
        "aux_data",
        {}
    )

    button_id = aux_data.get(
        "button_id"
    )

    if not chat_id or not sender_id:
        return

    print("\n👤 Sender:", sender_id)
    print("💬 Text:", text)
    print("🔘 Button:", button_id)

    user_id = update_user_info(
        chat_id,
        sender_id
    )

    if not user_id:
        user_id = sender_id

    # =====================================================
    # ADMIN
    # =====================================================

    if user_id == ADMIN_ID:

        # -------------------------------------------------
        # START
        # -------------------------------------------------

        if text == "/start":

            admin_states.pop(
                user_id,
                None
            )

            send_message(
                chat_id,
                "👑 پنل مدیریت Love Stitch Bot",
                admin_keyboard()
            )

            return

        # -------------------------------------------------
        # MAIN ADMIN BUTTONS
        # -------------------------------------------------

        if (
            button_id == "admin_users"
            or text == "👥 کاربران"
        ):

            admin_states.pop(
                user_id,
                None
            )

            show_users(
                chat_id
            )

            return

        if (
            button_id == "admin_stats"
            or text == "📊 آمار"
        ):

            admin_states.pop(
                user_id,
                None
            )

            show_stats(
                chat_id
            )

            return

        if (
            button_id == "admin_pt"
            or text == "💰 مدیریت PT"
        ):

            admin_states.pop(
                user_id,
                None
            )

            start_pt_management(
                chat_id,
                user_id
            )

            return

        if (
            button_id == "admin_newcode"
            or text == "🎟 ساخت کد"
        ):

            admin_states[user_id] = {
                "state": "newcode_name"
            }

            send_message(
                chat_id,
                "🎟 ساخت کد جدید\n\n"
                "اسم کد جایزه را بفرست.\n\n"
                "مثلاً:\n"
                "LOVE2026"
            )

            return

        if (
            button_id == "admin_codes"
            or text == "📋 کدها"
        ):

            admin_states.pop(
                user_id,
                None
            )

            show_codes(
                chat_id
            )

            return

        if (
            button_id == "admin_deletecode"
            or text == "❌ حذف کد"
        ):

            admin_states[user_id] = {
                "state": "delete_code"
            }

            send_message(
                chat_id,
                "❌ اسم کدی که می‌خواهی حذف کنی را بفرست:"
            )

            return

        # -------------------------------------------------
        # SHOP ADMIN BUTTONS (مدیریت شاپ / افزودن / لیست / حذف / قفل)
        # -------------------------------------------------

        if handle_admin_button(
            chat_id,
            user_id,
            text,
            button_id
        ):

            return

        # -------------------------------------------------
        # PT STATE
        # -------------------------------------------------

        if handle_pt_state(
            chat_id,
            user_id,
            text,
            button_id
        ):

            return

        # -------------------------------------------------
        # CODE STATE
        # -------------------------------------------------

        if handle_admin_code_state(
            chat_id,
            user_id,
            text
        ):

            return

        # -------------------------------------------------
        # SHOP STATE (نام/HP/کد/PT/قابلیت‌ها/تاییدِ شخصیت جدید)
        # -------------------------------------------------

        if handle_admin_state(
            chat_id,
            user_id,
            text
        ):

            return

        send_message(
            chat_id,
            "🤔 این دستور ادمین رو متوجه نشدم.",
            admin_keyboard()
        )

        return

    # =====================================================
    # USER
    # =====================================================

    # -----------------------------------------------------
    # START
    # -----------------------------------------------------

    if text == "/start":

        user_states.pop(
            user_id,
            None
        )

        send_message(
            chat_id,
            "👋 سلام!\n\n"
            "به Love Stitch Bot خوش اومدی ❤️",
            user_keyboard()
        )

        return

    # -----------------------------------------------------
    # BALANCE
    # -----------------------------------------------------

    if (
        button_id == "balance"
        or text == "💰 موجودی"
    ):

        user_states.pop(
            user_id,
            None
        )

        pt = users.get(
            user_id,
            {}
        ).get(
            "pt",
            0
        )

        send_message(
            chat_id,
            f"💰 موجودی فعلی شما:\n\n"
            f"{pt} PT",
            user_keyboard()
        )

        return

    # -----------------------------------------------------
    # REWARD CODE
    # -----------------------------------------------------

    if (
        button_id == "gift"
        or text == "🎁 کد جایزه"
    ):

        user_states[user_id] = {
            "state": "waiting_reward_code"
        }

        send_message(
            chat_id,
            "🎁 کد جایزه\n\n"
            "کد جایزه‌ات رو بفرست:",
            user_keyboard()
        )

        return

    # -----------------------------------------------------
    # SHOP
    # -----------------------------------------------------

    if (
        button_id == "shop"
        or text == "🛒 شاپ"
    ):

        enter_shop(
            chat_id,
            user_id
        )

        return

    # -----------------------------------------------------
    # SHOP BUTTONS (شخصیت جدید / شخصیت موجود / برگشتن / انتخاب)
    # -----------------------------------------------------

    if handle_user_button(
        chat_id,
        user_id,
        text,
        button_id
    ):

        return

    # -----------------------------------------------------
    # HELP
    # -----------------------------------------------------

    if (
        button_id == "help"
        or text == "ℹ️ راهنما"
    ):

        user_states.pop(
            user_id,
            None
        )

        send_message(
            chat_id,
            """ℹ️ راهنمای Love Stitch Bot

💰 موجودی
نمایش مقدار PT شما.

🎁 کد جایزه
کد جایزه را وارد کن تا در صورت معتبر بودن، PT آن به حسابت اضافه شود.

🛒 شاپ
خرید شخصیت‌ها و آیتم‌ها.

❤️ موفق باشی!""",
            user_keyboard()
        )

        return

    # -----------------------------------------------------
    # WAITING FOR REWARD CODE
    # -----------------------------------------------------

    state_data = user_states.get(
        user_id
    )

    if state_data:

        state = state_data.get(
            "state"
        )

        if state == "waiting_reward_code":

            user_states.pop(
                user_id,
                None
            )

            handle_user_reward_code(
                chat_id,
                user_id,
                text
            )

            return

        # -------------------------------------------------
        # SHOP STATE (کد خرید / تایید خرید)
        # -------------------------------------------------

        if handle_user_state(
            chat_id,
            user_id,
            text
        ):

            return

    # -----------------------------------------------------
    # SHOP: BARE CODE (اگه بدون زدن دکمه مستقیم کد فرستاده باشه)
    # -----------------------------------------------------

    if try_bare_code(
        chat_id,
        user_id,
        text
    ):

        return

    # -----------------------------------------------------
    # UNKNOWN
    # -----------------------------------------------------

    send_message(
        chat_id,
        "🤔 این دستور رو متوجه نشدم...\n\n"
        "از دکمه‌های زیر استفاده کن.",
        user_keyboard()
    )


# =========================================================
# GET UPDATES
# =========================================================

def get_updates(offset=None):

    payload = {
        "limit": 10
    }

    if offset:
        payload["offset_id"] = offset

    try:

        response = requests.post(
            f"{API_URL}/getUpdates",
            json=payload,
            timeout=30
        )

        return response.json()

    except Exception as e:

        if is_network_error(e):
            print("📡 قطعی موقت شبکه در getUpdates (مثلاً تغییر وی‌پی‌ان):", e)
        else:
            print("❌ خطا در getUpdates:")
            print(e)

        return {}


# =========================================================
# MAIN LOOP
# =========================================================
# این بخش داخل if __name__ == "__main__" قرار گرفته تا اگه بعداً
# فایل دیگه‌ای این فایل رو import کرد، حلقهٔ getUpdates
# خودبه‌خود اجرا نشه.

def run():

    global offset_id

    print("\n======================================")
    print("❤️ Love Stitch Bot")
    print("🚀 Main")
    print("======================================")

    print("👥 کاربران:", len(users))
    print("🎟 کدها:", len(codes))
    print("🎭 شخصیت‌های شاپ:", len(characters))
    print("📌 Offset:", offset_id)

    # مقدار تأخیر بعد از خطا؛ با هر خطای پشت‌سرهم بیشتر می‌شه
    # (backoff افزایشی) تا در قطعی‌های طولانی، منابع کمتر مصرف بشه.
    MIN_RETRY_DELAY = 3
    MAX_RETRY_DELAY = 30
    retry_delay = MIN_RETRY_DELAY

    while True:

        try:

            process_kill_log()

            result = get_updates(
                offset_id
            )

            if not result:

                # یعنی get_updates خودش خطا رو مدیریت و چاپ کرده
                # (مثلاً قطعی شبکه). فقط با تأخیر افزایشی صبر می‌کنیم.
                print(f"⏳ {retry_delay} ثانیه صبر و تلاش دوباره...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)

                continue

            if result.get("status") != "OK":

                print("❌ API ERROR:")
                print(result)

                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)

                continue

            # درخواست موفق بود؛ تأخیر رو به حالت اول برگردون
            retry_delay = MIN_RETRY_DELAY

            data = result.get(
                "data",
                {}
            )

            updates = data.get(
                "updates",
                []
            )

            next_offset = data.get(
                "next_offset_id"
            )

            if next_offset:

                offset_id = next_offset

                save_offset(
                    offset_id
                )

            for update in updates:

                print("\n📨 NEW UPDATE:")
                print(update)

                if update.get(
                    "type"
                ) == "NewMessage":

                    handle_message(
                        update
                    )

            time.sleep(0.3)

        except KeyboardInterrupt:

            print(
                "\n🛑 Bot stopped."
            )

            break

        except Exception as e:

            if is_network_error(e):
                print("📡 قطعی موقت شبکه در حلقهٔ اصلی (مثلاً تغییر وی‌پی‌ان):", e)
            else:
                print(
                    "❌ MAIN LOOP ERROR:"
                )
                print(e)

            print(f"⏳ {retry_delay} ثانیه صبر و تلاش دوباره...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)


if __name__ == "__main__":
    run()
