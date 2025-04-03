import asyncio
import aiohttp
import re
import os
import sys
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message
from config import TOKEN, ADMIN_ID, SUPPORT_CHAT_ID
from keyboards import main_keyboard, get_price_button, get_remove_game_keyboard, get_currency_keyboard
from collections import Counter
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Храним игры для каждого пользователя
user_games = {}
# Храним состояние пользователя (ожидает ли он ввода после кнопки)
user_states = {}
# Храним сообщения в поддержку
support_messages = []
# Словарь для хранения настроек валют пользователей
user_settings = {}

async def set_bot_commands():
    commands = [
        types.BotCommand(command="/start", description="Запустить бота"),
        types.BotCommand(command="/restart", description="Перезапустить бота"),
    ]
    await bot.set_my_commands(commands)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await set_bot_commands()  # Устанавливаем команды
    await dp.start_polling(bot)

# Функция для получения отчета для админа
async def get_admin_report():
    total_users = len(user_games)
    total_games = sum(len(games) for games in user_games.values())
    most_added_games = Counter(game for games in user_games.values() for game in games).most_common(5)

    report = (
        f"📝 *Отчет по боту*\n\n"
        f"👥 Пользователей: {total_users}\n"
        f"🎮 Игр в системе: {total_games}\n"
        f"📩 Сообщений в поддержку: {len(support_messages)}\n"
        f"\n🔥 *Часто добавляемые игры:*"
    )
    for game, count in most_added_games:
        game_name, _, _, _ = await get_price(game)
        report += f"\n{game_name} - {count} раз(а)"
    return report

# Команда /report для администратора
@dp.message(F.text == "/report")
async def report(message: Message):
    if message.from_user.id != ADMIN_ID:
        return  # Если не администратор, игнорируем команду
    report = await get_admin_report()
    await message.answer(report, parse_mode="Markdown")

# Функция для получения цены из Steam Store API
async def get_price(appid, user_id):
    currencies = user_settings.get(user_id, {"RU", "KZ"})  # По умолчанию RU и KZ
    price_data = {}
    discount_data = {}  # Словарь скидок по валютам

    async with aiohttp.ClientSession() as session:
        for currency in currencies:
            url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc={currency.lower()}"
            async with session.get(url) as resp:
                data = await resp.json()

            if str(appid) in data and data[str(appid)].get("success", False):
                game_data = data[str(appid)]["data"]
                price_overview = game_data.get("price_overview", {})

                price = price_overview.get("final", 0) / 100
                discount = price_overview.get("discount_percent", 0)

                price_data[currency] = price
                discount_data[currency] = discount  # Сохраняем скидку для конкретной валюты

    game_name = data[str(appid)]["data"].get("name", "Неизвестная игра") if data else "Неизвестная игра"
    return game_name, price_data, discount_data




url_pattern = r"https://store\.steampowered\.com/app/(\d+)"

@dp.message(F.text == "/start")
async def start(message: Message):
    user_games[message.from_user.id] = user_games.get(message.from_user.id, [])
    user_states.pop(message.from_user.id, None)  # Сбрасываем состояние
    await message.answer("Добавь игру по её AppID или ссылке Steam и проверяй цены.", reply_markup=main_keyboard())

# Команда /restart для перезапуска бота
@dp.message(F.text == "/restart")
async def restart(message: Message):
    # Проверяем, является ли пользователь администратором
    # if message.from_user.id != ADMIN_ID:
    #     return  # Если не администратор, игнорируем команду

    # Отправляем сообщение о перезапуске
    await message.answer("Бот перезапущен")

    # Перезапуск процесса
    os.execl(sys.executable, sys.executable, *sys.argv)

@dp.message(F.text == "➕ Добавить Игру")
async def add_game_prompt(message: Message):
    user_states[message.from_user.id] = "waiting_for_game_id"
    await message.answer("Отправьте AppID игры или ссылку на Steam, чтобы добавить игру.")

@dp.message(F.text.regexp(r"^\d+$"))
async def add_game_by_id(message: Message):
    user_id = message.from_user.id
    if user_states.get(user_id) != "waiting_for_game_id":
        return  # Игнорируем сообщение, если бот его не ждал

    appid = int(message.text)
    user_games.setdefault(user_id, [])

    if appid in user_games[user_id]:
        await message.answer("Эта игра уже добавлена!")
    else:
        user_games[user_id].append(appid)
        await message.answer("Игра добавлена!", reply_markup=main_keyboard())
    user_states.pop(user_id, None)  # Сбрасываем состояние

