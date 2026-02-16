import asyncio
import logging
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile
import os

# import ssl
# ssl._create_default_https_context = ssl._create_unverified_context

# --- Настройки ---
TOKEN = "8589591783:AAEO2xphzRV66TCH_P5mJAqVpGyKgBvnySQ"  # токен
ADMIN_ID = 0  # Укажи свой Telegram ID для ограничения доступа

# --- Создаем бота ---
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO)

# --- Работа с базой данных SQLite ---
def init_db():
    """Создание таблиц в базе данных"""
    conn = sqlite3.connect('debtor.db')
    cur = conn.cursor()
    
    # Таблица для болезней
    cur.execute('''
        CREATE TABLE IF NOT EXISTS sickness (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица для долгов (когда просит в долг)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            reason TEXT,
            date TEXT DEFAULT CURRENT_DATE,
            is_repaid BOOLEAN DEFAULT 0
        )
    ''')
    
    # Таблица для возвратов денег
    cur.execute('''
        CREATE TABLE IF NOT EXISTS repayments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            date TEXT DEFAULT CURRENT_DATE,
            comment TEXT
        )
    ''')
    
    # Таблица для общих заметок
    cur.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_text TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# --- Класс для состояний (FSM) ---
class AddSickness(StatesGroup):
    start_date = State()
    end_date = State()
    description = State()

class AddDebt(StatesGroup):
    amount = State()
    reason = State()

class AddRepayment(StatesGroup):
    amount = State()
    comment = State()

class AddNote(StatesGroup):
    text = State()

