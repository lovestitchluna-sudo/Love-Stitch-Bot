import json
import os
import time

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

TOKEN = os.environ["BOT_TOKENH"]
ADMIN_ID = "u0KNMhm07ba2376f545d81e75453c8c9"

API_URL = f"https://botapi.rubika.ir/v3/{TOKEN}"

bot = RubiBot(TOKEN)

# همون فایلی که Love Stitch / شاپ استفاده می‌کنن؛ هارلی باید کنار
# اونا، توی همون پوشه، اجرا بشه تا به شخصیت‌ها و کاربرها دسترسی داشته باشه.
USERS_FILE = "users.json"
OFFSET_FILE = "offset_harley.json"

# طبق چیزی که قبلاً توافق کردیم: ۲۰ PT برای هر کشتن (نه هر آسیب).
# اگه واقعاً ۱۰ می‌خوای، همین یه عدد رو عوض کن؛ بقیهٔ کد کاری باهاش نداره.
KILL_REWARD_PT = 20


# =========================================================
# JSON HELPERS (کپی مستقل؛ این بات پردازش جدایی از Love Stitch اجرا می‌شه)
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
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"❌ خطا در ذخیره {filename}:")
        print(e)
        return False


def load_all():
    return load_json(USERS_FILE, {})


def save_all(data):
    save_json(USERS_FILE, data)


def ensure_reserved(data):
    if "_shop_characters" not in data:
        data["_shop_characters"] = {}
    if "_kill_log" not in data:
        data["_kill_log"] = []


