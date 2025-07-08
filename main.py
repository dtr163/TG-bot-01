#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram-бот для сбора жалоб на водителей
Автор: Manus AI
Версия: 2.1 - Исправленная версия без ошибок
"""

import asyncio
import logging
import re
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict, field

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    InputMediaPhoto, InputMediaDocument, InputMediaVideo,
    Contact
)

# Импорт модуля обработки текста
from text_processor import TextProcessor

# Настройки бота
BOT_TOKEN = "7557858368:AAGTBY7345zhffvucjj0RImZo11joyYrg8M"
CHANNEL_ID = -1002847094335  # ID канала (исправлено: int, с -100)
ADMIN_ID = 864497192  # Telegram ID админа (исправлено: int)
ADMIN_USERNAME = "tdr_763"  # Username админа для ссылки "Возразить"

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Инициализация процессора текста
text_processor = TextProcessor()

# Состояния FSM
class ComplaintStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_name = State()
    waiting_for_position = State()
    waiting_for_contact = State()
    waiting_for_date = State()
    waiting_for_location = State()
    waiting_for_description = State()
    waiting_for_violation_category = State()
    waiting_for_positive_aspects = State()
    waiting_for_fired_status = State()
    waiting_for_rating = State()
    waiting_for_files = State()
    waiting_for_confirmation = State()

# Состояния для редактирования админом
class AdminEditStates(StatesGroup):
    editing_name = State()
    editing_position = State()
    editing_contact = State()
    editing_date = State()
    editing_location = State()
    editing_description = State()
    editing_rating = State()

# Новое состояние для причины отклонения
class AdminRejectStates(StatesGroup):
    waiting_for_rejection_reason = State()

# Структура данных жалобы
@dataclass
class Complaint:
    user_id: int
    photo_file_id: Optional[str] = None
    driver_name: str = ""
    position: str = ""
    contact_info: str = ""
    incident_date: str = ""
    location: str = ""
    description: str = ""
    violation_categories: List[str] = field(default_factory=list)
    positive_aspects: List[str] = field(default_factory=list)
    fired_status: str = ""
    rating: int = 0
    additional_files: list = field(default_factory=list)
    created_at: str = ""
    auto_assessment: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Хранилище жалоб и черновиков
complaints_storage: Dict[int, Complaint] = {}
drafts_storage: Dict[int, Complaint] = {}
editing_storage: Dict[int, int] = {}  # admin_id -> complaint_id для отслеживания редактирования
admin_reject_storage: Dict[int, int] = {} # admin_id -> complaint_id для отслеживания отклонения

# Константы для выбора (исправлено: убраны лишние должности)
POSITIONS = [
    "🚛 Водитель тягача",
    "📦 Логист",
    "👔 Менеджер",
    "🔧 Механик",
    "📋 Диспетчер"
]

VIOLATION_CATEGORIES = [
    "🚫 Хамство",
    "⛽ Слив топлива", 
    "🕒 Прогул",
    "📦 Кража груза",
    "🚗 Нарушение ПДД",
    "🍺 Алкогольное опьянение",
    "🚭 Курение в салоне",
    "📱 Разговор по телефону",
    "⏰ Опоздание",
    "💰 Вымогательство"
]

POSITIVE_ASPECTS = [
    "😊 Вежливость",
    "⏰ Пунктуальность",
    "🛡️ Безопасность вождения",
    "🧹 Чистота транспорта",
    "💬 Хорошее общение",
    "🎯 Профессионализм",
    "🤝 Помощь пассажирам",
    "📋 Знание маршрута",
    "🔧 Техническая грамотность",
    "💪 Ответственность"
]

# Функции для обработки текста
def process_description_text(text: str) -> Dict[str, any]:
    """Обработка описания жалобы"""
    return text_processor.process_complaint_text(text, max_length=1000)

def auto_assess_complaint(complaint: Complaint) -> str:
    """Автоматическая оценка жалобы ИИ"""
    score = 0
    
    # Проверяем полноту данных
    if complaint.driver_name and len(complaint.driver_name) > 5:
        score += 1
    
    if complaint.contact_info:
        score += 1
    
    if complaint.description and len(complaint.description) > 50:
        score += 2
    elif complaint.description and len(complaint.description) > 20:
        score += 1
    
    if complaint.violation_categories:
        score += 1
    
    if complaint.location and len(complaint.location) > 10:
        score += 1
    
    # Определяем оценку
    if score >= 5:
        return "🟢 Подробно"
    elif score >= 3:
        return "🟡 Поверхностно" 
    else:
        return "🔴 Мало данных"

def validate_complaint(complaint: Complaint) -> tuple[bool, str]:
    """Проверка полноты данных жалобы"""
    issues = []
    
    if not complaint.driver_name:
        issues.append("Не указано ФИО")
    
    if not complaint.contact_info:
        issues.append("Не указан контакт")
    
    if not complaint.incident_date:
        issues.append("Не указана дата инцидента")
    
    if not complaint.location:
        issues.append("Не указано место происшествия")
    
    if not complaint.description or len(complaint.description.strip()) < 10:
        issues.append("Описание слишком короткое или отсутствует")
    
    if complaint.rating < 0 or complaint.rating > 10:
        issues.append("Некорректная оценка")
    
    if issues:
        return False, "⚠️ Требует уточнений:\n" + "\n".join(f"• {issue}" for issue in issues)
    
    return True, "✅ Данные полные"

# Клавиатуры
def get_start_keyboard():
    """Стартовая клавиатура"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Подать жалобу")],
            [KeyboardButton(text="📄 Мои черновики"), KeyboardButton(text="ℹ️ Информация")],
            [KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_repeat_keyboard():
    """Клавиатура после успешной отправки жалобы (исправлено: отдельная функция)"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📨 Отправить ещё жалобу")],
            [KeyboardButton(text="📄 Мои черновики"), KeyboardButton(text="ℹ️ Информация")],
            [KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_position_keyboard():
    """Клавиатура выбора должности"""
    buttons = []
    for i in range(0, len(POSITIONS), 2):
        row = [InlineKeyboardButton(text=POSITIONS[i], callback_data=f"pos_{i}")]
        if i + 1 < len(POSITIONS):
            row.append(InlineKeyboardButton(text=POSITIONS[i + 1], callback_data=f"pos_{i + 1}"))
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="pos_manual")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_contact_keyboard():
    """Клавиатура для ввода контакта"""
    # Удалена кнопка "Поделиться контактом" и "Ввести номер вручную"
    return types.ReplyKeyboardRemove()

def get_violation_categories_keyboard(selected_categories: Optional[List[str]] = None) -> InlineKeyboardMarkup:
    """Клавиатура выбора категорий нарушений"""
    if selected_categories is None:
        selected_categories = []
    
    buttons = []
    for i in range(0, len(VIOLATION_CATEGORIES), 2):
        row = []
        for j in range(2):
            if i + j < len(VIOLATION_CATEGORIES):
                category = VIOLATION_CATEGORIES[i + j]
                text = f"✅ {category}" if category in selected_categories else category
                row.append(InlineKeyboardButton(
                    text=text, 
                    callback_data=f"viol_{i + j}"
                ))
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton(text="➡️ Продолжить", callback_data="viol_continue")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_positive_aspects_keyboard(selected_aspects: Optional[List[str]] = None) -> InlineKeyboardMarkup:
    """Клавиатура выбора положительных моментов"""
    if selected_aspects is None:
        selected_aspects = []
    
    buttons = []
    for i in range(0, len(POSITIVE_ASPECTS), 2):
        row = []
        for j in range(2):
            if i + j < len(POSITIVE_ASPECTS):
                aspect = POSITIVE_ASPECTS[i + j]
                text = f"✅ {aspect}" if aspect in selected_aspects else aspect
                row.append(InlineKeyboardButton(
                    text=text,
                    callback_data=f"pos_asp_{i + j}"
                ))
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton(text="➡️ Продолжить", callback_data="pos_asp_continue")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_fired_status_keyboard():
    """Клавиатура для статуса увольнения"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="fired_yes")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="fired_no")],
            [InlineKeyboardButton(text="❓ Неизвестно", callback_data="fired_unknown")]
        ]
    )
    return keyboard

