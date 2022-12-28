import logging
from typing import Callable, Dict, Iterable, List, Optional, Union
from aiogram import Bot, Dispatcher, types
from aiogram.types.reply_keyboard import ReplyKeyboardMarkup, KeyboardButton
import asyncio
from dataclasses import dataclass
import json
import re

from aiogram.utils.exceptions import ChatNotFound

HELLO = """
Вы можете предложить объявление в томскую барахолку Hookah and Vape, нажав на кнопку ниже.
""".strip()
PROVIDE_THE_DEVICE_NAME = """
Во время создания объявления вы всегда можете воспользоваться кнопкой отмены.

Укажите полное название устройства и его расцветку:
""".strip()
RANK_THE_OPERABILITY_OF_THE_DEVICE = """
Оцените работоспособность девайса по пятибалльной шкале, воспользовавшись кнопками ниже.

Подсказка: "5" значит "девайс в идеальном состоянии и почти не был использован", "4" значит "девайс в хорошем состоянии и был активно использован", "3" значит "девайс имеет некоторые незначительные неисправности", "2" значит "девайс имеет значительные неисправности, мешающие его работе, но они могут быть легко единоразово и быстро исправлены без дополнительного оборудования", "1" значит "девайс показывает признаки жизни, но может не работать".
""".strip()
OPERABILITY_RANKS = list("12345")
SPECIFY_THE_COMPONENTS = """
Перечислите аксессуары, оставшиеся от устройства. Если их нет, так и напишите.

<i>Пример: "Коробка, запасной испаритель на 0.3 Ом и кабель формата USB-C".</i>
""".strip()
PROVIDE_THE_PRICE = """
Укажите цену (просто числом, валюта всегда будет российскими рублями):
""".strip()
CHOOSE_THE_MEETING_METHOD = """
Как вы хотите организовать встречу?
""".strip()
PROVIDE_THE_PRODUCT = "Предложить товар"
CANCEL = "Отменить"
CONTINUE = "Продолжить"
MEETING_METHOD_BUTTONS = [["Самовывоз"], ["Можем встретиться"]]
PROVIDE_ONE_DEVICE_IMAGE = """
Предоставьте <bold>одну</bold> фотографию девайса. Потом вы сможете предоставить ещё одну или две, если необходимо.
""".strip()
PROVIDE_THE_DEVICE_PHOTO = """
Пожалуйста, предоставьте фотографию девайса.
""".strip()
PROVIDE_THE_DEVICE_PHOTO_OR_SKIP = """
Пожалуйста, предоставьте фотографию девайса или пропустите этот шаг.
""".strip()
PROVIDE_THE_SECOND_DEVICE_IMAGE = """
Предоставьте вторую фотографию девайса или нажмите на кнопку для продолжения.
""".strip()
PROVIDE_THE_THIRD_DEVICE_IMAGE = """
Предоставьте третью фотографию девайса или нажмите на кнопку для продолжения.
""".strip()
PROVIDE_THE_ADDITIONAL_INFORMATION = """
Предоставьте дополнительную информацию (или нажмите на кнопку продолжения, если дополнительной информации нет):
""".strip()
PRESS_ONE_OF_THE_BUTTONS = """
Пожалуйста, нажмите на одну из кнопок.
""".strip()
DO_NOT_USE_THE_BOT_IN_GROUPS = """
Этот бот не предназначен для использования в групповых чатах.
""".strip()
PLEASE_SEND_TEXT = """
Пожалуйста, отправьте текст.
""".strip()
PROVIDE_VALID_PRICE = """
Цена должна быть целым числом без дополнительных символов. Валюту, например, указывать не нужно.
""".strip()
REVIEW_THE_RESULT = """
Составление объявления завершено! Оно будет выложено в канал, если вы подтвердите его. Вот, как оно будет выглядеть:
""".strip()
ADDED_INTO_QUEUE = """
Объявление добавлено в очередь! Если вы хотите составить ещё одно объявление, нажмите на кнопку ниже.
""".strip()
PRESS_A_BUTTON_TO_START_FORM_FILLING = """
Нажмите на кнопку, чтобы начать составлять объявление.
""".strip()
CANCELED = """
Отменено. Чтобы начать составление объявления снова, нажмите на кнопку ниже.
""".strip()
HELP_MESSAGE = """
Команды:
* <code>/замены {"слово": "замена", "слово": "замена"}</code> - установить список замен для названий девайсов. Старые замены перезаписываются новыми.
* <code>/помощь</code> или <code>/help</code> - показать это сообщение
""".strip()
YOU_HAVENT_SET_A_USERNAME = """
У вас не установлен юзернейм. Он нужен, чтобы люди могли с вами связаться, когда объявление будет выложено. Установите себе юзернейм в настройках профиля в Телеграме.
""".strip()