def load_offset():
    if not os.path.exists(OFFSET_FILE):
        return None
    try:
        with open(OFFSET_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("offset_id")
    except Exception as e:
        print("❌ خطا در خواندن offset هارلی:")
        print(e)
        return None


def save_offset(offset_id):
    try:
        with open(OFFSET_FILE, "w", encoding="utf-8") as f:
            json.dump({"offset_id": offset_id}, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print("❌ خطا در ذخیره offset هارلی:")
        print(e)


offset_id = load_offset()

# برای مرحلهٔ «مطمئنی؟» قبل از پاک‌کردن فایت قبلی
admin_states = {}


# =========================================================
# NETWORK ERROR HELPER (همون منطق Love Stitch)
# =========================================================

NETWORK_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)


def is_network_error(e):
    return isinstance(e, NETWORK_ERRORS)


# =========================================================
# SEND MESSAGE
# =========================================================

def send_message(chat_id, text, keypad=None):
    try:
        if keypad is not None:
            result = bot.send_message(chat_id, text, chat_keypad=keypad)
        else:
            result = bot.send_message(chat_id, text)
        print("📥 SEND RESULT (Harley):")
        print(result)
        return result
    except Exception as e:
        if is_network_error(e):
            print("📡 قطعی موقت شبکه در send_message (هارلی):", e)
        else:
            print("❌ SEND MESSAGE ERROR (هارلی):")
            print(e)
        return None


# =========================================================
# USER / CHARACTER HELPERS
# =========================================================

def is_real_user_id(uid):
    return isinstance(uid, str) and not uid.startswith("_")


def find_user_by_username(data, username):
    username = username.strip().lstrip("@").lower()

    if not username:
        return None

    for uid, rec in data.items():
        if not is_real_user_id(uid) or not isinstance(rec, dict):
            continue
        if rec.get("username", "").lower() == username:
            return uid

    return None


def resolve_target(data, raw):
    """
    هدف رو هم با یوزرنیم (@user) و هم مستقیم با آیدی پیدا می‌کنه.
    """

    raw = raw.strip()

    if not raw:
        return None

    if raw.startswith("@"):
        return find_user_by_username(data, raw)

    if is_real_user_id(raw) and raw in data and isinstance(data[raw], dict):
        return raw

    return None


def get_character(data, code):
    if not code:
        return None
    return data.get("_shop_characters", {}).get(code)


def ensure_fighter(data, user_id):
    """
    رکورد فایتِ یه کاربر رو (HP فعلی، زنده/مرده، بیهوشی، قابلیت‌های
    یک‌بارمصرفِ استفاده‌شده) اگه نبود می‌سازه. اگه اصلاً کاربر ثبت‌نشده
    باشه (توی Love Stitch هیچ‌وقت /start نزده) None برمی‌گردونه.
    """

    rec = data.get(user_id)

    if not rec or not isinstance(rec, dict):
        return None

    if rec.get("fight_hp") is None or "fight_alive" not in rec:
        code = rec.get("selected_character")
        ch = get_character(data, code)
        rec["fight_hp"] = ch["hp"] if ch else 0
        rec["fight_alive"] = True

    rec.setdefault("stunned_turns", 0)
    rec.setdefault("used_onetime_abilities", [])

    return rec


def display_name(rec, user_id):
    username = rec.get("username")
    if username:
        return f"@{username}"
    return rec.get("display_name") or user_id


# =========================================================
# ADMIN KEYBOARDS
# =========================================================

def admin_keyboard():
    row1 = KeypadRow().add(
        KeypadSimpleButton("📊 وضعیت فایت", "harley_status")
    )
    row2 = KeypadRow().add(
        KeypadSimpleButton("🗑 پاک کردن فایت قبلی", "harley_reset")
    )
    return ChatKeypad(resize_keyboard=True).add(row1).add(row2)


def confirm_keyboard():
    row = KeypadRow().add(
        KeypadSimpleButton("✅ بله", "harley_reset_yes")
    ).add(
        KeypadSimpleButton("❌ نه", "harley_reset_no")
    )
    return ChatKeypad(resize_keyboard=True).add(row)


# =========================================================
# ADMIN COMMANDS
# =========================================================

def _do_reset_fight(data):
    """
    HP همه رو به مقدار کامل شخصیتشون برمی‌گردونه، همه رو زنده می‌کنه،
    بیهوشی‌ها رو صفر می‌کنه و لیست قابلیت‌های یک‌بارمصرفِ استفاده‌شده
    رو خالی می‌کنه — یعنی کاملاً مثل این‌که فایت قبلی اصلاً نبوده.
    """

    count = 0

    for uid, rec in data.items():
        if not is_real_user_id(uid) or not isinstance(rec, dict):
            continue
        if not rec.get("selected_character"):
            continue

        ch = get_character(data, rec.get("selected_character"))
        rec["fight_hp"] = ch["hp"] if ch else 0
        rec["fight_alive"] = True
        rec["stunned_turns"] = 0
        rec["used_onetime_abilities"] = []
        count += 1

    save_all(data)
    return count


def handle_admin_command(chat_id, data, text, sender_id, button_id=None):
    """
    اگه دستور ادمین بود پردازشش می‌کنه و True برمی‌گردونه (و data رو
    خودش ذخیره می‌کنه). اگه دستور ادمین نبود False برمی‌گردونه تا
    پیام به‌عنوان یه حرکت فایت بررسی بشه (ادمین هم می‌تونه بجنگه).
    """

    # -----------------------------------------------------
    # مرحلهٔ «مطمئنی؟» برای پاک‌کردن فایت قبلی
    # -----------------------------------------------------

    if admin_states.get(sender_id) == "waiting_reset_confirm":

        if button_id == "harley_reset_yes" or text == "✅ بله":
            admin_states.pop(sender_id, None)
            count = _do_reset_fight(data)
            send_message(
                chat_id,
                f"✅ فایت قبلی پاک شد. {count} نفر الان با HP کامل آماده‌ی فایت جدیدن.",
                admin_keyboard()
            )
            return True

        if button_id == "harley_reset_no" or text == "❌ نه":
            admin_states.pop(sender_id, None)
            send_message(
                chat_id,
                "باشه، فایت فعلی دست‌نخورده موند.",
                admin_keyboard()
            )
            return True

        send_message(
            chat_id,
            "❌ یکی از دکمه‌های زیر رو انتخاب کن.",
            confirm_keyboard()
        )
        return True

    # -----------------------------------------------------
    # /start
    # -----------------------------------------------------

    if text == "/start":
        send_message(
            chat_id,
            "سلام ادمین 👋\n\n"
            "هارلی سویر آماده‌ست.\n\n"
            "برای حمله (برای همه)، بنویس:\n"
            "اسم قابلیت.@یوزرنیم\n"
            "مثلاً: سیلی زدن.@user_2",
            admin_keyboard()
        )
        return True

    # -----------------------------------------------------
    # وضعیت فایت
    # -----------------------------------------------------

    if button_id == "harley_status" or text == "📊 وضعیت فایت" or text == "وضعیت فایت":

        lines = []

        for uid, rec in data.items():
            if not is_real_user_id(uid) or not isinstance(rec, dict):
                continue
            if not rec.get("selected_character"):
                continue

            status = "زنده ✅" if rec.get("fight_alive", True) else "مرده 💀"
            hp = rec.get("fight_hp", "-")
            lines.append(f"{display_name(rec, uid)} (آیدی: {uid})\nHP: {hp} — {status}")

        send_message(
            chat_id,
            "📊 وضعیت فایت:\n\n" + ("\n\n".join(lines) if lines else "کسی هنوز شخصیتی انتخاب نکرده."),
            admin_keyboard()
        )
        return True

    # -----------------------------------------------------
    # پاک کردن فایت قبلی → اول تأیید می‌گیریم
    # -----------------------------------------------------

    if button_id == "harley_reset" or text in ("🗑 پاک کردن فایت قبلی", "ریست فایت"):

        admin_states[sender_id] = "waiting_reset_confirm"

        send_message(
            chat_id,
            "⚠️ مطمئنی می‌خوای فایت قبلی رو پاک کنی؟\n\n"
            "همه‌چیز (HP، زنده/مرده، بیهوشی، قابلیت‌های یک‌بارمصرفِ استفاده‌شده) "
            "برای همه برمی‌گرده به حالت اول.",
            confirm_keyboard()
        )
        return True

    return False


# =========================================================
# HANDLE MESSAGE
# =========================================================

def handle_message(update):

    new_message = update.get("new_message", {})
    chat_id = update.get("chat_id")
    text = new_message.get("text", "").strip()
    sender_id = new_message.get("sender_id")
    button_id = new_message.get("aux_data", {}).get("button_id")

    if not chat_id or not sender_id:
        return

    print("\n👤 Sender (Harley):", sender_id)
    print("💬 Text:", text)

    data = load_all()
    ensure_reserved(data)

    # -----------------------------------------------------
    # ADMIN
    # -----------------------------------------------------

    if sender_id == ADMIN_ID:
        if handle_admin_command(chat_id, data, text, sender_id, button_id):
            return

    # -----------------------------------------------------
    # اگه فرستنده الان توی فایته (شخصیت انتخاب کرده)، اول ببینیم
    # اصلاً اجازهٔ حرکت داره یا نه (مرده / بیهوش) — این چک روی هر
    # پیامی اعمال می‌شه، نه فقط پیام‌های حمله.
    # -----------------------------------------------------

    rec = data.get(sender_id)

    if rec and isinstance(rec, dict) and rec.get("selected_character"):

        fighter = ensure_fighter(data, sender_id)

        if not fighter.get("fight_alive", True):
            send_message(chat_id, "❌ تو نمی‌تونی حرکت کنی چون مردی. برای فایت بعدی صبر کن.")
            save_all(data)
            return

        if fighter.get("stunned_turns", 0) > 0:
            fighter["stunned_turns"] -= 1
            remaining = fighter["stunned_turns"]

            if remaining > 0:
                send_message(
                    chat_id,
                    f"❌ تو تا {remaining} دفعهٔ دیگه نمی‌تونی کاری کنی چون بیهوش/فلجی هستی."
                )
            else:
                send_message(
                    chat_id,
                    "❌ این نوبت هنوز بیهوش/فلجی هستی، ولی نوبت بعد می‌تونی حرکت کنی."
                )

            save_all(data)
            return

    # -----------------------------------------------------
    # حرکت فایت: اسم قابلیت.هدف
    # -----------------------------------------------------

    if "." not in text:
        return

    ability_name, _, target_raw = text.partition(".")
    ability_name = ability_name.strip()
    target_raw = target_raw.strip()

    if not ability_name or not target_raw:
        return

    attacker = ensure_fighter(data, sender_id)

    if not attacker:
        send_message(chat_id, "❌ تو هنوز توی Love Stitch Bot ثبت نشدی. اول اونجا /start بزن.")
        return

    if not attacker.get("selected_character"):
        send_message(chat_id, "❌ تو هنوز شخصیتی انتخاب نکردی (توی شاپ Love Stitch انتخاب کن).")
        return

    attacker_char = get_character(data, attacker["selected_character"])

    if not attacker_char:
        send_message(chat_id, "❌ اطلاعات شخصیت تو پیدا نشد.")
        return

    ability = next(
        (a for a in attacker_char.get("abilities", []) if a.get("name") == ability_name),
        None
    )

    if not ability:
        send_message(
            chat_id,
            f"❌ شخصیت تو ({attacker_char['name']}) قابلیت «{ability_name}» رو نداره."
        )
        return

    target_id = resolve_target(data, target_raw)

    if not target_raw.startswith("@"):
        send_message(
            chat_id,
            "❌ برای حمله باید یوزرنیم طرف رو با @ بنویسی.\n\n"
            f"مثلاً: {ability_name}.@user_2"
        )
        return

    if not target_id or target_id == sender_id:
        send_message(chat_id, "❌ همچین یوزرنیمی پیدا نشد.")
        return

    target = ensure_fighter(data, target_id)

    if not target or not target.get("selected_character"):
        send_message(chat_id, "❌ این کاربر هنوز شخصیتی انتخاب نکرده، نمی‌تونی بهش حمله کنی.")
        return

    target_name = display_name(target, target_id)

    if not target.get("fight_alive", True):
        send_message(chat_id, f"❌ {target_name} از قبل مرده. برای فایت بعدی صبر کن.")
        return

    target_char = get_character(data, target["selected_character"])
    ability_type = ability.get("type")

    if ability_type == "damage":

        amount = ability.get("amount", 0)
        target["fight_hp"] = max(0, target.get("fight_hp", 0) - amount)

        msg = (
            f"🩸 {amount} تا از HP {target_name} کم شد.\n"
            f"❤️ HP باقی‌مانده: {target['fight_hp']}"
        )

    elif ability_type == "stun":

        turns = ability.get("turns", 1)
        target["stunned_turns"] = turns

        msg = f"😵 {target_name} به مدت {turns} نوبت بیهوش/فلج شد."

    elif ability_type == "onetime":

        used = attacker.setdefault("used_onetime_abilities", [])

        if ability_name in used:
            send_message(
                chat_id,
                f"❌ تو قبلاً از قابلیت یک‌بار مصرفِ «{ability_name}» استفاده کرده‌ای."
            )
            return

        used.append(ability_name)

        if target_char and target_char.get("class") == "boss":
            half = target_char.get("hp", 0) // 2
            target["fight_hp"] = max(0, target.get("fight_hp", 0) - half)
            msg = (
                f"💥 {target_name} (باس) نصف HP‌اش رو از دست داد.\n"
                f"❤️ HP باقی‌مانده: {target['fight_hp']}"
            )
        else:
            target["fight_hp"] = 0
            msg = f"💥 {target_name} با یه ضربه از پا در اومد!"

    else:
        send_message(chat_id, "❌ نوع این قابلیت شناخته‌شده نیست.")
        return

    if target["fight_hp"] <= 0 and target.get("fight_alive", True):

        target["fight_alive"] = False
        msg += f"\n💀 {target_name} مرد!"

        data.setdefault("_kill_log", []).append({
            "killer_id": sender_id,
            "victim_id": target_id,
            "processed": False
        })

    save_all(data)
    send_message(chat_id, msg)


# =========================================================
# GET UPDATES
# =========================================================

def get_updates(offset=None):

    payload = {"limit": 10}

    if offset:
        payload["offset_id"] = offset

    try:
        response = requests.post(f"{API_URL}/getUpdates", json=payload, timeout=30)

        try:
            return response.json()
        except ValueError:
            print("❌ جواب getUpdates (هارلی) JSON نبود:")
            print("کد وضعیت HTTP:", response.status_code)
            print("متن خام:", response.text[:300])
            return {}

    except Exception as e:
        if is_network_error(e):
            print("📡 قطعی موقت شبکه در getUpdates (هارلی):", e)
        else:
            print("❌ خطا در getUpdates (هارلی):")
            print(e)
        return {}


# =========================================================
# MAIN LOOP
# =========================================================

def run():

    global offset_id

    print("\n======================================")
    print("🥷 Harley Sawyer Bot")
    print("======================================")
    print("📌 Offset:", offset_id)

    MIN_RETRY_DELAY = 3
    MAX_RETRY_DELAY = 30
    retry_delay = MIN_RETRY_DELAY

    while True:

        try:
            result = get_updates(offset_id)

            if not result:
                print(f"⏳ {retry_delay} ثانیه صبر و تلاش دوباره...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
                continue

            if result.get("status") != "OK":
                print("❌ API ERROR (هارلی):")
                print(result)
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
                continue

            retry_delay = MIN_RETRY_DELAY

            data_wrap = result.get("data", {})
            updates = data_wrap.get("updates", [])
            next_offset = data_wrap.get("next_offset_id")

            if next_offset:
                offset_id = next_offset
                save_offset(offset_id)

            for update in updates:
                print("\n📨 NEW UPDATE (Harley):")
                print(update)

                if update.get("type") == "NewMessage":
                    handle_message(update)

            time.sleep(0.3)

        except KeyboardInterrupt:
            print("\n🛑 Harley Sawyer stopped.")
            break

        except Exception as e:
            if is_network_error(e):
                print("📡 قطعی موقت شبکه در حلقهٔ اصلی (هارلی):", e)
            else:
                print("❌ MAIN LOOP ERROR (هارلی):")
                print(e)

            print(f"⏳ {retry_delay} ثانیه صبر و تلاش دوباره...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)


if __name__ == "__main__":
    run()