# --- Клавиатуры ---
def main_keyboard():
    buttons = [
        [KeyboardButton(text="🤒 Добавить болезнь")],
        [KeyboardButton(text="💰 Добавить долг")],
        [KeyboardButton(text="💵 Добавить возврат")],
        [KeyboardButton(text="📝 Добавить заметку")],
        [KeyboardButton(text="📊 Выгрузить статистику")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

# --- Проверка доступа ---
async def check_access(message: types.Message):
    if ADMIN_ID != 0 and message.from_user.id != ADMIN_ID:
        await message.answer("Извини, этот бот только для личного использования.")
        return False
    return True

# --- Обработчики команд и кнопок ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if not await check_access(message):
        return
    await message.answer(
        "Привет! Это бот для учёта проделок твоего друга-лудомана.\n"
        "Выбери действие:",
        reply_markup=main_keyboard()
    )

@dp.message(F.text == "❌ Отмена")
async def cancel_handler(message: types.Message, state: FSMContext):
    """Отмена любого действия"""
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_keyboard())

# --- Добавление болезни ---
@dp.message(F.text == "🤒 Добавить болезнь")
async def add_sickness_start(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    await state.set_state(AddSickness.start_date)
    await message.answer(
        "Введи дату начала болезни (в формате ДД.ММ.ГГГГ):\n"
        "Например: 25.01.2024",
        reply_markup=cancel_keyboard()
    )

@dp.message(AddSickness.start_date)
async def add_sickness_start_date(message: types.Message, state: FSMContext):
    try:
        # Проверка формата даты
        datetime.strptime(message.text, "%d.%m.%Y")
        await state.update_data(start_date=message.text)
        await state.set_state(AddSickness.end_date)
        await message.answer("Введи дату окончания болезни (в формате ДД.ММ.ГГГГ):")
    except ValueError:
        await message.answer("Неверный формат даты. Попробуй ещё раз или нажми 'Отмена'.")

@dp.message(AddSickness.end_date)
async def add_sickness_end_date(message: types.Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%d.%m.%Y")
        await state.update_data(end_date=message.text)
        await state.set_state(AddSickness.description)
        await message.answer("Введи описание (что случилось, какие симптомы и т.д.) или отправь '-' если без описания:")
    except ValueError:
        await message.answer("Неверный формат даты. Попробуй ещё раз или нажми 'Отмена'.")

@dp.message(AddSickness.description)
async def add_sickness_description(message: types.Message, state: FSMContext):
    data = await state.get_data()
    desc = None if message.text == '-' else message.text
    
    conn = sqlite3.connect('debtor.db')
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sickness (start_date, end_date, description) VALUES (?, ?, ?)",
        (data['start_date'], data['end_date'], desc)
    )
    conn.commit()
    conn.close()
    
    await state.clear()
    await message.answer(
        f"✅ Запись о болезни добавлена!\n"
        f"Период: {data['start_date']} - {data['end_date']}",
        reply_markup=main_keyboard()
    )

# --- Добавление долга ---
@dp.message(F.text == "💰 Добавить долг")
async def add_debt_start(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    await state.set_state(AddDebt.amount)
    await message.answer(
        "Введи сумму долга (только число, например: 1500 или 500.50):",
        reply_markup=cancel_keyboard()
    )

@dp.message(AddDebt.amount)
async def add_debt_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
        await state.update_data(amount=amount)
        await state.set_state(AddDebt.reason)
        await message.answer("Введи причину (на что просил) или отправь '-' если без причины:")
    except ValueError:
        await message.answer("Неверный формат суммы. Введи число (например, 1500 или 500.50).")

@dp.message(AddDebt.reason)
async def add_debt_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    reason = None if message.text == '-' else message.text
    
    conn = sqlite3.connect('debtor.db')
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO debts (amount, reason) VALUES (?, ?)",
        (data['amount'], reason)
    )
    conn.commit()
    conn.close()
    
    await state.clear()
    await message.answer(
        f"✅ Запись о долге добавлена!\n"
        f"Сумма: {data['amount']} руб.\n"
        f"Причина: {reason if reason else 'не указана'}",
        reply_markup=main_keyboard()
    )

# --- Добавление возврата ---
@dp.message(F.text == "💵 Добавить возврат")
async def add_repayment_start(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    await state.set_state(AddRepayment.amount)
    await message.answer(
        "Введи сумму возврата (только число):",
        reply_markup=cancel_keyboard()
    )

@dp.message(AddRepayment.amount)
async def add_repayment_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
        await state.update_data(amount=amount)
        await state.set_state(AddRepayment.comment)
        await message.answer("Введи комментарий (за какой период, примечание) или '-' если без комментария:")
    except ValueError:
        await message.answer("Неверный формат суммы. Введи число.")

@dp.message(AddRepayment.comment)
async def add_repayment_comment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    comment = None if message.text == '-' else message.text
    
    conn = sqlite3.connect('debtor.db')
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO repayments (amount, comment) VALUES (?, ?)",
        (data['amount'], comment)
    )
    conn.commit()
    conn.close()
    
    await state.clear()
    await message.answer(
        f"✅ Возврат зафиксирован!\n"
        f"Сумма: {data['amount']} руб.",
        reply_markup=main_keyboard()
    )

# --- Добавление заметки ---
@dp.message(F.text == "📝 Добавить заметку")
async def add_note_start(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    await state.set_state(AddNote.text)
    await message.answer(
        "Введи текст заметки (любую информацию о его проделках):",
        reply_markup=cancel_keyboard()
    )

@dp.message(AddNote.text)
async def add_note_text(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('debtor.db')
    cur = conn.cursor()
    cur.execute("INSERT INTO notes (note_text) VALUES (?)", (message.text,))
    conn.commit()
    conn.close()
    
    await state.clear()
    await message.answer("✅ Заметка сохранена!", reply_markup=main_keyboard())

# --- Выгрузка статистики ---
@dp.message(F.text == "📊 Выгрузить статистику")
async def get_statistics(message: types.Message):
    if not await check_access(message):
        return
    
    conn = sqlite3.connect('debtor.db')
    cur = conn.cursor()
    
    # Собираем данные
    result = "📁 СТАТИСТИКА ПО ДРУГУ-ЛУДОМАНУ\n"
    result += "=" * 40 + "\n\n"
    
    # 1. Общие заметки
    cur.execute("SELECT created_at, note_text FROM notes ORDER BY created_at DESC")
    notes = cur.fetchall()
    result += "📝 ПОСЛЕДНИЕ ЗАМЕТКИ:\n"
    if notes:
        for created, note in notes[:10]:  # последние 10
            result += f"• [{created}] {note}\n"
    else:
        result += "• Нет заметок\n"
    result += "\n"
    
    # 2. Болезни
    cur.execute("SELECT start_date, end_date, description FROM sickness ORDER BY start_date DESC")
    sickness = cur.fetchall()
    result += "🤒 ИСТОРИЯ БОЛЕЗНЕЙ:\n"
    if sickness:
        for start, end, desc in sickness[:15]:  # последние 15
            desc_text = f" - {desc}" if desc else ""
            result += f"• {start} - {end}{desc_text}\n"
    else:
        result += "• Нет записей о болезнях\n"
    result += "\n"
    
    # 3. Долги
    cur.execute("SELECT amount, reason, date FROM debts WHERE is_repaid = 0 ORDER BY date DESC")
    debts = cur.fetchall()
    result += "💰 ТЕКУЩИЕ ДОЛГИ:\n"
    total_debt = 0
    if debts:
        for amount, reason, date in debts:
            reason_text = f" ({reason})" if reason else ""
            result += f"• {date}: {amount} руб.{reason_text}\n"
            total_debt += amount
    else:
        result += "• Нет активных долгов\n"
    result += f"ИТОГО ДОЛЖЕН: {total_debt} руб.\n\n"
    
    # 4. Возвраты
    cur.execute("SELECT amount, date, comment FROM repayments ORDER BY date DESC")
    repayments = cur.fetchall()
    result += "💵 ИСТОРИЯ ВОЗВРАТОВ:\n"
    total_repaid = 0
    if repayments:
        for amount, date, comment in repayments[:15]:
            comment_text = f" - {comment}" if comment else ""
            result += f"• {date}: {amount} руб.{comment_text}\n"
            total_repaid += amount
    else:
        result += "• Нет возвратов\n"
    result += f"ВСЕГО ВОЗВРАЩЕНО: {total_repaid} руб.\n\n"
    
    # 5. Итоговый баланс
    cur.execute("SELECT SUM(amount) FROM debts")
    all_debts_sum = cur.fetchone()[0] or 0
    
    result += "📊 СВОДКА:\n"
    result += f"• Общая сумма взятых в долг: {all_debts_sum} руб.\n"
    result += f"• Общая сумма возвратов: {total_repaid} руб.\n"
    result += f"• ОСТАТОК ДОЛГА: {all_debts_sum - total_repaid} руб.\n"
    
    conn.close()
    
    # Сохраняем результат во временный файл
    filename = f"stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(filename, 'w', encoding='utf-8-sig') as f:
        f.write(result)
    
    # Отправляем файл
    await message.answer_document(
        FSInputFile(filename),
        caption="Вот полная статистика по другу.",
        reply_markup=main_keyboard()
    )
    
    # Удаляем временный файл
    os.remove(filename)

# --- Запуск бота ---
async def main():
    init_db()
    print("Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())