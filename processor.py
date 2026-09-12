import logging
from datetime import datetime, timezone
from safew_api import get_chat_member

from config import LOCAL_TZ
from database import record_message
from handlers import (
    handle_command,
    get_display_name,
    handle_group_command,
)


logger = logging.getLogger("safew-bot")


# ============================================================
# SafeW message timestamp
# ============================================================

def get_message_datetime(message):

    timestamp = message.get(
        "date"
    )

    # 如果 SafeW 没有提供 date
    # 则使用服务器当前时间
    if timestamp is None:

        return datetime.now(
            LOCAL_TZ
        )

    try:

        dt = datetime.fromtimestamp(
            timestamp,
            timezone.utc
        )

        return dt.astimezone(
            LOCAL_TZ
        )

    except Exception:

        logger.exception(
            "Failed to parse message timestamp"
        )

        return datetime.now(
            LOCAL_TZ
        )


# ============================================================
# 记录普通群消息
# ============================================================

def process_normal_message(
    message
):

    chat = message.get(
        "chat",
        {}
    )

    user = message.get(
        "from",
        {}
    )

    chat_type = chat.get(
        "type"
    )

    # ========================================================
    # 只统计群
    # ========================================================

    if chat_type not in (
        "group",
        "supergroup"
    ):

        return

    chat_id = str(
        chat.get("id")
    )

    chat_title = (
        chat.get("title")
        or "Unnamed Group"
    )

    user_id = str(
        user.get("id")
    )

    username = get_chat_member(chat_id, user_id).get("result", {}).get("user", {}).get("username")
    

    display_name = get_display_name(
        user
    )

    # ========================================================
    # 使用 SafeW 消息时间
    # ========================================================

    message_datetime = (
        get_message_datetime(
            message
        )
    )

    activity_date = (
        message_datetime.strftime(
            "%Y-%m-%d"
        )
    )

    message_time = (
        message_datetime.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    # ========================================================
    # SQLite +1
    # ========================================================

    record_message(

        activity_date=activity_date,

        chat_id=chat_id,

        chat_title=chat_title,

        user_id=user_id,

        username=username,

        display_name=display_name,

        message_time=message_time
    )

    logger.info(
        "Message recorded | "
        "date=%s | "
        "group=%s | "
        "user=%s | "
        "username=%s",
        activity_date,
        chat_title,
        display_name,
        username
    )


# ============================================================
# Update
# ============================================================

def process_update(update):

    logger.info(
        "Received update: %s",
        update
    )

    # ========================================================
    # message
    # ========================================================

    message = update.get(
        "message"
    )

    if not message:

        logger.info(
            "Update does not contain message"
        )

        return

    chat = message.get(
        "chat",
        {}
    )

    user = message.get(
        "from",
        {}
    )

    logger.info(
        "CHAT: %s",
        chat
    )

    logger.info(
        "USER: %s",
        user
    )

    logger.info(
        "TEXT: %s",
        message.get("text")
    )

    chat_type = chat.get(
        "type"
    )

    logger.info(
        "CHAT TYPE: %s",
        chat_type
    )

    # ========================================================
    # Command
    # ========================================================

    text = message.get(
        "text",
        ""
    )

    if text.startswith("/"):

        logger.info(
            "Command detected"
        )

        handle_command(
            message
        )

        logger.info(
            "Command processed"
        )

        return

    # ========================================================
    # 普通群消息
    # ========================================================

    if chat_type in (
        "group",
        "supergroup"
    ):

        process_normal_message(
            message
        )

    else:

        logger.info(
            "Not a group message, ignored"
        )