@dataclass
class Config:
    token: str
    admin_chat_id: int
    posting_channel_id: str
    delay_between_posts_in_seconds: int


config = Config(**json.load(open("config.json")))
bot = Bot(config.token)
dp = Dispatcher(bot)

logger = logging.getLogger("hoarder")
logger.setLevel(logging.DEBUG)
stream_handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s:%(levelname)s:%(name)s:%(message)s")
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

DEFAULT_PARSE_MODE = types.ParseMode.HTML

REPLACEMENTS_FILE_NAME = "replacements.json"


@dataclass
class Post:
    file_ids: list
    text: str


waiting_for_message: Dict[int, Optional[types.Message]] = {}
post_queue: List[Post] = []

replacements = {}
try:
    with open(REPLACEMENTS_FILE_NAME) as f:
        replacements = json.load(f)
except FileNotFoundError:
    pass


@dataclass
class Filter:
    filter: Callable[[types.Message], bool]
    failure_message: str


TEXT_EXISTS_FILTER = Filter(
    filter=lambda message: bool(message.text),
    failure_message=PLEASE_SEND_TEXT
)


class CancellationError(Exception):
    pass


tasks = []


def task(function):
    tasks.append(function)
    return function


@task
async def post_periodically():
    while True:
        try:
            post = post_queue.pop()
            logger.debug("POSTING %s", post)
            await send_a_post(config.posting_channel_id, post.file_ids, post.text)
        except IndexError:
            logger.debug("NO POSTS FOUND IN THE QUEUE")
        except ChatNotFound:
            logger.error("CHANNEL FOR POSTING WAS NOT FOUND")
        await asyncio.sleep(config.delay_between_posts_in_seconds)


async def wait_for_message(previous: types.Message, filters: Iterable[Filter] = ()) -> types.Message:
    assert previous.from_id not in waiting_for_message
    logger.debug("WAITING FOR %d", previous.from_id)
    waiting_for_message[previous.from_id] = None
    while True:
        try:
            message = waiting_for_message[previous.from_id]
        except KeyError:
            # Cancellation happened
            raise CancellationError
        if message is None:
            await asyncio.sleep(0)
        else:
            logger.debug("FOUND %s", message)
            del waiting_for_message[previous.from_id]
            for filter_ in filters:
                if not filter_.filter(message):
                    waiting_for_message[previous.from_id] = None
                    await bot.send_message(
                        previous.from_id, filter_.failure_message
                    )
                    break
            else:
                return message


async def choice(previous: types.Message, message: str, buttons: List[List[str]]):
    button_names = set()
    for row in buttons:
        button_names.update(row)
    await send_message(previous, message, buttons)
    while True:
        new_message = await wait_for_message(previous)
        if new_message.text in button_names:
            return new_message.text
        else:
            await bot.send_message(previous.from_id, PRESS_ONE_OF_THE_BUTTONS)


def generate_a_keyboard(buttons: List[List[str]]):
    keyboard = ReplyKeyboardMarkup(
        one_time_keyboard=False, resize_keyboard=True
    )
    for row in buttons:
        keyboard.add(*(KeyboardButton(column) for column in row))
    return keyboard


async def send_message(previous: types.Message, message: str, buttons: List[List[str]]):
    keyboard = generate_a_keyboard(buttons + [[CANCEL]])
    await bot.send_message(
        previous.from_id, message, reply_markup=keyboard,
        parse_mode=DEFAULT_PARSE_MODE,
    )


async def send_first_button(previous: types.Message, message: str):
    await bot.send_message(
        previous.from_id, message,
        reply_markup=generate_a_keyboard([[PROVIDE_THE_PRODUCT]]),
    )


async def send_a_post(destination_id: Union[int, str], file_ids: list, text: str):
    file_ids_iterator = iter(file_ids)
    try:
        first_file_id = next(file_ids_iterator)
    except StopIteration:
        await bot.send_message(destination_id, text, parse_mode=DEFAULT_PARSE_MODE)
    else:
        media = [types.InputMediaPhoto(
            media=first_file_id, caption=text, parse_mode=DEFAULT_PARSE_MODE,
        )]
        media.extend(types.InputMediaPhoto(media=file_id) for file_id in file_ids_iterator)
        await bot.send_media_group(destination_id, media)


