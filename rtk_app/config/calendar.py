"""
Настройки Яндекс.Календаря (CalDAV).

Инструменты календаря: список/создание/изменение/удаление событий.
Доступ по CalDAV (https://caldav.yandex.ru/), учётные данные —
из файла ya.txt (логин/email + пароль приложения).
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

YANDEX_CALDAV_URL = "https://caldav.yandex.ru/"
YA_CRED_FILE = os.path.join(BASE_DIR, "ya.txt")
CALENDAR_TZ = "Europe/Moscow"
