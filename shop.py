from rubibot.types import (
    ChatKeypad,
    KeypadRow,
    KeypadSimpleButton
)

import main_test as core  # به send_message ،users ،save_users و ... از main_test.py دسترسی می‌دهد


# =========================================================
# STORAGE
# =========================================================
# برخلاف نسخهٔ قبلی، اینجا هیچ فایل جداگانه‌ای (مثل characters.json
# یا shop_settings.json) ساخته نمی‌شه. شخصیت‌ها و تنظیمات شاپ زیر دو
# کلید مخصوص، داخل همون دیکشنری users (و در نتیجه همون users.json)
# نگه داشته می‌شن. این دو خط فقط یه اشارهٔ (reference) به همون
# دیکشنری‌های داخل core.users هستن، پس هر تغییری روشون بدیم خودکار
# روی core.users هم اعمال می‌شه و با core.save_users() ذخیره می‌شه.

CHAR_KEY = "_shop_characters"
SETTINGS_KEY = "_shop_settings"

if CHAR_KEY not in core.users:
    core.users[CHAR_KEY] = {}

if SETTINGS_KEY not in core.users:
    core.users[SETTINGS_KEY] = {"characters_locked": False}

characters = core.users[CHAR_KEY]
shop_settings = core.users[SETTINGS_KEY]


def save_characters():
    core.save_users()


def save_settings():
    core.save_users()


def is_locked():
    return shop_settings.get("characters_locked", False)


# =========================================================
# KEYBOARDS
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
# CHARACTER HELPERS
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
# ADMIN: ADD CHARACTER FLOW
# =========================================================

def start_add_character(chat_id, admin_id):
    core.admin_states[admin_id] = {"state": "shop_newchar_name"}

    core.send_message(
        chat_id,
        "➕ افزودن شخصیت جدید\n\n"
        "اسم شخصیت را وارد کن.\n\n"
        "مثلاً:\n"
        "Huggy Wuggy"
    )