@dp.message(F.text.regexp(url_pattern))
async def add_game_by_url(message: Message):
    user_id = message.from_user.id
    if user_states.get(user_id) != "waiting_for_game_id":
        return

    match = re.match(url_pattern, message.text)
    if match:
        appid = int(match.group(1))
        user_games.setdefault(user_id, [])

        if appid in user_games[user_id]:
            await message.answer("Эта игра уже добавлена!")
        else:
            user_games[user_id].append(appid)
            await message.answer("Игра добавлена!", reply_markup=main_keyboard())
    user_states.pop(user_id, None)

@dp.message(F.text == "❌ Удалить Игру")
async def remove_game_prompt(message: Message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)
    if not user_games.get(user_id, []):
        await message.answer("У вас нет добавленных игр.")
        return

    keyboard = get_remove_game_keyboard(user_games[user_id])
    await message.answer("Выберите игру для удаления:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("remove_game_"))
async def remove_game(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    game_id = int(callback.data.split("_")[2])  # Получаем ID игры

    if user_id in user_games and game_id in user_games[user_id]:
        user_games[user_id].remove(game_id)
        await callback.answer("✅ Игра удалена.")

        # Обновляем клавиатуру после удаления
        if user_games[user_id]:
            keyboard = get_remove_game_keyboard(user_games[user_id])
            await callback.message.edit_text("Выберите игру для удаления:", reply_markup=keyboard)
        else:
            await callback.message.edit_text("У вас больше нет добавленных игр.")
    else:
        await callback.answer("⚠️ Игра уже удалена или не найдена.", show_alert=True)

@dp.message(F.text == "💰 Проверить цены")
async def check_prices(message: Message):
    user_id = message.from_user.id

    if not user_games.get(user_id, []):
        await message.answer("У вас нет добавленных игр.")
        return

    response = "💰 *Актуальные цены на ваши игры:*\n"
    currency_flags = {
        "RU": "🇷🇺", "KZ": "🇰🇿",
        "UA": "🇺🇦", "CN": "🇨🇳",
        "EU": "🇪🇺", "US": "🇺🇸",
        "PL": "🇵🇱"
    }

    for appid in user_games[user_id]:
        game_name, price_data, discount_data = await get_price(appid, user_id)
        discount_text = None  # Будем хранить единственную скидку

        response += f"\n🎮 {game_name}\n\n"

        if price_data:
            for currency, price in price_data.items():
                flag = currency_flags.get(currency, "")
                response += f"{flag} {price:.2f} {currency}\n"

                # Берём первую найденную скидку (все скидки обычно одинаковые)
                if discount_text is None and currency in discount_data:
                    discount = discount_data[currency]
                    discount_text = f"💰 Скидка: {discount}%" if discount else "💰 Скидка: 0%"

            if discount_text:
                response += f"\n{discount_text}\n"  # Ставим скидку один раз после всех цен

        else:
            response += "⚠️ Не удалось получить цену\n"

    await message.answer(response, parse_mode="Markdown", reply_markup=get_price_button())

# Обработчик inline-кнопки "🔄 Проверить цены"
@dp.callback_query(F.data == "check_prices")
async def refresh_prices(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    if not user_games.get(user_id, []):
        await callback.answer("У вас нет добавленных игр.", show_alert=True)
        return

    response = "💰 *Актуальные цены на ваши игры:*\n"
    currency_flags = {
        "RU": "🇷🇺", "KZ": "🇰🇿",
        "UA": "🇺🇦", "CN": "🇨🇳",
        "EU": "🇪🇺", "US": "🇺🇸",
        "PL": "🇵🇱"
    }

    for appid in user_games[user_id]:
        game_name, price_data, discount_data = await get_price(appid, user_id)
        discount_text = None  # Будем хранить единственную скидку

        response += f"\n🎮 *{game_name}*\n"

        if price_data:
            for currency, price in price_data.items():
                flag = currency_flags.get(currency, "")
                response += f"{flag} {price:.2f} {currency}\n"

                # Берём первую найденную скидку (все скидки обычно одинаковые)
                if discount_text is None and currency in discount_data:
                    discount = discount_data[currency]
                    discount_text = f"💰 Скидка: {discount}%" if discount else "💰 Скидка: 0%"

            if discount_text:
                response += f"{discount_text}\n"  # Ставим скидку один раз после всех цен

        else:
            response += "⚠️ Не удалось получить цену\n"

    new_text = response.strip()

    # Проверяем, изменился ли текст перед обновлением сообщения
    if callback.message.text.strip() != new_text:
        await callback.message.edit_text(new_text, reply_markup=get_price_button())
        await callback.answer("Цены обновлены ✅", show_alert=True)
    else:
        await callback.answer("Цены не изменились ✅", show_alert=True)



@dp.message(F.text == "👤 Профиль")
async def profile(message: Message):
    user_id = message.from_user.id  # Получаем ID пользователя
    games_list = user_games.get(user_id, [])

    response = f"👤 Ваш профиль:\n\n"

    if not games_list:
        response += "Пусто! \nДобавь игры через нужный раздел.\n"
    else:
        response += "Ваши добавленные игры:\n"
        for game_id in games_list:
            game_name, _, _ = await get_price(game_id, user_id)  # Убираем лишнее распаковку
            response += f"🎮 {game_name}\n"
    await message.answer(response, reply_markup=main_keyboard())

@dp.message(F.text == "🆘 Поддержка")
async def support_start(message: Message):
    user_states[message.from_user.id] = "waiting_for_support_message"
    await message.answer("🆘 Напишите ваш вопрос или проблему, и мы свяжемся с вами.")

@dp.message(F.text == "⚙️ Настройка валют")
async def settings(message: Message):
    await message.answer("Выберите валюты для отображения цен:\n              ⚠️Укажите хотя-бы 1⚠️\n", reply_markup=get_currency_keyboard(message.from_user.id, user_settings))

@dp.callback_query(F.data.startswith("currency_"))
async def change_currency(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    currency = callback.data.split("_")[1]  # Получаем код валюты

    # Инициализируем настройки, если их нет
    if user_id not in user_settings:
        user_settings[user_id] = {"RU", "KZ"}  # По умолчанию RU и KZ

    # Переключение состояния валюты (вкл/выкл)
    if currency in user_settings[user_id]:
        user_settings[user_id].remove(currency)
    else:
        user_settings[user_id].add(currency)

    await callback.answer("Настройки обновлены ✅", show_alert=True)
    await callback.message.edit_text("Выберите валюты для отображения цен:", reply_markup=get_currency_keyboard(user_id))

@dp.callback_query(F.data.startswith("toggle_currency_"))
async def toggle_currency(call: types.CallbackQuery):
    user_id = call.from_user.id
    currency_code = call.data.split("_")[-1]  # Получаем код валюты (например, "RU", "KZ")

    if user_id not in user_settings:
        user_settings[user_id] = {"RU", "KZ"}  # Значения по умолчанию

    if currency_code in user_settings[user_id]:
        user_settings[user_id].remove(currency_code)
    else:
        user_settings[user_id].add(currency_code)

    await call.message.edit_reply_markup(reply_markup=get_currency_keyboard(user_id, user_settings))
    await call.answer()  # Закрывает "часики" у пользователя


@dp.message(F.text == "🔔 Обновления")
async def show_updates(message: Message):
    updates_text = (
        "🆕 *Что нового в боте?*\n\n"
        "✅ Теперь можно добавлять игры не только по AppID, но и по ссылке!\n"
        "✅ Добавлена настройка актуальных регионов для цен.\n"
        "✅ Добавлена эта кнопка 'Обновления', чтобы следить за нововведениями.\n"
        "✅ Улучшена проверка актуальных цен и скидок.\n"
        "✅ Оптимизация процессов.\n"
        "\n🔥 Следите за обновлениями!"
    )
    await message.answer(updates_text, parse_mode="Markdown")







@dp.callback_query(F.data.startswith("toggle_currency_"))
async def toggle_currency(call: types.CallbackQuery):
    logging.info(f"Нажата кнопка: {call.data}")

@dp.message()
async def handle_unexpected_messages(message: Message):
    user_id = message.from_user.id

    if user_states.get(user_id) == "waiting_for_support_message":
        # Отправляем сообщение в поддержку
        support_message = f"📩 Сообщение в поддержку от {message.from_user.full_name} (@{message.from_user.username}):\n\n{message.text}"
        support_messages.append(support_message)
        await bot.send_message(SUPPORT_CHAT_ID, support_message)

        # Ответ пользователю
        await message.answer("✅ Ваше сообщение отправлено в поддержку.")
        user_states.pop(user_id, None)
        return

    # Не удаляем сообщение, если оно в контексте
    await message.answer("Я не понимаю это сообщение. Пожалуйста, следуйте инструкциям.")
    await message.delete()
if __name__ == "__main__":
    asyncio.run(main())