import os
import asyncio
import random
from datetime import datetime, timedelta
from loguru import logger
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError, SlowModeWaitError,
    ChatWriteForbiddenError, PeerIdInvalidError,
    ChannelPrivateError, UserBannedInChannelError,
    UnauthorizedError, RPCError
)
from telethon.tl.functions.messages import ForwardMessagesRequest

# Логирование
logger.add("debug.log", format="{time} {level} {message}", level="INFO")

class SpamBotClient:
    def __init__(self, session_file):
        self.clients = []
        self.session_file = session_file
        self.delay_range = (1, 5)  # Задержка между отправками (секунды)
        self.cycle_interval = (10, 14)  # Задержка между циклами (минуты)
        self.report_chat = "https://t.me/infoinfoinfoinfoo"  # Чат для отчетов
        self.last_message_time = {}  # Время последней отправки сообщения
        self.sent_messages_count = {}  # Количество отправленных сообщений

        self._init_environment()
        self.session_configs = self._load_sessions()
        self._init_clients()

    def _init_environment(self):
        os.makedirs('sessions', exist_ok=True)
    
    def _load_sessions(self):
        try:
            with open(self.session_file, 'r', encoding='utf-8') as f:
                return [self._parse_session_line(line) for line in f if line.strip()]
        except Exception as e:
            logger.error(f"Ошибка загрузки сессий: {str(e)}")
            return []

    def _parse_session_line(self, line):
        parts = line.strip().split(',')
        if len(parts) != 4:
            logger.error(f"Некорректный формат строки: {line.strip()}")
            return None
        return {
            'session_name': parts[0].strip(),
            'api_id': int(parts[1].strip()),
            'api_hash': parts[2].strip(),
            'phone': parts[3].strip()
        }

    def _init_clients(self):
        for config in self.session_configs:
            client = TelegramClient(
                f'sessions/{config["session_name"]}',
                config['api_id'],
                config['api_hash']
            )
            client.phone = config['phone']
            self.clients.append(client)

    async def forward_messages(self, client):
        sent_count = 0
        try:
            dialogs = await client.get_dialogs()
            target_chats = [d for d in dialogs if d.is_group or d.is_channel]
            messages = await client.get_messages("me", limit=20)  # Берем 20 последних сообщений из "Избранного"
            
            if not messages:
                return sent_count

            tasks = []
            for chat in target_chats:  # Отправляем сообщения во все чаты
                msg = random.choice(messages)  # Выбираем случайное сообщение
                tasks.append(self._send_message(client, chat, msg))
            
            results = await asyncio.gather(*tasks)
            sent_count = sum(results)
        except Exception:
            pass  # Suppress errors
        return sent_count

    async def _send_message(self, client, chat, msg):
        try:
            await client(ForwardMessagesRequest(
                from_peer="me",
                id=[msg.id],
                to_peer=chat
            ))
            self.sent_messages_count[client.phone] = self.sent_messages_count.get(client.phone, 0) + 1
            self.last_message_time[client.phone] = datetime.now()
            await asyncio.sleep(random.uniform(*self.delay_range))
            return 1
        except (ChatWriteForbiddenError, PeerIdInvalidError, ChannelPrivateError, UserBannedInChannelError, RPCError):
            pass  # Suppress errors
        except Exception:
            pass  # Suppress errors
        return 0

    async def handle_spam_bot(self, client):
        if datetime.now() - self.last_message_time.get(client.phone, datetime.min) < timedelta(minutes=15):
            return
        
        try:
            spam_bot = await client.get_entity("SpamBot")
            async with client.conversation(spam_bot) as conv:
                for _ in range(3):
                    await conv.send_message("/start")
                    response = await conv.get_response()
                    await asyncio.sleep(random.uniform(2, 5))
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
        except Exception:
            pass  # Suppress errors

    async def send_report(self, client, sent_count, total_chats, delay_minutes):
        report_message = (
            f"📊 Отчет о рассылке:\n"
            f"Аккаунт: {client.phone}\n"
            f"Отправлено сообщений: {sent_count}\n"
            f"Всего чатов: {total_chats}\n"
            f"Следующая рассылка через: {delay_minutes} минут"
        )
        try:
            await client.send_message(self.report_chat, report_message)
        except Exception:
            pass  # Suppress errors

    async def start(self):
        logger.info("Начало работы скрипта")
        # Инициализация клиентов
        for client in self.clients:
            try:
                await client.connect()
                if not await client.is_user_authorized():
                    continue
            except Exception:
                pass  # Suppress errors
        
        while True:
            # Создаем список задач для параллельного выполнения
            tasks = []
            for client in self.clients:
                task = asyncio.create_task(self._process_client(client))
                tasks.append(task)
            
            # Ждем выполнения всех задач
            await asyncio.gather(*tasks)
            
            delay_minutes = random.randint(*self.cycle_interval)
            await asyncio.sleep(delay_minutes * 60)

    async def _process_client(self, client):
        """Обработка одного клиента"""
        sent_count = await self.forward_messages(client)
        dialogs = await client.get_dialogs()
        total_chats = len(dialogs)
        await self.handle_spam_bot(client)
        delay_minutes = random.randint(*self.cycle_interval)
        await self.send_report(client, sent_count, total_chats, delay_minutes)

async def main():
    while True:
        try:
            session_file = "sessions.txt"
            bot_client = SpamBotClient(session_file)
            await bot_client.start()
        except Exception:
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())