def handle_admin_state(chat_id, admin_id, text):
    """
    وضعیت‌های چندمرحله‌ایِ مربوط به شاپ را مدیریت می‌کند.
    اگر متعلق به شاپ نبود False برمی‌گرداند تا bot.py ادامه بدهد.
    """

    state_data = core.admin_states.get(admin_id)

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
            core.send_message(chat_id, "❌ اسم نمی‌تواند خالی باشد.")
            return True

        core.admin_states[admin_id] = {
            "state": "shop_newchar_hp",
            "name": name
        }

        core.send_message(
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
            core.send_message(chat_id, "❌ HP باید فقط عدد باشد.\n\nمثلاً:\n50")
            return True

        if hp <= 0:
            core.send_message(chat_id, "❌ HP باید بیشتر از صفر باشد.")
            return True

        state_data["state"] = "shop_newchar_code"
        state_data["hp"] = hp

        core.send_message(
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
            core.send_message(chat_id, "❌ کد باید دقیقاً ۴ رقم باشد.\n\nمثلاً:\n5665")
            return True

        if code in characters:
            core.send_message(
                chat_id,
                "❌ این کد قبلاً برای شخصیت دیگری استفاده شده.\n\n"
                "یک کد دیگر وارد کن:"
            )
            return True

        state_data["state"] = "shop_newchar_pt"
        state_data["code"] = code

        core.send_message(
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
            core.send_message(chat_id, "❌ مقدار PT باید فقط عدد باشد.\n\nمثلاً:\n1000")
            return True

        if price <= 0:
            core.send_message(chat_id, "❌ مقدار PT باید بیشتر از صفر باشد.")
            return True

        state_data["state"] = "shop_newchar_class"
        state_data["price"] = price

        core.send_message(
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
            core.send_message(
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
            core.send_message(chat_id, "❌ فقط عدد بفرست (بین ۱ تا ۵).")
            return True

        if not (1 <= n <= 5):
            core.send_message(chat_id, "❌ تعداد قابلیت باید بین ۱ تا ۵ باشد.")
            return True

        state_data["state"] = "shop_newchar_ability_name"
        state_data["ability_count"] = n
        state_data["abilities"] = []

        core.send_message(
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
            core.send_message(chat_id, "❌ اسم قابلیت نمی‌تواند خالی باشد.")
            return True

        state_data["state"] = "shop_newchar_ability_type"
        state_data["pending_ability"] = {"name": name}

        core.send_message(
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
            core.send_message(
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
            core.send_message(chat_id, "❌ فقط عدد بفرست.")
            return True

        if turns <= 0:
            core.send_message(chat_id, "❌ عدد باید بیشتر از صفر باشد.")
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
            core.send_message(chat_id, "❌ فقط عدد بفرست.")
            return True

        if amount <= 0:
            core.send_message(chat_id, "❌ عدد باید بیشتر از صفر باشد.")
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
            core.admin_states.pop(admin_id, None)
            core.send_message(chat_id, "🚫 ساخت شخصیت لغو شد.", shop_admin_menu_keyboard())
            return True

        core.send_message(
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

        core.admin_states.pop(admin_id, None)

        if not ch:
            core.send_message(
                chat_id,
                "❌ شخصیتی با این کد پیدا نشد.",
                shop_admin_menu_keyboard()
            )
            return True

        save_characters()

        core.send_message(
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

    core.send_message(
        chat_id,
        "✨ این شخصیت چند تا قابلیت داره؟ (بین ۱ تا ۵)"
    )


def _set_ability_type(chat_id, admin_id, state_data, t):

    pending = state_data["pending_ability"]
    pending["type"] = t

    if t == "stun":
        state_data["state"] = "shop_newchar_ability_stun_turns"
        core.send_message(
            chat_id,
            f"😵 «{pending['name']}» چند نوبت طرف رو بیهوش/فلج می‌کنه؟\n\n"
            "یه عدد بفرست."
        )

    elif t == "damage":
        state_data["state"] = "shop_newchar_ability_damage"
        core.send_message(
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

        core.send_message(
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

        core.send_message(
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

    core.admin_states.pop(admin_id, None)

    core.send_message(
        chat_id,
        "✅ شخصیت با موفقیت ثبت شد. 🎉\n\n"
        f"{format_character(characters[code])}",
        shop_admin_menu_keyboard()
    )


# =========================================================
# ADMIN: BUTTON-LEVEL MENU
# =========================================================

def handle_admin_button(chat_id, admin_id, text, button_id):
    """
    دکمه‌های سطح منوی شاپ (نه وضعیت‌های چندمرحله‌ای) را مدیریت می‌کند.
    """

    if button_id == "shop_admin_menu" or text == "🎭 مدیریت شاپ":
        core.admin_states.pop(admin_id, None)
        core.send_message(
            chat_id,
            "🎭 مدیریت شاپ Love Stitch Bot",
            shop_admin_menu_keyboard()
        )
        return True

    if button_id == "shop_admin_back" or text == "🔙 بازگشت به پنل":
        core.admin_states.pop(admin_id, None)
        core.send_message(chat_id, "👑 پنل مدیریت Love Stitch Bot", core.admin_keyboard())
        return True

    if button_id == "shop_admin_add" or text == "➕ افزودن شخصیت":
        start_add_character(chat_id, admin_id)
        return True

    if button_id == "shop_admin_list" or text == "📋 لیست شخصیت‌ها":
        core.admin_states.pop(admin_id, None)
        _show_character_list(chat_id)
        return True

    if button_id == "shop_admin_delete" or text == "❌ حذف شخصیت":
        core.admin_states[admin_id] = {"state": "shop_delete_character"}
        core.send_message(chat_id, "🔢 کد شخصیتی که می‌خواهی حذف کنی را بفرست:")
        return True

    # کلاس شخصیت (Player / Mini Huggy / Boss) هنگام ساخت شخصیت
    if button_id in ("class_player", "class_mini_huggy", "class_boss"):
        state_data = core.admin_states.get(admin_id)
        if state_data and state_data.get("state") == "shop_newchar_class":
            cls = button_id.split("class_", 1)[1]
            _proceed_to_ability_count(chat_id, admin_id, state_data, cls)
            return True

    # نوع قابلیت (بیهوش / یک‌بار مصرف / دمیج) هنگام ساخت شخصیت
    if button_id in ("ability_type_stun", "ability_type_onetime", "ability_type_damage"):
        state_data = core.admin_states.get(admin_id)
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

        core.send_message(
            chat_id,
            f"✅ امکان انتخاب/تغییر شخصیت توسط کاربران {status}.",
            shop_admin_menu_keyboard()
        )
        return True

    # دکمه‌های بله/نه ممکن است هنگام تایید ساخت شخصیت هم برسند
    if button_id in ("shop_confirm_yes", "shop_confirm_no"):
        state_data = core.admin_states.get(admin_id)
        if state_data and state_data.get("state") == "shop_newchar_confirm":
            if button_id == "shop_confirm_yes":
                _save_new_character(chat_id, admin_id, state_data)
            else:
                core.admin_states.pop(admin_id, None)
                core.send_message(chat_id, "🚫 ساخت شخصیت لغو شد.", shop_admin_menu_keyboard())
            return True

    return False


def _show_character_list(chat_id):

    if not characters:
        core.send_message(
            chat_id,
            "📋 هنوز هیچ شخصیتی ساخته نشده.",
            shop_admin_menu_keyboard()
        )
        return

    text = "📋 شخصیت‌های شاپ:\n\n"

    for code, ch in characters.items():
        text += f"🔢 کد: {code}\n{format_character(ch)}\n\n"

    core.send_message(chat_id, text, shop_admin_menu_keyboard())


# =========================================================
# USER: ENTER SHOP
# =========================================================

def enter_shop(chat_id, user_id):
    core.user_states.pop(user_id, None)

    core.send_message(
        chat_id,
        "🛒 به شاپ Love Stitch Bot خوش آمدید.\n\n"
        "از گزینه‌های زیر انتخاب کنید:",
        shop_main_keyboard()
    )


# =========================================================
# USER: BUTTON-LEVEL (شخصیت جدید / شخصیت موجود / برگشتن / انتخاب)
# =========================================================

def handle_user_button(chat_id, user_id, text, button_id):

    if button_id == "shop_back_main" or text == "🔙 برگشتن":
        core.user_states.pop(user_id, None)
        core.send_message(chat_id, "👋 به منوی اصلی برگشتی.", core.user_keyboard())
        return True

    if button_id == "shop_new_character" or text == "🆕 شخصیت جدید":
        core.user_states[user_id] = {"state": "shop_buy_code"}
        core.send_message(chat_id, "🔢 کد شخصیت را وارد کنید.")
        return True

    if button_id == "shop_my_characters" or text == "🎭 شخصیت موجود":
        core.user_states.pop(user_id, None)
        _show_characters(chat_id, user_id)
        return True

    if button_id and button_id.startswith("shop_select_"):
        code = button_id.split("shop_select_", 1)[1]
        _select_character(chat_id, user_id, code)
        return True

    if button_id in ("shop_confirm_yes", "shop_confirm_no"):
        state_data = core.user_states.get(user_id)
        if state_data and state_data.get("state") == "shop_buy_confirm":
            if button_id == "shop_confirm_yes":
                _finalize_purchase(chat_id, user_id, state_data)
            else:
                core.user_states.pop(user_id, None)
                core.send_message(chat_id, "🚫 خرید لغو شد.", shop_main_keyboard())
            return True

    return False


def _show_characters(chat_id, user_id):

    owned = core.users.get(user_id, {}).get("characters", [])

    if not owned:
        core.send_message(
            chat_id,
            "🎭 هنوز هیچ شخصیتی نخریدی.",
            shop_main_keyboard()
        )
        return

    core.send_message(
        chat_id,
        "🎭 شخصیت‌های شما:",
        characters_keyboard(owned)
    )


def _select_character(chat_id, user_id, code):

    if is_locked():
        core.send_message(
            chat_id,
            "🔒 در حال حاضر امکان انتخاب یا تغییر شخصیت بسته است.",
            shop_main_keyboard()
        )
        return

    owned = core.users.get(user_id, {}).get("characters", [])

    if code not in owned:
        core.send_message(
            chat_id,
            "❌ این شخصیت جزو شخصیت‌های خریداری‌شدهٔ تو نیست.",
            shop_main_keyboard()
        )
        return

    ch = characters.get(code)

    if not ch:
        core.send_message(
            chat_id,
            "❌ اطلاعات این شخصیت دیگر در دسترس نیست.",
            shop_main_keyboard()
        )
        return

    core.users[user_id]["selected_character"] = code
    core.save_users()

    core.send_message(
        chat_id,
        f"🥳 تبریک! شخصیت شما با موفقیت انتخاب شد: {ch['name']}",
        back_keyboard()
    )


# =========================================================
# USER: MULTI-STEP STATES (کد خرید / تایید خرید)
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

    owned = core.users.get(user_id, {}).get("characters", [])

    if code in owned:
        core.user_states.pop(user_id, None)
        core.send_message(
            chat_id,
            f"ℹ️ تو قبلاً شخصیت «{ch['name']}» را خریده‌ای.",
            shop_main_keyboard()
        )
        return True

    core.user_states[user_id] = {
        "state": "shop_buy_confirm",
        "code": code
    }

    core.send_message(
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
    main_test.py این رو درست قبل از پیام fallback صدا می‌زنه.
    """

    code = text.strip()

    if not (code.isdigit() and len(code) == 4):
        return False

    return _handle_buy_code_input(chat_id, user_id, code)


def handle_user_state(chat_id, user_id, text):

    state_data = core.user_states.get(user_id)

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

        core.send_message(
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
            core.user_states.pop(user_id, None)
            core.send_message(chat_id, "🚫 خرید لغو شد.", shop_main_keyboard())
            return True

        core.send_message(
            chat_id,
            "❌ متوجه نشدم. یکی از دکمه‌های زیر را انتخاب کن.",
            yes_no_keyboard()
        )
        return True

    return False


def _finalize_purchase(chat_id, user_id, state_data):

    code = state_data.get("code")
    ch = characters.get(code)

    core.user_states.pop(user_id, None)

    if not ch:
        core.send_message(
            chat_id,
            "❌ این شخصیت دیگر در دسترس نیست.",
            shop_main_keyboard()
        )
        return

    if user_id not in core.users:
        core.send_message(
            chat_id,
            "❌ اطلاعات کاربری تو پیدا نشد.",
            shop_main_keyboard()
        )
        return

    user = core.users[user_id]
    current_pt = user.get("pt", 0)
    price = ch["price"]

    if current_pt < price:
        core.send_message(
            chat_id,
            f"❌ موجودی کافی نیست!\n\n"
            f"💰 موجودی فعلی: {current_pt} PT\n"
            f"💸 قیمت شخصیت: {price} PT",
            shop_main_keyboard()
        )
        return

    owned = user.setdefault("characters", [])

    if code in owned:
        core.send_message(
            chat_id,
            f"ℹ️ تو قبلاً شخصیت «{ch['name']}» را خریده‌ای.",
            shop_main_keyboard()
        )
        return

    user["pt"] = current_pt - price
    owned.append(code)

    core.save_users()

    core.send_message(
        chat_id,
        f"✅ شخصیت «{ch['name']}» خریداری شد.\n\n"
        f"💰 موجودی جدید: {user['pt']} PT",
        back_keyboard()
        )