def get_files_keyboard():
    """Клавиатура для дополнительных файлов"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📎 Добавить файлы", callback_data="add_files")],
            [InlineKeyboardButton(text="➡️ Продолжить без файлов", callback_data="skip_files")]
        ]
    )
    return keyboard

def get_confirmation_keyboard():
    """Клавиатура подтверждения"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ СОГЛАСЕН", callback_data="confirm_complaint")],
            [InlineKeyboardButton(text="💾 Сохранить в черновики", callback_data="save_draft")]
        ]
    )
    return keyboard

def get_edit_keyboard(complaint_id: int):
    """Клавиатура для редактирования жалобы админом"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Изменить ФИО", callback_data=f"edit_name_{complaint_id}")],
            [InlineKeyboardButton(text="💼 Изменить должность", callback_data=f"edit_position_{complaint_id}")],
            [InlineKeyboardButton(text="📞 Изменить контакт", callback_data=f"edit_contact_{complaint_id}")],
            [InlineKeyboardButton(text="📅 Изменить дату", callback_data=f"edit_date_{complaint_id}")],
            [InlineKeyboardButton(text="📍 Изменить место", callback_data=f"edit_location_{complaint_id}")],
            [InlineKeyboardButton(text="📖 Изменить описание", callback_data=f"edit_description_{complaint_id}")],
            [InlineKeyboardButton(text="📊 Изменить оценку", callback_data=f"edit_rating_{complaint_id}")],
            [InlineKeyboardButton(text="✅ Завершить редактирование", callback_data=f"finish_edit_{complaint_id}")],
            [InlineKeyboardButton(text="❌ Отменить редактирование", callback_data=f"cancel_edit_{complaint_id}")]
        ]
    )
    return keyboard

def get_admin_keyboard(complaint_id: int):
    """Клавиатура для админа (исправлено: убрана лишняя кнопка)"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"admin_approve_{complaint_id}")],
            [InlineKeyboardButton(text="❌ Отклонить без причины", callback_data=f"admin_reject_no_reason_{complaint_id}")],
            [InlineKeyboardButton(text="❌ Отклонить с причиной", callback_data=f"admin_reject_with_reason_{complaint_id}")],
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin_edit_{complaint_id}")]
        ]
    )
    return keyboard

def get_drafts_keyboard(user_id: int):
    """Клавиатура для работы с черновиками"""
    if user_id in drafts_storage:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📝 Продолжить черновик", callback_data="continue_draft")],
                [InlineKeyboardButton(text="🗑️ Удалить черновик", callback_data="delete_draft")]
            ]
        )
    else:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📝 Создать новую жалобу", callback_data="new_complaint")]
            ]
        )
    return keyboard

# Обработчики команд
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    welcome_text = """
🤖 Добро пожаловать в бот для подачи жалоб!

Этот бот поможет вам анонимно подать жалобу на сотрудника. 
Все данные будут проверены администратором перед публикацией.

🔒 Ваша анонимность гарантирована - никакие личные данные не сохраняются и не публикуются.

Выберите действие:
"""
    
    await message.answer(welcome_text, reply_markup=get_start_keyboard())

@dp.message(F.text == "📝 Подать жалобу")
async def start_complaint(message: types.Message, state: FSMContext):
    """Начало процесса подачи жалобы"""
    user_id = message.from_user.id
    
    # Создаем новую жалобу
    complaints_storage[user_id] = Complaint(user_id=user_id)
    
    await message.answer(
        "📸 Шаг 1/11: Отправьте фото сотрудника или транспорта\n\n"
        "Это поможет идентифицировать нарушителя. Фото обязательно для подачи жалобы.",
        reply_markup=types.ReplyKeyboardRemove()
    )
    
    await state.set_state(ComplaintStates.waiting_for_photo)

# Исправлено: добавлен обработчик кнопки "📨 Отправить ещё жалобу"
@dp.message(F.text == "📨 Отправить ещё жалобу")
async def start_another_complaint(message: types.Message, state: FSMContext):
    """Начало новой жалобы после успешной отправки предыдущей"""
    await start_complaint(message, state)

@dp.message(F.text == "📄 Мои черновики")
async def show_drafts(message: types.Message):
    """Показ черновиков пользователя"""
    user_id = message.from_user.id
    
    if user_id in drafts_storage:
        draft = drafts_storage[user_id]
        draft_text = f"""
📄 У вас есть сохраненный черновик:

👤 ФИО: {draft.driver_name or 'не указано'}
💼 Должность: {draft.position or 'не указана'}
📞 Контакт: {draft.contact_info or 'не указан'}
📅 Дата: {draft.incident_date or 'не указана'}
📍 Место: {draft.location or 'не указано'}

Создан: {draft.created_at}
"""
        await message.answer(draft_text, reply_markup=get_drafts_keyboard(user_id))
    else:
        await message.answer(
            "📄 У вас нет сохраненных черновиков.\n\n"
            "Начните создание новой жалобы:",
            reply_markup=get_drafts_keyboard(user_id)
        )

@dp.callback_query(F.data == "continue_draft")
async def continue_draft(callback: types.CallbackQuery, state: FSMContext):
    """Продолжение работы с черновиком"""
    user_id = callback.from_user.id
    
    if user_id in drafts_storage:
        # Перемещаем черновик в активные жалобы
        complaints_storage[user_id] = drafts_storage[user_id]
        del drafts_storage[user_id]
        
        # Исправлено: используем answer вместо edit_text для безопасности
        await callback.message.answer(
            "📝 Черновик загружен! Продолжаем с того места, где остановились.\n\n"
            "Проверьте данные и продолжите заполнение.",
            reply_markup=types.ReplyKeyboardRemove()  # Убираем клавиатуру для чистоты
        )
        await callback.message.delete()
        
        # Определяем, на каком этапе остановились и продолжаем
        complaint = complaints_storage[user_id]
        
        if not complaint.photo_file_id:
            await callback.message.answer("📸 Шаг 1/11: Отправьте фото сотрудника или транспорта:")
            await state.set_state(ComplaintStates.waiting_for_photo)
        elif not complaint.driver_name:
            await callback.message.answer("👤 Шаг 2/11: Укажите ФИО сотрудника:")
            await state.set_state(ComplaintStates.waiting_for_name)
        elif not complaint.position:
            await callback.message.answer("💼 Шаг 3/11: Выберите должность сотрудника:", reply_markup=get_position_keyboard())
            await state.set_state(ComplaintStates.waiting_for_position)
        elif not complaint.contact_info:
            await callback.message.answer("📞 Шаг 4/11: Укажите контактную информацию сотрудника:\n\nПример: +7 900 123-45-67 или Таб.№12345", reply_markup=get_contact_keyboard())
            await state.set_state(ComplaintStates.waiting_for_contact)
        elif not complaint.incident_date:
            await callback.message.answer("📅 Шаг 5/11: Укажите дату инцидента:")
            await state.set_state(ComplaintStates.waiting_for_date)
        elif not complaint.location:
            await callback.message.answer("📍 Шаг 6/11: Укажите место происшествия:")
            await state.set_state(ComplaintStates.waiting_for_location)
        elif not complaint.description:
            await callback.message.answer("📖 Шаг 7/11: Опишите ситуацию подробно:")
            await state.set_state(ComplaintStates.waiting_for_description)
        elif not complaint.violation_categories:
            await callback.message.answer("🚫 Шаг 8/11: Выберите категории нарушений:", reply_markup=get_violation_categories_keyboard())
            await state.set_state(ComplaintStates.waiting_for_violation_category)
        elif not complaint.positive_aspects:
            await callback.message.answer("😊 Шаг 9/11: Выберите положительные качества сотрудника:", reply_markup=get_positive_aspects_keyboard())
            await state.set_state(ComplaintStates.waiting_for_positive_aspects)
        elif not complaint.fired_status:
            await callback.message.answer("❌ Шаг 10/11: Был ли сотрудник уволен?", reply_markup=get_fired_status_keyboard())
            await state.set_state(ComplaintStates.waiting_for_fired_status)
        elif not complaint.rating:
            await callback.message.answer("📊 Шаг 11/11: Оцените сотрудника от 0 до 10:")
            await state.set_state(ComplaintStates.waiting_for_rating)
        elif not complaint.additional_files:
            await callback.message.answer("📎 Дополнительные файлы:", reply_markup=get_files_keyboard())
            await state.set_state(ComplaintStates.waiting_for_files)
        else:
            # Если все поля заполнены, переходим к подтверждению
            await show_confirmation(callback.message, state)

