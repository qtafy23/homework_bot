import logging
import time
import os
import sys

import requests
import telegram
from http import HTTPStatus
from dotenv import load_dotenv
from exceptions import HomeworkWithoutStatus

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRAC_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGA_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s',
    filename='bot.log'
)


def check_tokens():
    """Проверка доступности переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot, message):
    """Отправка cообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Успешная отправка сообщения {message}')
    except telegram.error.TelegramError as error:
        logging.error(f'Ошибка при отправке сообщения {error}')


def get_api_answer(timestamp):
    """Запрос к API-сервису."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != HTTPStatus.OK:
            logging.error('Код ответа не ОК.')
            raise requests.exceptions.HTTPError
    except requests.RequestException as error:
        logging.error(error)
        raise error('Something wrong')
    response = response.json()
    return response


def check_response(response):
    """Проверка запроса."""
    if not isinstance(response, dict):
        raise TypeError('Ожидался словарь.')
    elif response.get('homeworks') is None:
        logging.error('Введены неверные данные.')
        raise KeyError('Введены неверные данные.')
    response = response.get('homeworks')
    if not isinstance(response, list):
        raise TypeError('Ожидался список.')
    return response


def parse_status(homework):
    """Проверка статуса."""
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        logging.error('Работа не имеет статуса')
        raise HomeworkWithoutStatus('Работа не имеет статуса')
    homework_name = homework.get('homework_name')
    if homework_name is None:
        logging.error('Список пуст')
        raise KeyError('Список пуст')
    verdict = HOMEWORK_VERDICTS.get(status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Переменные окружения недоступны.')
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    error_message = ''
    try:
        while True:
            try:
                response = get_api_answer(timestamp)
                homework = check_response(response)
                timestamp = response.get('current_date', timestamp)
                if not homework:
                    raise KeyError('Статус домашней роботы не обновлен.')
                else:
                    status = parse_status(homework[0])
                    send_message(bot, status)
            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                if message != error_message:
                    send_message(bot, message)
                    logging.debug('Сообщение отправилось.')
            finally:
                time.sleep(RETRY_PERIOD)
    except KeyboardInterrupt:
        print('\nЗавершение работы программы.')


if __name__ == '__main__':
    main()
