from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Основная клавиатура
def main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👤 Профиль")],
        [KeyboardButton(text="➕ Добавить Игру"), KeyboardButton(text="❌ Удалить Игру")],
        [KeyboardButton(text="💰 Проверить цены"), KeyboardButton(text="🔔 Обновления"), KeyboardButton(text="⚙️ Настройка валют")],
        [KeyboardButton(text="🆘 Поддержка")],
    ], resize_keyboard=True)

# Кнопка проверки цены
def get_price_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Проверить цены", callback_data="check_prices")]
    ])

# Клавиатура для удаления игры
def get_remove_game_keyboard(games):
    buttons = [
        [InlineKeyboardButton(text=f"❌ {game_id}", callback_data=f"remove_game_{game_id}")]
        for game_id in games
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)




def get_currency_keyboard(user_id, user_settings):
    if user_id not in user_settings:
        user_settings[user_id] = {"RU", "KZ"}  # Если нет настроек, ставим RU и KZ по умолчанию

    selected_currencies = user_settings[user_id]

    buttons = []
    available_currencies = {
        "RU": "🇷🇺 RUB",
        "KZ": "🇰🇿 KZT",
        "UA": "🇺🇦 UAH",
        "CN": "🇨🇳 CNY",
        "EU": "🇪🇺 EUR",
        "US": "🇺🇸 USD",
        "PL": "🇵🇱 PLN",
    }

    for code, label in available_currencies.items():
        is_selected = "✅" if code in selected_currencies else "❌"
        buttons.append([InlineKeyboardButton(text=f"{is_selected} {label}", callback_data=f"toggle_currency_{code}")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
