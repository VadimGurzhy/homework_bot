
from http import HTTPStatus
import json
import logging
import os
import requests
import telegram
import time

from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка наличия токенов."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        logging.debug('Попытка отправить сообщение')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Удачная отправка сообщения')
    except telegram.error.TelegramError as error:
        logging.error(f'Неудачная отправка сообщения: {error}')
        raise Exception(error)


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        logging.debug('Попытка отправки запроса')
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        logging.debug('Отправлен запрос')
    except Exception as error:
        logging.error(f'Эндпоинт недоступен: {error}')
        send_message(f'Эндпоинт недоступен: {error}')
    if response.status_code != HTTPStatus.OK:
        logging.error(f'Код ответа не 200: {response.status_code}')
        raise requests.exceptions.RequestException(
            f'Код ответа не 200: {response.status_code}'
        )
    try:
        return response.json()
    except json.JSONDecodeError:
        logging.error('Сервер вернул невалидный ответ')
        send_message('Сервер вернул невалидный ответ')


def check_response(response):
    """Проверяет ответ API."""
    try:
        homework = response['homeworks']
    except KeyError as error:
        logging.error(f'Ошибка доступа по ключу homeworks: {error}')
    if not isinstance(homework, list):
        logging.error('Homeworks не в виде списка')
        raise TypeError('Homeworks не в виде списка')
    return homework


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе."""
    try:
        homework_name = homework['homework_name']
    except KeyError:
        logging.error('Неверный ответ сервера')
    homework_status = homework.get('status')
    verdict = ''
    if ((homework_status is None) or (
        homework_status == '')) or ((
            homework_status != 'approved') and (
            homework_status != 'rejected') and (
            homework_status != 'reviewing')):
        logging.error(f'Статус работы некорректен: {homework_status}')
        raise KeyError('Homeworks не в виде списка')
    if homework_status == 'rejected':
        verdict = HOMEWORK_VERDICTS['rejected']
    elif homework_status == 'approved':
        verdict = HOMEWORK_VERDICTS['approved']
    elif homework_status == 'reviewing':
        verdict = HOMEWORK_VERDICTS['reviewing']
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствие обязательных переменных окружения')
        raise Exception('Отсутствие обязательных переменных окружения')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    logging.info('Бот запущен')
    timestamp = int(time.time())
    first_status = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)[0]
            status = parse_status(homework)
            if status != first_status:
                first_status = status
                send_message(bot, status)
                logging.info('Сообщение отправлено')
            else:
                logging.debug('Изменений нет')
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            logging.error(f'Сбой в работе программы: {error}')
            send_message(bot, f'Сбой в работе программы: {error}')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s, %(levelname)s, %(message)s',
        filename='program.log'
    )
    main()
