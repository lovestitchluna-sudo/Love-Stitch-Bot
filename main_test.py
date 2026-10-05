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

    total_users = len(users)

    total_pt = 0

    for data in users.values():

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

        if shop.handle_admin_button(
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

        if shop.handle_admin_state(
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

        shop.enter_shop(
            chat_id,
            user_id
        )

        return

    # -----------------------------------------------------
    # SHOP BUTTONS (شخصیت جدید / شخصیت موجود / برگشتن / انتخاب)
    # -----------------------------------------------------

    if shop.handle_user_button(
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

        if shop.handle_user_state(
            chat_id,
            user_id,
            text
        ):

            return

    # -----------------------------------------------------
    # SHOP: BARE CODE (اگه بدون زدن دکمه مستقیم کد فرستاده باشه)
    # -----------------------------------------------------

    if shop.try_bare_code(
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
# KILL LOG (از هارلی سویر) — واریز PT برای کشتن
# =========================================================
# هارلی سویر (بات ۲) توی همین users.json، زیر کلید _kill_log،
# هر کشتن رو ثبت می‌کنه. اینجا هر چرخهٔ حلقهٔ اصلی چک می‌کنیم و
# اگه رکورد پردازش‌نشده‌ای بود، PT رو واریز و به قاتل خبر می‌دیم.

def reload_users():
    global users
    users.clear()
    users.update(load_json(USERS_FILE, {}))


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
# SHOP MODULE
# =========================================================
import shop.json


# =========================================================
# MAIN LOOP
# =========================================================
# این بخش داخل if __name__ == "__main__" قرار گرفته تا اگه بعداً
# shop.py (یا هر فایل دیگه‌ای) این فایل رو import کرد، حلقهٔ
# getUpdates خودبه‌خود اجرا نشه.

def run():

    global offset_id

    print("\n======================================")
    print("❤️ Love Stitch Bot")
    print("🚀 Main Test")
    print("======================================")

    print("👥 کاربران:", len(users))
    print("🎟 کدها:", len(codes))
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
