"""
Настройки профилей (персон).

Профиль — именованная «персона» со СВОЕЙ памятью, диалогом и настройками.
Характер (тон) и характер ответов (формат/длина) задаются при создании.
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROFILES_FILE = os.path.join(os.path.join(BASE_DIR, "session"), "profiles.json")
PROFILE_NAME_CAP = 60
PROFILE_ATTR_CAP = 400
PROFILE_MAX = 50
