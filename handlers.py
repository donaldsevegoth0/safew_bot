import logging
from database import get_ranking

from datetime import datetime

from config import LOCAL_TZ
from database import (
    get_ranking,
    get_user_activity,
    get_group_info
)
from safew_api import send_message


logger = logging.getLogger("safew-bot")


# ============================================================
# 当前中国日期
# ============================================================

def get_today():
    """
    UTC+8 当前日期。
    """

    return datetime.now(
        LOCAL_TZ
    ).strftime(
        "%Y-%m-%d"
    )


# ============================================================
# 显示名称
# ============================================================

def get_display_name(user):

    first_name = (
        user.get("first_name")
        or ""
    )

    last_name = (
        user.get("last_name")
        or ""
    )

    name = (
        f"{first_name} {last_name}"
    ).strip()

    if name:
        return name

    username = user.get(
        "username"
    )

    if username:
        return f"@{username}"

    return "Unknown"


# ============================================================
# 日期格式验证
# ============================================================

def valid_date(date_text):

    try:

        datetime.strptime(
            date_text,
            "%Y-%m-%d"
        )

        return True

    except ValueError:

        return False


# ============================================================
# 获取用户名显示文字
# ============================================================

def format_user_name(row):

    if row["username"]:

        return (
            f"@{row['username']}"
        )

    return (
        row["display_name"]
        or "Unknown"
    )


# ============================================================
# 生成完整排行榜
# ============================================================

def format_ranking(
    chat_id,
    activity_date
):

    rows = get_ranking(
        chat_id,
        activity_date
    )

    if not rows:

        return (
            "📊 群活跃统计\n"
            f"📅 {activity_date}\n\n"
            "暂无消息记录。"
        )

    lines = [

        "📊 群活跃统计",

        f"📅 {activity_date}",

        f"👥 活跃人数：{len(rows)}",

        ""
    ]

    for index, row in enumerate(
        rows,
        start=1
    ):

        name = format_user_name(
            row
        )

        count = row[
            "message_count"
        ]

        lines.append(
            f"{index}. "
            f"{name}："
            f"{count} 条"
        )

    return "\n".join(lines)


# ============================================================
# 发送长消息
# ============================================================

def send_long_message(
    chat_id,
    text,
    max_length=3500
):
    """
    防止统计人数太多导致单条消息过长。

    按行拆分。
    """

    lines = text.split("\n")

    chunks = []

    current = ""

    for line in lines:

        # 单独一行已经超过限制
        if len(line) > max_length:

            if current:

                chunks.append(
                    current
                )

                current = ""

            # 强制切割
            for i in range(
                0,
                len(line),
                max_length
            ):

                chunks.append(
                    line[
                        i:i + max_length
                    ]
                )

            continue

        candidate = (
            f"{current}\n{line}"
            if current
            else line
        )

        if len(candidate) > max_length:

            chunks.append(
                current
            )

            current = line

        else:

            current = candidate

    if current:

        chunks.append(
            current
        )

    for chunk in chunks:

        send_message(
            chat_id,
            chunk
        )


# ============================================================
# /stats
# ============================================================

def handle_stats(
    message,
    parts
):

    chat = message.get(
        "chat",
        {}
    )

    chat_id = str(
        chat.get("id")
    )

    # 默认今天
    activity_date = get_today()

    # /stats 2026-09-10
    if len(parts) >= 2:

        activity_date = parts[1]

        if not valid_date(
            activity_date
        ):

            send_message(
                chat_id,
                "❌ 日期格式错误。\n\n"
                "正确格式：\n"
                "/stats 2026-09-10"
            )

            return

    result = format_ranking(
        chat_id,
        activity_date
    )

    send_long_message(
        chat_id,
        result
    )


# ============================================================
# /me
# ============================================================

def handle_me(message):

    chat = message.get(
        "chat",
        {}
    )

    user = message.get(
        "from",
        {}
    )

    chat_id = str(
        chat.get("id")
    )

    user_id = str(
        user.get("id")
    )

    activity_date = get_today()

    row = get_user_activity(
        chat_id,
        user_id,
        activity_date
    )

    if not row:

        send_message(
            chat_id,
            "📊 你的今日数据\n\n"
            "消息数量：0"
        )

        return

    if row["username"]:

        name_text = (
            f"用户名："
            f"@{row['username']}"
        )

    else:

        name_text = (
            f"昵称："
            f"{row['display_name']}"
        )

    reply_text = (

        "📊 你的今日数据\n\n"

        f"{name_text}\n"

        f"消息数量："
        f"{row['message_count']}"
    )

    send_message(
        chat_id,
        reply_text
    )


# ============================================================
# /start
# ============================================================

def handle_start(message):

    chat = message.get(
        "chat",
        {}
    )

    chat_id = str(
        chat.get("id")
    )

    text = (
        "🤖 SafeW 群活跃统计机器人\n\n"

        "/stats\n"
        "查看今天全部活跃用户\n\n"

        "/stats YYYY-MM-DD\n"
        "查看指定日期\n\n"

        "/me\n"
        "查看自己的今日消息数量"
    )

    send_message(
        chat_id,
        text
    )


# ============================================================
# Command Router
# ============================================================

def handle_command(message):

    text = message.get(
        "text",
        ""
    ).strip()

    if not text.startswith("/"):
        return

    command = text.split()[0].split("@")[0]

    if command == "/group":
        handle_group_command(message)
        return

    chat = message.get(
        "chat",
        {}
    )

    chat_type = chat.get(
        "type"
    )

    # 只允许群
    if chat_type not in (
        "group",
        "supergroup"
    ):

        return

    parts = text.split()

    if not parts:
        return

    raw_command = parts[0].lower()

    # 支持：
    #
    # /stats
    #
    # /stats@MyBot
    #
    command = raw_command.split(
        "@",
        1
    )[0]

    if command == "/stats":

        handle_stats(
            message,
            parts
        )

    elif command == "/me":

        handle_me(
            message
        )

    elif command == "/start":

        handle_start(
            message
        )

    else:

        logger.info(
            "Unknown command: %s",
            command
        )

def handle_group_command(message):
    text = message.get("text", "").strip()
    parts = text.split()

    chat_id = message["chat"]["id"]

    if len(parts) != 2:
        send_message(
            chat_id,
            "用法：/group <群ID>\n\n例如：\n/group 10000834587"
        )
        return

    target_chat_id = parts[1]

    group = get_group_info(target_chat_id)

    if not group:
        send_message(
            chat_id,
            f"❌ 找不到群组：{target_chat_id}"
        )
        return

    today = datetime.now().strftime("%Y-%m-%d")

    ranking = get_ranking(
        target_chat_id,
        today
    )

    total_messages = sum(
        row["message_count"]
        for row in ranking
    )

    lines = [
        "📊 群组资料",
        "",
        f"群名称：{group['chat_title']}",
        f"群 ID：{target_chat_id}",
        "",
        f"👥 今日活跃人数：{len(ranking)}",
        f"💬 今日消息数：{total_messages}",
        "",
        "🏆 今日排行"
    ]

    for i, row in enumerate(ranking, 1):

        if row["username"]:
            name = f"@{row['username']}"
        else:
            name = row["display_name"] or row["user_id"]

        lines.append(
            f"{i}. {name} — {row['message_count']}"
        )

    send_message(
        chat_id,
        "\n".join(lines)
    )