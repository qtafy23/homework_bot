import logging
import time
import os
import sys
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (
    UnknownHomeworkStatus, TelegramNotAvailable,
    HttpError, RequestException,
)

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
        raise TelegramNotAvailable('Ошибка при отправке сообщения')


def get_api_answer(timestamp):
    """Запрос к API-сервису."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != HTTPStatus.OK:
            logging.error('Код ответа не ОК.')
            raise HttpError('Код ответа не ОК.')
    except requests.RequestException as error:
        logging.error(error)
        raise RequestException('Что-то пошло не так.')
    response = response.json()
    return response


def check_response(response):
    """Проверка запроса."""
    if not isinstance(response, dict):
        raise TypeError('Ожидался словарь.')
    elif response.get('homeworks') is None:
        logging.error('Введены неверные данные.')
        raise KeyError('Введены неверные данные.')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Ожидался список.')
    return homeworks


def parse_status(homework):
    """Проверка статуса."""
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        logging.error('Пришёл неизвестный статус домашки.')
        raise UnknownHomeworkStatus('Пришёл неизвестный статус домашки.')
    homework_name = homework.get('homework_name')
    if homework_name is None:
        logging.error('Нет ключа homework_name')
        raise KeyError('Нет ключа homework_name')
    verdict = HOMEWORK_VERDICTS.get(status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Переменные окружения недоступны.')
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = None
    message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            timestamp = response.get('current_date', timestamp)
            if not homeworks:
                message = 'Статус работы не обновлён'
                if message != last_message:
                    send_message(bot, message)
            else:
                message = parse_status(homeworks[0])
                if message != last_message:
                    send_message(bot, message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != last_message:
                send_message(bot, message)
                logging.debug('Сообщение отправилось.')
        finally:
            last_message = message
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logging.info('\nЗавершение работы программы.')
