import logging

import requests

from config import API_BASE


logger = logging.getLogger("safew-bot")


# ============================================================
# SafeW API
# ============================================================

def api_call(
    method,
    params=None,
    http_method="GET"
):
    """
    调用 SafeW Bot API。
    """

    url = f"{API_BASE}/{method}"

    if http_method.upper() == "POST":

        response = requests.post(
            url,
            json=params or {},
            timeout=15
        )

    else:

        response = requests.get(
            url,
            params=params or {},
            timeout=15
        )

    response.raise_for_status()

    data = response.json()

    if not data.get("ok"):

        raise RuntimeError(
            f"SafeW API error: {data}"
        )

    return data

def set_webhook(url):
    return api_call(
        "setwebhook",
        {
            "url": url,
            "allowed_updates": ["message"]
        },
        http_method="POST"
    )

# ============================================================
# sendMessage
# ============================================================

def send_message(
    chat_id,
    text
):
    """
    发送消息。
    """

    return api_call(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text
        },
        http_method="POST"
    )


# ============================================================
# getMe
# ============================================================

def check_bot():

    data = api_call(
        "getMe"
    )

    bot = data["result"]

    logger.info(
        "Bot connected: @%s (%s)",
        bot.get("username"),
        bot.get("id")
    )

    logger.info(
        "can_join_groups = %s",
        bot.get("can_join_groups")
    )

    logger.info(
        "can_read_all_group_messages = %s",
        bot.get(
            "can_read_all_group_messages"
        )
    )

    logger.info(
        "supports_inline_queries = %s",
        bot.get(
            "supports_inline_queries"
        )
    )

    return bot

def get_chat_member(chat_id, user_id):
    return api_call(
        "getChatMember",
        {
            "chat_id": chat_id,
            "user_id": user_id
        },
        http_method="GET"
    )