async def user_route(message: types.Message):
    sender = lambda text, buttons: send_message(message, text, buttons)
    await sender(PROVIDE_THE_DEVICE_NAME, [])
    device_name = (await wait_for_message(
        message, filters=[TEXT_EXISTS_FILTER]
    )).text
    for string, replacement in replacements.items():
        device_name = device_name.replace(string.lower(), replacement)
    device_rank = await choice(
        message, RANK_THE_OPERABILITY_OF_THE_DEVICE, [OPERABILITY_RANKS]
    )
    await sender(SPECIFY_THE_COMPONENTS, [])
    device_components = (await wait_for_message(
        message, [TEXT_EXISTS_FILTER]
    )).text
    await sender(PROVIDE_THE_PRICE, [])
    device_price = int((await wait_for_message(
        message, [Filter(
            filter=lambda message: bool(message.text) and all(
                character in "1234567890"
                for character in message.text
            ),
            failure_message=PROVIDE_VALID_PRICE
        )]
    )).text)
    meeting_type = await choice(
        message, CHOOSE_THE_MEETING_METHOD, MEETING_METHOD_BUTTONS,
    )
    await sender(PROVIDE_ONE_DEVICE_IMAGE, [])
    reply = await wait_for_message(message, [Filter(
        filter=lambda message: bool(message.photo),
        failure_message=PROVIDE_THE_DEVICE_PHOTO,
    )])
    device_photos = [reply.photo[-1].file_id]
    continuing = False
    for text in [
        PROVIDE_THE_SECOND_DEVICE_IMAGE,
        PROVIDE_THE_THIRD_DEVICE_IMAGE,
    ]:
        await sender(text, [[CONTINUE]])
        while True:
            reply = await wait_for_message(message)
            if reply.photo:
                device_photos.append(reply.photo[-1].file_id)
                break
            elif reply.text == CONTINUE:
                continuing = True
                break
            else:
                await bot.send_message(
                    message.from_id,
                    PROVIDE_THE_DEVICE_PHOTO_OR_SKIP
                )
        if continuing:
            break
    await sender(PROVIDE_THE_ADDITIONAL_INFORMATION, [[CONTINUE]])
    additional_information = (await wait_for_message(message, [TEXT_EXISTS_FILTER])).text
    if additional_information == CONTINUE:
        additional_information = ""
    else:
        additional_information = additional_information
    await sender(REVIEW_THE_RESULT, [[CONTINUE]])
    result_text = (
        f"Продавец: @{message.from_user.username}\n"
        f"\n"
        f"<strong>{device_name}</strong>\n"
        f"* Работоспособность: {device_rank}/{len(OPERABILITY_RANKS)}\n"
        f"* Комплектация: {device_components}\n"
        f"* Цена: {device_price} рублей\n"
        f"* Предпочтительный тип встречи: {meeting_type}"
    )
    if additional_information:
        result_text += "\nДополнительная информация: " + additional_information
    await send_a_post(message.from_id, device_photos, result_text)
    await wait_for_message(message, [Filter(
        filter=lambda message: message.text == CONTINUE,
        failure_message=PRESS_ONE_OF_THE_BUTTONS,
    )])
    post_queue.append(Post(file_ids=device_photos, text=result_text))
    await send_first_button(message, ADDED_INTO_QUEUE)


async def handle_admin_message(message: types.Message):
    if message.text in ("/help", "/помощь"):
        return HELP_MESSAGE
    match = re.match(r"/замены (.+)", message.text)
    if match:
        replacements_text = match.group(1)
        try:
            new_replacements = json.loads(replacements_text)
        except json.JSONDecodeError:
            return "Ошибка: поданное значение - не JSON."
        if not (
            isinstance(new_replacements, dict)
            and any(isinstance(value, str) for value in new_replacements.values())
        ):
            return "Поданный JSON с заменами сформирован неправильно."
        with open(REPLACEMENTS_FILE_NAME, "w", encoding="utf-8") as f:
            f.write(replacements_text)
        global replacements
        replacements = new_replacements
        return "Сохранено."


@dp.message_handler(content_types=types.ContentType.ANY)
async def start_handler(message: types.Message):
    logger.debug("NEW MESSAGE %s", message)
    if message.chat.type == "private":
        if message.from_id in waiting_for_message:
            if message.text == CANCEL:
                logger.debug("CANCELED %d", message.from_id)
                del waiting_for_message[message.from_id]
                await send_first_button(message, CANCELED)
            else:
                logger.debug("RECEIVED %s", message)
                waiting_for_message[message.from_id] = message
        elif message.text == "/start":
            await send_first_button(message, HELLO)
        elif message.text == PROVIDE_THE_PRODUCT:
            if not message.from_user.username:
                await bot.send_message(message.from_id, YOU_HAVENT_SET_A_USERNAME)
            else:
                try:
                    await user_route(message)
                except CancellationError:
                    pass
        else:
            await send_first_button(
                message, PRESS_A_BUTTON_TO_START_FORM_FILLING
            )
    elif message.chat.id == config.admin_chat_id:
        response = await handle_admin_message(message)
        if response is not None:
            await bot.send_message(
                message.chat.id, response, parse_mode=DEFAULT_PARSE_MODE,
            )
    else:
        await message.reply(DO_NOT_USE_THE_BOT_IN_GROUPS)


async def main():
    logger.debug("STARTING!")
    for task in tasks:
        asyncio.create_task(task())
    await dp.start_polling()


asyncio.run(main())