@dp.callback_query(F.data == "delete_draft")
async def delete_draft(callback: types.CallbackQuery):
    """Удаление черновика"""
    user_id = callback.from_user.id
    
    if user_id in drafts_storage:
        del drafts_storage[user_id]
        # Исправлено: используем answer + delete вместо edit_text и добавляем клавиатуру
        await callback.message.answer(
            "🗑️ Черновик удален.",
            reply_markup=get_start_keyboard()  # Добавляем клавиатуру для возврата в меню
        )
        await callback.message.delete()
    
    await callback.answer()

@dp.callback_query(F.data == "new_complaint")
async def new_complaint_from_callback(callback: types.CallbackQuery, state: FSMContext):
    """Создание новой жалобы из callback"""
    user_id = callback.from_user.id
    
    complaints_storage[user_id] = Complaint(user_id=user_id)
    
    # Исправлено: используем answer + delete вместо edit_text
    await callback.message.answer(
        "📸 Шаг 1/11: Отправьте фото сотрудника или транспорта\n\n"
        "Это поможет идентифицировать нарушителя. Фото обязательно для подачи жалобы.",
        reply_markup=types.ReplyKeyboardRemove()  # Убираем клавиатуру для чистоты
    )
    await callback.message.delete()
    
    await state.set_state(ComplaintStates.waiting_for_photo)
    await callback.answer()

# Обработка фото
@dp.message(ComplaintStates.waiting_for_photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    """Обработка фото"""
    user_id = message.from_user.id
    
    if user_id in complaints_storage:
        photo = message.photo[-1]
        complaints_storage[user_id].photo_file_id = photo.file_id
        
        await message.answer(
            "✅ Фото получено!\n\n"
            "👤 Шаг 2/11: Укажите ФИО сотрудника\n\n"
            "Пример: Иванов Иван Иванович"
        )
        
        await state.set_state(ComplaintStates.waiting_for_name)
    else:
        await message.answer("❌ Ошибка. Начните сначала с команды /start")

# Обработка ФИО
@dp.message(ComplaintStates.waiting_for_name, F.text)
async def process_name(message: types.Message, state: FSMContext):
    """Обработка ФИО"""
    user_id = message.from_user.id
    
    if user_id in complaints_storage:
        name = message.text.strip()
        if len(name) < 3:
            await message.answer("❌ ФИО слишком короткое. Попробуйте еще раз:")
            return
        
        complaints_storage[user_id].driver_name = name
        
        await message.answer(
            f"✅ ФИО записано!\n\n"
            "💼 Шаг 3/11: Выберите должность сотрудника:",
            reply_markup=get_position_keyboard()
        )
        
        await state.set_state(ComplaintStates.waiting_for_position)
    else:
        await message.answer("❌ Ошибка. Начните сначала с команды /start")

# Обработка выбора должности
@dp.callback_query(ComplaintStates.waiting_for_position)
async def process_position(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора должности"""
    user_id = callback.from_user.id
    
    if user_id in complaints_storage:
        if callback.data.startswith("pos_"):
            if callback.data == "pos_manual":
                # Исправлено: используем answer + delete вместо edit_text
                await callback.message.answer("✏️ Введите должность вручную:")
                await callback.message.delete()
                return
            
            try:
                pos_index = int(callback.data.split("_")[1])
                position = POSITIONS[pos_index]
                complaints_storage[user_id].position = position
                
                # Исправлено: используем answer + delete вместо edit_text
                await callback.message.answer(
                    f"✅ Должность выбрана: {position}\n\n"
                    "📞 Шаг 4/11: Укажите контактную информацию сотрудника\n\n"
                    "Пример: +7 900 123-45-67 или Таб.№12345",
                    reply_markup=get_contact_keyboard()
                )
                await callback.message.delete()
                
                await state.set_state(ComplaintStates.waiting_for_contact)
                
            except (ValueError, IndexError):
                await callback.answer("❌ Ошибка выбора должности")
        
    await callback.answer()

# Обработка должности вручную
@dp.message(ComplaintStates.waiting_for_position, F.text)
async def process_position_manual(message: types.Message, state: FSMContext):
    """Обработка ввода должности вручную"""
    user_id = message.from_user.id
    
    if user_id in complaints_storage:
        position = message.text.strip()
        if len(position) < 2:
            await message.answer("❌ Должность слишком короткая. Попробуйте еще раз:")
            return
        
        complaints_storage[user_id].position = position
        
        await message.answer(
            f"✅ Должность записана: {position}\n\n"
            "📞 Шаг 4/11: Укажите контактную информацию сотрудника\n\n"
            "Пример: +7 900 123-45-67 или Таб.№12345",
            reply_markup=get_contact_keyboard()
        )
        
        await state.set_state(ComplaintStates.waiting_for_contact)
    else:
        await message.answer("❌ Ошибка. Начните сначала с команды /start")

# Обработка контакта
# Удален обработчик F.contact

# Удален @dp.message(ComplaintStates.waiting_for_contact, F.text == "✏️ Ввести номер вручную")
# async def process_contact_manual_request(message: types.Message, state: FSMContext):
#     """Запрос ввода номера вручную"""
#     await message.answer(
#         "📞 Введите номер телефона или другую контактную информацию:\n\n"
#         "Пример: +7 900 123-45-67 или Таб.№12345",
#         reply_markup=types.ReplyKeyboardRemove()
#     )

@dp.message(ComplaintStates.waiting_for_contact, F.text)
async def process_contact_manual(message: types.Message, state: FSMContext):
    """Обработка ввода контакта вручную"""
    user_id = message.from_user.id
    
    if user_id in complaints_storage:
        contact_info = message.text.strip()
        if len(contact_info) < 5:
            await message.answer("❌ Контактная информация слишком короткая. Попробуйте еще раз:")
            return
        
        complaints_storage[user_id].contact_info = contact_info
        
        await message.answer(
            f"✅ Контакт записан: {contact_info}\n\n"
            "📅 Шаг 5/11: Укажите дату инцидента\n\n"
            "Пример: 06.07.2025 или вчера, сегодня"
        )
        
        await state.set_state(ComplaintStates.waiting_for_date)
    else:
        await message.answer("❌ Ошибка. Начните сначала с команды /start")

# Обработка даты
@dp.message(ComplaintStates.waiting_for_date, F.text)
async def process_date(message: types.Message, state: FSMContext):
    """Обработка даты"""
    user_id = message.from_user.id
    
    if user_id in complaints_storage:
        date_text = message.text.strip()
        
        # Простая обработка относительных дат
        if date_text.lower() in ['сегодня', 'today']:
            date_text = datetime.now().strftime("%d.%m.%Y")
        elif date_text.lower() in ['вчера', 'yesterday']:
            from datetime import timedelta
            yesterday = datetime.now() - timedelta(days=1)
            date_text = yesterday.strftime("%d.%m.%Y")
        
        complaints_storage[user_id].incident_date = date_text
        
        await message.answer(
            "✅ Дата записана!\n\n"
            "📍 Шаг 6/11: Укажите место происшествия\n\n"
            "Пример: Москва, ул. Тверская, д.1 или Санкт-Петербург, Невский проспект"
        )
        
        await state.set_state(ComplaintStates.waiting_for_location)
    else:
        await message.answer("❌ Ошибка. Начните сначала с команды /start")

# Обработка места
@dp.message(ComplaintStates.waiting_for_location, F.text)
async def process_location(message: types.Message, state: FSMContext):
    """Обработка места"""
    user_id = message.from_user.id
    
    if user_id in complaints_storage:
        location = message.text.strip()
        if len(location) < 5:
            await message.answer("❌ Место слишком короткое. Укажите город и адрес:")
            return
        
        complaints_storage[user_id].location = location
        
        await message.answer(
            "✅ Место записано!\n\n"
            "📖 Шаг 7/11: Опишите ситуацию подробно\n\n"
            "Максимум 1000 символов. Избегайте нецензурной лексики.\n"
            "Опишите что произошло, как вел себя сотрудник, какие были нарушения."
        )
        
        await state.set_state(ComplaintStates.waiting_for_description)
    else:
        await message.answer("❌ Ошибка. Начните сначала с команды /start")

# Обработка описания (исправлено: БЕЗ уведомления об изменениях)
@dp.message(ComplaintStates.waiting_for_description, F.text)
async def process_description(message: types.Message, state: FSMContext):
    """Обработка описания"""
    user_id = message.from_user.id
    
    if user_id in complaints_storage:
        description = message.text.strip()
        
        if len(description) < 10:
            await message.answer("❌ Описание слишком короткое. Опишите ситуацию подробнее:")
            return
        
        if len(description) > 1000:
            await message.answer(f"❌ Описание слишком длинное ({len(description)} символов). Максимум 1000. Сократите:")
            return
        
        # Обрабатываем текст ТИХО (без уведомления пользователя)
        processing_result = process_description_text(description)
        processed_description = processing_result['processed_text']
        
        # Сохраняем обработанное описание
        complaints_storage[user_id].description = processed_description
        
        # Простое подтверждение БЕЗ упоминания обработки
        await message.answer(
            "✅ Описание записано!\n\n"
            "🚫 Шаг 8/11: Выберите категории нарушений\n\n"
            "Можете выбрать несколько категорий:",
            reply_markup=get_violation_categories_keyboard()
        )
        
        await state.set_state(ComplaintStates.waiting_for_violation_category)
    else:
        await message.answer("❌ Ошибка. Начните сначала с команды /start")

# Обработка категорий нарушений
@dp.callback_query(ComplaintStates.waiting_for_violation_category)
async def process_violation_category(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора категорий нарушений"""
    user_id = callback.from_user.id
    
    if user_id in complaints_storage:
        complaint = complaints_storage[user_id]
        
        if callback.data == "viol_continue":
            if not complaint.violation_categories:
                await callback.answer("⚠️ Выберите хотя бы одну категорию нарушения")
                return
            
            # Исправлено: используем answer + delete вместо edit_text
            await callback.message.answer(
                f"✅ Выбрано категорий: {len(complaint.violation_categories)}\n\n"
                "😊 Шаг 9/11: Выберите положительные качества сотрудника\n\n"
                "Это поможет дать объективную оценку:",
                reply_markup=get_positive_aspects_keyboard()
            )
            await callback.message.delete()
            
            await state.set_state(ComplaintStates.waiting_for_positive_aspects)
            
        elif callback.data.startswith("viol_"):
            try:
                viol_index = int(callback.data.split("_")[1])
                category = VIOLATION_CATEGORIES[viol_index]
                
                if category in complaint.violation_categories:
                    complaint.violation_categories.remove(category)
                else:
                    complaint.violation_categories.append(category)
                
                # Обновляем клавиатуру
                await callback.message.edit_reply_markup(
                    reply_markup=get_violation_categories_keyboard(complaint.violation_categories)
                )
                
            except (ValueError, IndexError):
                await callback.answer("❌ Ошибка выбора категории")
    
    await callback.answer()

# Обработка положительных моментов
@dp.callback_query(ComplaintStates.waiting_for_positive_aspects)
async def process_positive_aspects(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора положительных моментов"""
    user_id = callback.from_user.id
    
    if user_id in complaints_storage:
        complaint = complaints_storage[user_id]
        
        if callback.data == "pos_asp_continue":
            # Исправлено: используем answer + delete вместо edit_text
            await callback.message.answer(
                f"✅ Выбрано положительных качеств: {len(complaint.positive_aspects)}\n\n"
                "❌ Шаг 10/11: Был ли сотрудник уволен?\n\n"
                "Выберите один из вариантов:",
                reply_markup=get_fired_status_keyboard()
            )
            await callback.message.delete()
            
            await state.set_state(ComplaintStates.waiting_for_fired_status)
            
        elif callback.data.startswith("pos_asp_"):
            try:
                asp_index = int(callback.data.split("_")[2])
                aspect = POSITIVE_ASPECTS[asp_index]
                
                if aspect in complaint.positive_aspects:
                    complaint.positive_aspects.remove(aspect)
                else:
                    complaint.positive_aspects.append(aspect)
                
                # Обновляем клавиатуру
                await callback.message.edit_reply_markup(
                    reply_markup=get_positive_aspects_keyboard(complaint.positive_aspects)
                )
                
            except (ValueError, IndexError):
                await callback.answer("❌ Ошибка выбора качества")
    
    await callback.answer()

# Обработка статуса увольнения
@dp.callback_query(ComplaintStates.waiting_for_fired_status)
async def process_fired_status(callback: types.CallbackQuery, state: FSMContext):
    """Обработка статуса увольнения"""
    user_id = callback.from_user.id
    
    if user_id in complaints_storage:
        status_map = {
            "fired_yes": "Да",
            "fired_no": "Нет", 
            "fired_unknown": "Неизвестно"
        }
        
        status = status_map.get(callback.data, "Неизвестно")
        complaints_storage[user_id].fired_status = status
        
        # Исправлено: используем answer + delete вместо edit_text
        await callback.message.answer(
            f"✅ Статус увольнения: {status}\n\n"
            "📊 Шаг 11/11: Оцените сотрудника от 0 до 10\n\n"
            "0 - ужасно, 10 - отлично\n"
            "Учтите выбранные положительные качества при оценке.\n"
            "Просто напишите цифру:"
        )
        await callback.message.delete()
        
        await state.set_state(ComplaintStates.waiting_for_rating)
        await callback.answer()
    else:
        await callback.answer("❌ Ошибка. Начните сначала с команды /start")

# Обработка оценки
@dp.message(ComplaintStates.waiting_for_rating, F.text)
async def process_rating(message: types.Message, state: FSMContext):
    """Обработка оценки"""
    user_id = message.from_user.id
    
    if user_id in complaints_storage:
        try:
            rating = int(message.text.strip())
            if rating < 0 or rating > 10:
                await message.answer("❌ Оценка должна быть от 0 до 10. Попробуйте еще раз:")
                return
            
            complaint = complaints_storage[user_id]
            complaint.rating = rating
            
            # Выполняем автооценку
            complaint.auto_assessment = auto_assess_complaint(complaint)
            
            await message.answer(
                f"✅ Оценка записана: {rating}/10\n"
                f"🤖 Автооценка жалобы: {complaint.auto_assessment}\n\n"
                "📎 Дополнительные файлы\n\n"
                "Вы можете приложить дополнительные фото, документы или видео для подтверждения жалобы.",
                reply_markup=get_files_keyboard()
            )
            
            await state.set_state(ComplaintStates.waiting_for_files)
            
        except ValueError:
            await message.answer("❌ Введите число от 0 до 10:")
    else:
        await message.answer("❌ Ошибка. Начните сначала с команды /start")

# Обработка файлов
@dp.callback_query(ComplaintStates.waiting_for_files)
async def process_files_choice(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора файлов"""
    if callback.data == "add_files":
        # Исправлено: используем answer + delete вместо edit_text
        await callback.message.answer(
            "📎 Отправьте дополнительные файлы:\n\n"
            "• Фото\n"
            "• Документы (PDF, DOC)\n"
            "• Видео\n\n"
            "Когда закончите, напишите 'готово'"
        )
        await callback.message.delete()
        await callback.answer()
    elif callback.data == "skip_files":
        await show_confirmation(callback.message, state)
        await callback.answer()

@dp.message(ComplaintStates.waiting_for_files, F.text)
async def process_files_done(message: types.Message, state: FSMContext):
    """Завершение добавления файлов"""
    if message.text.lower() in ['готово', 'done', 'готов']:
        await show_confirmation(message, state)

@dp.message(ComplaintStates.waiting_for_files, F.photo | F.document | F.video)
async def process_additional_files(message: types.Message, state: FSMContext):
    """Обработка дополнительных файлов"""
    user_id = message.from_user.id
    
    if user_id in complaints_storage:
        file_info = None
        
        if message.photo:
            file_info = {
                'type': 'photo',
                'file_id': message.photo[-1].file_id,
                'caption': message.caption or ''
            }
        elif message.document:
            file_info = {
                'type': 'document',
                'file_id': message.document.file_id,
                'filename': message.document.file_name or 'document',
                'caption': message.caption or ''
            }
        elif message.video:
            file_info = {
                'type': 'video',
                'file_id': message.video.file_id,
                'caption': message.caption or ''
            }
        
        if file_info:
            complaints_storage[user_id].additional_files.append(file_info)
            await message.answer(
                f"✅ Файл добавлен! Всего файлов: {len(complaints_storage[user_id].additional_files)}\n\n"
                "Отправьте еще файлы или напишите 'готово' для завершения."
            )

async def show_confirmation(message: types.Message, state: FSMContext):
    """Показ подтверждения"""
    confirmation_text = """
⚖️ ЮРИДИЧЕСКОЕ ПОДТВЕРЖДЕНИЕ

Я подтверждаю, что вся информация отправлена мной добровольно. Я принимаю полную юридическую и моральную ответственность за её содержание. Администрация бота и канала ответственности не несут.

⚠️ Внимание: Подача ложной информации может повлечь юридические последствия.

Выберите действие:
"""
    
    await message.answer(
        confirmation_text,
        reply_markup=get_confirmation_keyboard()
    )
    
    await state.set_state(ComplaintStates.waiting_for_confirmation)

@dp.callback_query(ComplaintStates.waiting_for_confirmation)
async def process_confirmation(callback: types.CallbackQuery, state: FSMContext):
    """Обработка подтверждения"""
    user_id = callback.from_user.id
    
    if callback.data == "confirm_complaint":
        if user_id in complaints_storage:
            complaint = complaints_storage[user_id]
            
            # Проверяем данные
            is_valid, validation_message = validate_complaint(complaint)
            
            # Исправлено: используем answer + delete вместо edit_text и показываем кнопку повтора
            await callback.message.answer(
                "✅ Жалоба принята!\n\n"
                "Ваша жалоба отправлена на модерацию. "
                "После проверки администратором она будет опубликована в канале.\n\n"
                "Спасибо за обращение!",
                reply_markup=get_repeat_keyboard()  # Исправлено: показываем кнопку повтора
            )
            await callback.message.delete()
            
            # Отправляем админу
            await send_to_admin(complaint, is_valid, validation_message)
            
            # Очищаем состояние
            await state.clear()
            
            await callback.answer("Жалоба отправлена на модерацию!")
        else:
            await callback.answer("❌ Ошибка. Начните сначала с команды /start")
    
    elif callback.data == "save_draft":
        if user_id in complaints_storage:
            # Сохраняем в черновики
            drafts_storage[user_id] = complaints_storage[user_id]
            del complaints_storage[user_id]
            
            # Исправлено: используем answer + delete вместо edit_text и добавляем кнопку возврата
            await callback.message.answer(
                "💾 Жалоба сохранена в черновики!\n\n"
                "Вы можете продолжить её заполнение позже через меню 'Мои черновики'.",
                reply_markup=get_start_keyboard()  # Добавляем клавиатуру для возврата в меню
            )
            await callback.message.delete()
            
            await state.clear()
            await callback.answer("Сохранено в черновики!")
        else:
            await callback.answer("❌ Ошибка сохранения")

async def send_to_admin(complaint: Complaint, is_valid: bool, validation_message: str):
    """Отправка жалобы админу"""
    try:
        # Формируем сообщение для админа
        categories_text = ", ".join(complaint.violation_categories) if complaint.violation_categories else "Не указаны"
        positive_text = ", ".join(complaint.positive_aspects) if complaint.positive_aspects else "Не указаны"
        
        admin_text = f"""
🔍 НОВАЯ ЖАЛОБА #{complaint.user_id}

👤 ФИО: {complaint.driver_name}
💼 Должность: {complaint.position}
📞 Контакт: {complaint.contact_info}
📅 Дата: {complaint.incident_date}
📍 Место: {complaint.location}
📖 Описание: {complaint.description}
🚫 Категории: {categories_text}
😊 Положительное: {positive_text}
❌ Уволен: {complaint.fired_status}
📊 Оценка: {complaint.rating}/10
🤖 Автооценка: {complaint.auto_assessment}
📎 Доп. файлы: {len(complaint.additional_files)} шт.

{validation_message}

Время подачи: {complaint.created_at}
"""
        
        # Исправлено: отправляем напрямую по ADMIN_ID (int)
        if complaint.photo_file_id:
            await bot.send_photo(
                chat_id=ADMIN_ID,
                photo=complaint.photo_file_id,
                caption=admin_text,
                reply_markup=get_admin_keyboard(complaint.user_id)
            )
        else:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_text,
                reply_markup=get_admin_keyboard(complaint.user_id)
            )
        
        # Отправляем дополнительные файлы
        if complaint.additional_files:
            media_group = []
            for i, file_info in enumerate(complaint.additional_files[:10]):
                if file_info['type'] == 'photo':
                    media_group.append(InputMediaPhoto(
                        media=file_info['file_id'],
                        caption=f"Доп. фото {i+1}" + (f": {file_info['caption']}" if file_info['caption'] else "")
                    ))
                elif file_info['type'] == 'document':
                    media_group.append(InputMediaDocument(
                        media=file_info['file_id'],
                        caption=f"Документ {i+1}" + (f": {file_info['caption']}" if file_info['caption'] else "")
                    ))
                elif file_info['type'] == 'video':
                    media_group.append(InputMediaVideo(
                        media=file_info['file_id'],
                        caption=f"Видео {i+1}" + (f": {file_info['caption']}" if file_info['caption'] else "")
                    ))
            
            if media_group:
                await bot.send_media_group(chat_id=ADMIN_ID, media=media_group)
        
        logger.info(f"Жалоба #{complaint.user_id} отправлена админу")
        
    except Exception as e:
        logger.error(f"Ошибка отправки админу: {e}")

# Обработчики редактирования админом
@dp.callback_query(F.data.startswith("edit_"))
async def process_edit_field(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора поля для редактирования"""
    try:
        admin_id = callback.from_user.id
        if admin_id != ADMIN_ID:
            await callback.answer("❌ Доступ запрещен")
            return
        
        parts = callback.data.split("_")
        field = parts[1]
        complaint_id = int(parts[2])
        
        if admin_id not in editing_storage or editing_storage[admin_id] != complaint_id:
            await callback.answer("❌ Сессия редактирования не найдена")
            return
        
        if complaint_id not in complaints_storage:
            await callback.answer("❌ Жалоба не найдена")
            return
        
        complaint = complaints_storage[complaint_id]
        
        if field == "name":
            await callback.message.answer(
                f"👤 Текущее ФИО: {complaint.driver_name}\n\n"
                "Введите новое ФИО:"
            )
            await state.set_state(AdminEditStates.editing_name)
            
        elif field == "position":
            await callback.message.answer(
                f"💼 Текущая должность: {complaint.position}\n\n"
                "Выберите новую должность:",
                reply_markup=get_position_keyboard()
            )
            await state.set_state(AdminEditStates.editing_position)
            
        elif field == "contact":
            await callback.message.answer(
                f"📞 Текущий контакт: {complaint.contact_info}\n\n"
                "Введите новый контакт:"
            )
            await state.set_state(AdminEditStates.editing_contact)
            
        elif field == "date":
            await callback.message.answer(
                f"📅 Текущая дата: {complaint.incident_date}\n\n"
                "Введите новую дату:"
            )
            await state.set_state(AdminEditStates.editing_date)
            
        elif field == "location":
            await callback.message.answer(
                f"📍 Текущее место: {complaint.location}\n\n"
                "Введите новое место:"
            )
            await state.set_state(AdminEditStates.editing_location)
            
        elif field == "description":
            await callback.message.answer(
                f"📖 Текущее описание: {complaint.description}\n\n"
                "Введите новое описание:"
            )
            await state.set_state(AdminEditStates.editing_description)
            
        elif field == "rating":
            await callback.message.answer(
                f"📊 Текущая оценка: {complaint.rating}/10\n\n"
                "Введите новую оценку (0-10):"
            )
            await state.set_state(AdminEditStates.editing_rating)
        
        await callback.message.delete()
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка редактирования поля: {e}")
        await callback.answer("❌ Ошибка редактирования")

@dp.callback_query(F.data.startswith("finish_edit_"))
async def finish_editing(callback: types.CallbackQuery, state: FSMContext):
    """Завершение редактирования"""
    try:
        admin_id = callback.from_user.id
        complaint_id = int(callback.data.split("_")[2])
        
        if admin_id in editing_storage:
            del editing_storage[admin_id]
        
        await state.clear()
        
        # Показываем обновленную жалобу
        complaint = complaints_storage[complaint_id]
        updated_text = f"""
✅ РЕДАКТИРОВАНИЕ ЗАВЕРШЕНО

Обновленные данные жалобы #{complaint_id}:
👤 ФИО: {complaint.driver_name}
💼 Должность: {complaint.position}
📞 Контакт: {complaint.contact_info}
📅 Дата: {complaint.incident_date}
📍 Место: {complaint.location}
📖 Описание: {complaint.description}
📊 Оценка: {complaint.rating}/10

Выберите действие:
"""
        
        await callback.message.answer(
            updated_text,
            reply_markup=get_admin_keyboard(complaint_id)
        )
        await callback.message.delete()
        await callback.answer("✅ Редактирование завершено")
        
    except Exception as e:
        logger.error(f"Ошибка завершения редактирования: {e}")
        await callback.answer("❌ Ошибка")

@dp.callback_query(F.data.startswith("cancel_edit_"))
async def cancel_editing(callback: types.CallbackQuery, state: FSMContext):
    """Отмена редактирования"""
    try:
        admin_id = callback.from_user.id
        complaint_id = int(callback.data.split("_")[2])
        
        if admin_id in editing_storage:
            del editing_storage[admin_id]
        
        await state.clear()
        
        await callback.message.answer(
            "❌ Редактирование отменено",
            reply_markup=get_admin_keyboard(complaint_id)
        )
        await callback.message.delete()
        await callback.answer("Отменено")
        
    except Exception as e:
        logger.error(f"Ошибка отмены редактирования: {e}")
        await callback.answer("❌ Ошибка")

# Обработчики ввода новых значений при редактировании
@dp.message(AdminEditStates.editing_name, F.text)
async def edit_name(message: types.Message, state: FSMContext):
    """Редактирование ФИО"""
    admin_id = message.from_user.id
    if admin_id not in editing_storage:
        await message.answer("❌ Сессия редактирования не найдена")
        return
    
    complaint_id = editing_storage[admin_id]
    new_name = message.text.strip()
    
    if len(new_name) < 3:
        await message.answer("❌ ФИО слишком короткое. Попробуйте еще раз:")
        return
    
    complaints_storage[complaint_id].driver_name = new_name
    await message.answer(
        f"✅ ФИО обновлено: {new_name}\n\n"
        "Выберите следующее поле для редактирования:",
        reply_markup=get_edit_keyboard(complaint_id)
    )
    await state.clear()

@dp.message(AdminEditStates.editing_contact, F.text)
async def edit_contact(message: types.Message, state: FSMContext):
    """Редактирование контакта"""
    admin_id = message.from_user.id
    if admin_id not in editing_storage:
        await message.answer("❌ Сессия редактирования не найдена")
        return
    
    complaint_id = editing_storage[admin_id]
    new_contact = message.text.strip()
    
    if len(new_contact) < 5:
        await message.answer("❌ Контактная информация слишком короткая. Попробуйте еще раз:")
        return
    
    complaints_storage[complaint_id].contact_info = new_contact
    await message.answer(
        f"✅ Контакт обновлен: {new_contact}\n\n"
        "Выберите следующее поле для редактирования:",
        reply_markup=get_edit_keyboard(complaint_id)
    )
    await state.clear()

@dp.message(AdminEditStates.editing_date, F.text)
async def edit_date(message: types.Message, state: FSMContext):
    """Редактирование даты"""
    admin_id = message.from_user.id
    if admin_id not in editing_storage:
        await message.answer("❌ Сессия редактирования не найдена")
        return
    
    complaint_id = editing_storage[admin_id]
    new_date = message.text.strip()
    
    complaints_storage[complaint_id].incident_date = new_date
    await message.answer(
        f"✅ Дата обновлена: {new_date}\n\n"
        "Выберите следующее поле для редактирования:",
        reply_markup=get_edit_keyboard(complaint_id)
    )
    await state.clear()

@dp.message(AdminEditStates.editing_location, F.text)
async def edit_location(message: types.Message, state: FSMContext):
    """Редактирование места"""
    admin_id = message.from_user.id
    if admin_id not in editing_storage:
        await message.answer("❌ Сессия редактирования не найдена")
        return
    
    complaint_id = editing_storage[admin_id]
    new_location = message.text.strip()
    
    if len(new_location) < 5:
        await message.answer("❌ Место слишком короткое. Попробуйте еще раз:")
        return
    
    complaints_storage[complaint_id].location = new_location
    await message.answer(
        f"✅ Место обновлено: {new_location}\n\n"
        "Выберите следующее поле для редактирования:",
        reply_markup=get_edit_keyboard(complaint_id)
    )
    await state.clear()

@dp.message(AdminEditStates.editing_description, F.text)
async def edit_description(message: types.Message, state: FSMContext):
    """Редактирование описания"""
    admin_id = message.from_user.id
    if admin_id not in editing_storage:
        await message.answer("❌ Сессия редактирования не найдена")
        return
    
    complaint_id = editing_storage[admin_id]
    new_description = message.text.strip()
    
    if len(new_description) < 10:
        await message.answer("❌ Описание слишком короткое. Попробуйте еще раз:")
        return
    
    if len(new_description) > 1000:
        await message.answer(f"❌ Описание слишком длинное ({len(new_description)} символов). Максимум 1000:")
        return
    
    # Обрабатываем текст
    processing_result = process_description_text(new_description)
    processed_description = processing_result['processed_text']
    
    complaints_storage[complaint_id].description = processed_description
    await message.answer(
        f"✅ Описание обновлено\n\n"
        "Выберите следующее поле для редактирования:",
        reply_markup=get_edit_keyboard(complaint_id)
    )
    await state.clear()

@dp.message(AdminEditStates.editing_rating, F.text)
async def edit_rating(message: types.Message, state: FSMContext):
    """Редактирование оценки"""
    admin_id = message.from_user.id
    if admin_id not in editing_storage:
        await message.answer("❌ Сессия редактирования не найдена")
        return
    
    complaint_id = editing_storage[admin_id]
    
    try:
        new_rating = int(message.text.strip())
        if new_rating < 0 or new_rating > 10:
            await message.answer("❌ Оценка должна быть от 0 до 10. Попробуйте еще раз:")
            return
        
        complaints_storage[complaint_id].rating = new_rating
        # Обновляем автооценку
        complaints_storage[complaint_id].auto_assessment = auto_assess_complaint(complaints_storage[complaint_id])
        
        await message.answer(
            f"✅ Оценка обновлена: {new_rating}/10\n\n"
            "Выберите следующее поле для редактирования:",
            reply_markup=get_edit_keyboard(complaint_id)
        )
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите число от 0 до 10:")

# Обработка выбора должности при редактировании
@dp.callback_query(AdminEditStates.editing_position)
async def edit_position_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора должности при редактировании"""
    admin_id = callback.from_user.id
    if admin_id not in editing_storage:
        await callback.answer("❌ Сессия редактирования не найдена")
        return
    
    complaint_id = editing_storage[admin_id]
    
    if callback.data.startswith("pos_"):
        if callback.data == "pos_manual":
            await callback.message.answer("✏️ Введите должность вручную:")
            await callback.message.delete()
            return
        
        try:
            pos_index = int(callback.data.split("_")[1])
            position = POSITIONS[pos_index]
            complaints_storage[complaint_id].position = position
            
            await callback.message.answer(
                f"✅ Должность обновлена: {position}\n\n"
                "Выберите следующее поле для редактирования:",
                reply_markup=get_edit_keyboard(complaint_id)
            )
            await callback.message.delete()
            await state.clear()
            
        except (ValueError, IndexError):
            await callback.answer("❌ Ошибка выбора должности")
    
    await callback.answer()

@dp.message(AdminEditStates.editing_position, F.text)
async def edit_position_manual(message: types.Message, state: FSMContext):
    """Редактирование должности вручную"""
    admin_id = message.from_user.id
    if admin_id not in editing_storage:
        await message.answer("❌ Сессия редактирования не найдена")
        return
    
    complaint_id = editing_storage[admin_id]
    new_position = message.text.strip()
    
    if len(new_position) < 2:
        await message.answer("❌ Должность слишком короткая. Попробуйте еще раз:")
        return
    
    complaints_storage[complaint_id].position = new_position
    await message.answer(
        f"✅ Должность обновлена: {new_position}\n\n"
        "Выберите следующее поле для редактирования:",
        reply_markup=get_edit_keyboard(complaint_id)
    )
    await state.clear()

# Обработчики админских действий (исправлено: упрощенные без лишних кнопок)
@dp.callback_query(F.data.startswith("admin_approve_"))
async def admin_approve_complaint(callback: types.CallbackQuery):
    """Обработка подтверждения жалобы админом"""
    try:
        complaint_id = int(callback.data.split("_")[2])
        
        if complaint_id not in complaints_storage:
            await callback.answer("❌ Жалоба не найдена")
            return
        
        complaint = complaints_storage[complaint_id]
        
        # Публикуем в канал
        await publish_to_channel(complaint)
        # Исправлено: используем answer + delete вместо edit_text
        await callback.message.answer(f"✅ Жалоба #{complaint_id} опубликована в канале")
        await callback.message.delete()
        # Удаляем из хранилища
        del complaints_storage[complaint_id]
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка обработки админского действия (approve): {e}")
        await callback.answer("❌ Ошибка обработки")

@dp.callback_query(F.data.startswith("admin_reject_no_reason_"))
async def admin_reject_no_reason(callback: types.CallbackQuery, state: FSMContext):
    """Отклонение жалобы без причины"""
    try:
        complaint_id = int(callback.data.split("_")[4])
        
        if complaint_id not in complaints_storage:
            await callback.answer("❌ Жалоба не найдена")
            return
        
        complaint = complaints_storage[complaint_id]
        
        # Уведомляем пользователя об отклонении
        user_message = "❌ Ваша жалоба была отклонена администратором без указания причины."
        await bot.send_message(chat_id=complaint.user_id, text=user_message)
        
        await callback.message.answer(f"❌ Жалоба #{complaint_id} отклонена без причины.")
        await callback.message.delete()
        
        del complaints_storage[complaint_id]
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка отклонения жалобы без причины: {e}")
        await callback.answer("❌ Ошибка")

@dp.callback_query(F.data.startswith("admin_reject_with_reason_"))
async def admin_reject_with_reason_prompt(callback: types.CallbackQuery, state: FSMContext):
    """Запрос причины отклонения"""
    try:
        complaint_id = int(callback.data.split("_")[4])
        
        if complaint_id not in complaints_storage:
            await callback.answer("❌ Жалоба не найдена")
            return
        
        admin_reject_storage[callback.from_user.id] = complaint_id
        await callback.message.answer("📝 Введите причину отклонения жалобы:")
        await state.set_state(AdminRejectStates.waiting_for_rejection_reason)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка запроса причины отклонения: {e}")
        await callback.answer("❌ Ошибка")

@dp.message(AdminRejectStates.waiting_for_rejection_reason, F.text)
async def admin_reject_with_reason(message: types.Message, state: FSMContext):
    """Отклонение жалобы с причиной"""
    try:
        admin_id = message.from_user.id
        if admin_id not in admin_reject_storage:
            await message.answer("❌ Сессия отклонения не найдена")
            return
        
        complaint_id = admin_reject_storage[admin_id]
        rejection_reason = message.text.strip()
        
        if complaint_id not in complaints_storage:
            await message.answer("❌ Жалоба не найдена")
            return
        
        complaint = complaints_storage[complaint_id]
        
        # Уведомляем пользователя об отклонении с причиной
        user_message = f"❌ Ваша жалоба была отклонена администратором по следующей причине:\n\n{rejection_reason}"
        await bot.send_message(chat_id=complaint.user_id, text=user_message)
        
        await message.answer(f"❌ Жалоба #{complaint_id} отклонена с причиной: {rejection_reason}")
        
        del complaints_storage[complaint_id]
        del admin_reject_storage[admin_id]
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка отклонения жалобы с причиной: {e}")
        await message.answer("❌ Ошибка")

@dp.callback_query(F.data.startswith("admin_edit_"))
async def admin_edit_complaint(callback: types.CallbackQuery, state: FSMContext):
    """Начало редактирования жалобы админом"""
    try:
        complaint_id = int(callback.data.split("_")[2])
        
        if complaint_id not in complaints_storage:
            await callback.answer("❌ Жалоба не найдена")
            return
        
        # Начинаем редактирование
        editing_storage[callback.from_user.id] = complaint_id
        
        # Показываем текущие данные и меню редактирования
        complaint = complaints_storage[complaint_id]
        edit_text = f"""
✏️ РЕДАКТИРОВАНИЕ ЖАЛОБЫ #{complaint_id}

Текущие данные:
👤 ФИО: {complaint.driver_name}
💼 Должность: {complaint.position}
📞 Контакт: {complaint.contact_info}
📅 Дата: {complaint.incident_date}
📍 Место: {complaint.location}
📖 Описание: {complaint.description[:100]}...
📊 Оценка: {complaint.rating}/10

Выберите поле для редактирования:
"""
        
        await callback.message.answer(
            edit_text,
            reply_markup=get_edit_keyboard(complaint_id)
        )
        await callback.message.delete()
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка обработки админского действия (edit): {e}")
        await callback.answer("❌ Ошибка обработки")

async def publish_to_channel(complaint: Complaint):
    """Публикация жалобы в канал"""
    try:
        # Формируем хэштеги из категорий
        hashtags = []
        for category in complaint.violation_categories:
            # Убираем эмодзи и создаем хэштег
            clean_category = re.sub(r'[^\\w\\s]', '', category).strip().replace(' ', '_')
            hashtags.append(f"#{clean_category}")
        
        hashtags_text = " ".join(hashtags) if hashtags else ""
        
        # Формируем итоговое сообщение
        channel_text = f"""
🚨 Жалоба на сотрудника

👤 ФИО: {complaint.driver_name}
💼 Должность: {complaint.position}
📞 Контакт: {complaint.contact_info}
📅 Дата: {complaint.incident_date}
📍 Место: {complaint.location}
📖 Описание: {complaint.description}
🚫 Нарушения: {", ".join(complaint.violation_categories) if complaint.violation_categories else 'Не указаны'}
😊 Положительное: {", ".join(complaint.positive_aspects) if complaint.positive_aspects else 'Не указаны'}
❌ Уволен: {complaint.fired_status}
📊 Оценка: {complaint.rating}/10
🤖 {complaint.auto_assessment}
📎 Приложения: {len(complaint.additional_files) + (1 if complaint.photo_file_id else 0)} файл(ов)

{hashtags_text}

📢 Сообщение отправлено анонимно
"""
        
        # Добавляем кнопки "Возразить" и "Новая жалоба"
        objection_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⚖️ Возразить",
                        url=f"https://t.me/{ADMIN_USERNAME}"
                    ),
                    InlineKeyboardButton(
                        text="📝 Новая жалоба",
                        url=f"https://t.me/{(await bot.get_me()).username}"
                    )
                ]
            ]
        )
        
        # Исправлено: публикуем в канал с правильным ID
        if complaint.photo_file_id:
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=complaint.photo_file_id,
                caption=channel_text,
                reply_markup=objection_keyboard
            )
        else:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=channel_text,
                reply_markup=objection_keyboard
            )
        
        # Публикуем дополнительные файлы
        if complaint.additional_files:
            media_group = []
            for i, file_info in enumerate(complaint.additional_files[:10]):
                if file_info['type'] == 'photo':
                    media_group.append(InputMediaPhoto(media=file_info['file_id']))
                elif file_info['type'] == 'document':
                    media_group.append(InputMediaDocument(media=file_info['file_id']))
                elif file_info['type'] == 'video':
                    media_group.append(InputMediaVideo(media=file_info['file_id']))
            
            if media_group:
                await bot.send_media_group(chat_id=CHANNEL_ID, media=media_group)
        
        logger.info(f"Жалоба #{complaint.user_id} опубликована в канале")
        
    except Exception as e:
        logger.error(f"Ошибка публикации в канал: {e}")

# Дополнительные обработчики
@dp.message(F.text == "ℹ️ Информация")
async def show_info(message: types.Message):
    """Показ информации о боте"""
    info_text = f"""
ℹ️ Информация о боте

🎯 Назначение: Анонимная подача жалоб на сотрудников

🔒 Анонимность: Ваши личные данные не сохраняются и не публикуются

📝 Процесс:
1. Заполнение анкеты (11 шагов)
2. Выбор должности и категорий нарушений
3. Указание положительных качеств
4. Автооценка ИИ
5. Юридическое подтверждение
6. Модерация администратором
7. Публикация в канале

⚖️ Ответственность: Вы несете полную ответственность за достоверность информации

💾 Черновики: Возможность сохранения незавершенных жалоб

📞 Поддержка: @{ADMIN_USERNAME}
"""
    
    await message.answer(info_text, reply_markup=get_start_keyboard())

@dp.message(F.text == "❓ Помощь")
async def show_help(message: types.Message):
    """Показ помощи"""
    help_text = """
❓ Помощь

🚀 Как начать:
1. Нажмите "📝 Подать жалобу"
2. Следуйте инструкциям бота
3. Заполните все 11 шагов
4. Подтвердите отправку

📋 Что нужно подготовить:
• Фото сотрудника или транспорта
• ФИО сотрудника
• Контактную информацию
• Дату инцидента
• Место происшествия
• Подробное описание (до 1000 символов)
• Дополнительные файлы (по желанию)

✨ Новые возможности:
• Выбор должности сотрудника
• Категории нарушений с хэштегами
• Положительные качества для объективности
• Автооценка жалобы ИИ
• Сохранение в черновики
• Кнопка "Возразить" в публикациях

⚠️ Важно:
• Избегайте нецензурной лексики (автоматически фильтруется)
• Указывайте только достоверную информацию
• Помните о юридической ответственности

🔄 Команды:
/start - Начать сначала
"""
    
    await message.answer(help_text, reply_markup=get_start_keyboard())

# Обработчик неизвестных сообщений
@dp.message()
async def handle_unknown(message: types.Message):
    """Обработчик неизвестных сообщений"""
    await message.answer(
        "❓ Я не понимаю эту команду.\n\n"
        "Используйте кнопки меню или команду /start",
        reply_markup=get_start_keyboard()
    )

# Основная функция
async def main():
    """Основная функция запуска бота"""
    logger.info("Запуск бота...")
    
    try:
        # Проверяем токен
        bot_info = await bot.get_me()
        logger.info(f"Бот запущен: @{bot_info.username}")
        
        # Запускаем polling
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")



