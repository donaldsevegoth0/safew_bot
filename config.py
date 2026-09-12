import os
import time
import sqlite3
import logging
from datetime import datetime, timezone, timedelta

import requests
from dotenv import load_dotenv


# ============================================================
# 配置
# ============================================================

load_dotenv()

HOST = os.getenv("HOST")
PORT = os.getenv("PORT")
WEBHOOK_PATH = os.getenv("SAFEW_WEBHOOK_PATH")
SAFEW_WEBHOOK_URL = os.getenv("SAFEW_WEBHOOK_URL")
BOT_TOKEN = os.getenv("SAFEW_BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError(
        "SAFEW_BOT_TOKEN 没有设置，请检查 .env 文件"
    )

# SafeW Bot API
API_BASE = f"https://api.safew.bot/bot{BOT_TOKEN}"

# SQLite 数据库
DB_FILE = "activity.db"

# 泰国时间 UTC+7
LOCAL_TZ = timezone(timedelta(hours=8))

# 每次最多获取 100 条 update
UPDATE_LIMIT = 100

# Long Polling 等待时间
POLL_TIMEOUT = 30

# API 出错后的重试时间
RETRY_DELAY = 5


# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("safew-bot")


# ============================================================
# SafeW API
# ============================================================

def api_call(method, params=None, http_method="GET"):
    """
    调用 SafeW Bot API。

    GET:
        参数放 params

    POST:
        参数放 JSON
    """

    url = f"{API_BASE}/{method}"

    if http_method.upper() == "POST":

        response = requests.post(
            url,
            json=params or {},
            timeout=POLL_TIMEOUT + 10
        )

    else:

        response = requests.get(
            url,
            params=params or {},
            timeout=POLL_TIMEOUT + 10
        )

    response.raise_for_status()

    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(
            f"SafeW API error: {data}"
        )

    return data


# ============================================================
# SQLite
# ============================================================

def get_db():
    """
    获取 SQLite connection。
    """

    conn = sqlite3.connect(
        DB_FILE,
        timeout=30
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_database():
    """
    初始化数据库。
    """

    conn = get_db()

    cursor = conn.cursor()

    # --------------------------------------------------------
    # 每天、每个群、每个用户一条记录
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_activity (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            activity_date TEXT NOT NULL,

            chat_id TEXT NOT NULL,

            chat_title TEXT,

            user_id TEXT NOT NULL,

            username TEXT,

            display_name TEXT,

            message_count INTEGER NOT NULL DEFAULT 0,

            last_message_at TEXT,

            UNIQUE (
                activity_date,
                chat_id,
                user_id
            )
        )
    """)

    # --------------------------------------------------------
    # 保存 Bot 已经处理到哪个 update_id
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_state (

            key TEXT PRIMARY KEY,

            value TEXT
        )
    """)

    # --------------------------------------------------------
    # 查询排行榜的索引
    # --------------------------------------------------------

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_activity_date_chat

        ON daily_activity (
            activity_date,
            chat_id,
            message_count DESC
        )
    """)

    conn.commit()

    conn.close()

    logger.info("Database initialized.")


# ============================================================
# 日期 / 时间
# ============================================================

def get_today():
    """
    返回泰国当地日期：

    YYYY-MM-DD
    """

    return datetime.now(LOCAL_TZ).strftime(
        "%Y-%m-%d"
    )


def get_now():
    """
    返回泰国当地时间：

    YYYY-MM-DD HH:MM:SS
    """

    return datetime.now(LOCAL_TZ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# ============================================================
# Update Offset
# ============================================================

def get_offset():
    """
    获取上一次处理到的 offset。
    """

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT value
        FROM bot_state
        WHERE key = 'offset'
    """)

    row = cursor.fetchone()

    conn.close()

    if row:
        return int(row["value"])

    return 0


def save_offset(offset):
    """
    保存 offset。
    """

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO bot_state (
            key,
            value
        )

        VALUES (
            'offset',
            ?
        )

        ON CONFLICT(key)
        DO UPDATE SET
            value = excluded.value
    """, (
        str(offset),
    ))

    conn.commit()

    conn.close()


# ============================================================
# 用户显示名称
# ============================================================

def get_display_name(user):
    """
    尽量获得用户的可读名称。
    """

    first_name = user.get("first_name") or ""
    last_name = user.get("last_name") or ""

    name = f"{first_name} {last_name}".strip()

    if name:
        return name

    username = user.get("username")

    if username:
        return f"@{username}"

    return "Unknown"


# ============================================================
# 记录普通群消息
# ============================================================

def record_message(message):
    """
    将一条 Group / Supergroup 消息
    计入当天统计。
    """

    chat = message.get("chat", {})
    user = message.get("from", {})

    chat_type = chat.get("type")

    # --------------------------------------------------------
    # 只统计 Group / Supergroup
    # --------------------------------------------------------

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

    username = user.get(
        "username"
    )

    display_name = get_display_name(
        user
    )

    activity_date = get_today()

    now = get_now()

    conn = get_db()

    cursor = conn.cursor()

    # --------------------------------------------------------
    # 如果今天这个用户第一次发言：
    #
    # INSERT
    #
    # 如果已经存在：
    #
    # message_count + 1
    # --------------------------------------------------------

    cursor.execute("""
        INSERT INTO daily_activity (

            activity_date,
            chat_id,
            chat_title,
            user_id,
            username,
            display_name,
            message_count,
            last_message_at

        )

        VALUES (
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            1,
            ?
        )

        ON CONFLICT (
            activity_date,
            chat_id,
            user_id
        )

        DO UPDATE SET

            username =
                excluded.username,

            display_name =
                excluded.display_name,

            message_count =
                daily_activity.message_count + 1,

            last_message_at =
                excluded.last_message_at,

            chat_title =
                excluded.chat_title
    """, (

        activity_date,
        chat_id,
        chat_title,
        user_id,
        username,
        display_name,
        now
    ))

    conn.commit()

    conn.close()

    logger.info(
        "Message recorded | "
        "group=%s | "
        "user=%s | "
        "username=%s",
        chat_title,
        display_name,
        username
    )


# ============================================================
# 查询排行榜
# ============================================================

def get_ranking(
    chat_id,
    activity_date=None,
    limit=10
):

    if activity_date is None:
        activity_date = get_today()

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT

            user_id,
            username,
            display_name,
            message_count,
            last_message_at

        FROM daily_activity

        WHERE activity_date = ?
        AND chat_id = ?

        ORDER BY
            message_count DESC

        LIMIT ?
    """, (

        activity_date,
        str(chat_id),
        limit
    ))

    rows = cursor.fetchall()

    conn.close()

    return rows


# ============================================================
# 查询某个用户
# ============================================================

def get_user_activity(
    chat_id,
    user_id,
    activity_date=None
):

    if activity_date is None:
        activity_date = get_today()

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT

            username,
            display_name,
            message_count,
            last_message_at

        FROM daily_activity

        WHERE activity_date = ?
        AND chat_id = ?
        AND user_id = ?
    """, (

        activity_date,
        str(chat_id),
        str(user_id)
    ))

    row = cursor.fetchone()

    conn.close()

    return row


# ============================================================
# 格式化排行榜
# ============================================================

def format_ranking(
    chat_id,
    activity_date=None,
    limit=10
):

    if activity_date is None:
        activity_date = get_today()

    rows = get_ranking(
        chat_id,
        activity_date,
        limit
    )

    # --------------------------------------------------------
    # 没有数据
    # --------------------------------------------------------

    if not rows:

        return (
            f"📊 群活跃排行榜\n"
            f"📅 {activity_date}\n\n"
            "暂无消息记录。"
        )

    lines = [

        "📊 群活跃排行榜",

        f"📅 {activity_date}",

        ""
    ]

    medals = [
        "🥇",
        "🥈",
        "🥉"
    ]

    for index, row in enumerate(
        rows,
        start=1
    ):

        # 优先显示 username
        if row["username"]:

            name = (
                f"@{row['username']}"
            )

        else:

            name = (
                row["display_name"]
                or "Unknown"
            )

        # 前三名
        if index <= 3:

            prefix = medals[
                index - 1
            ]

        else:

            prefix = f"{index}."

        lines.append(
            f"{prefix} "
            f"{name} — "
            f"{row['message_count']} 条"
        )

    lines.append("")

    lines.append(
        f"共显示 Top {len(rows)}"
    )

    return "\n".join(lines)


# ============================================================
# SafeW sendMessage
# ============================================================

def send_message(
    chat_id,
    text
):

    return api_call(
        "sendMessage",

        {
            "chat_id": chat_id,
            "text": text
        },

        http_method="POST"
    )


# ============================================================
# Bot 命令
# ============================================================

def handle_command(message):

    text = message.get(
        "text",
        ""
    )

    # 不是命令
    if not text.startswith("/"):
        return

    chat = message.get(
        "chat",
        {}
    )

    chat_type = chat.get(
        "type"
    )

    # 只允许群命令
    if chat_type not in (
        "group",
        "supergroup"
    ):
        return

    chat_id = str(
        chat.get("id")
    )

    parts = text.strip().split()

    command = parts[0].lower()

    # ========================================================
    # /stats
    # ========================================================

    if command == "/stats":

        activity_date = None

        # 例如：
        #
        # /stats
        #
        # /stats 2026-09-10

        if len(parts) >= 2:

            activity_date = parts[1]

        result = format_ranking(
            chat_id,
            activity_date,
            limit=10
        )

        send_message(
            chat_id,
            result
        )

    # ========================================================
    # /top100
    # ========================================================

    elif command == "/top100":

        activity_date = None

        if len(parts) >= 2:

            activity_date = parts[1]

        result = format_ranking(
            chat_id,
            activity_date,
            limit=100
        )

        send_message(
            chat_id,
            result
        )

    # ========================================================
    # /me
    # ========================================================

    elif command == "/me":

        user = message.get(
            "from",
            {}
        )

        user_id = str(
            user.get("id")
        )

        row = get_user_activity(
            chat_id,
            user_id
        )

        if not row:

            reply_text = (
                "📊 你的今日数据\n\n"
                "消息数量：0"
            )

        else:

            if row["username"]:

                name_text = (
                    f"用户名：@"
                    f"{row['username']}"
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
# 处理 Update
# ============================================================

def process_update(update):

    print("=" * 60)

    print("收到 UPDATE:")

    print(update)

    print("=" * 60)

    # --------------------------------------------------------
    # update_id
    # --------------------------------------------------------

    update_id = update.get(
        "update_id"
    )

    if update_id is None:

        print(
            "没有 update_id"
        )

        return

    # --------------------------------------------------------
    # message
    # --------------------------------------------------------

    message = update.get(
        "message"
    )

    if not message:

        print(
            "这个 update 没有 message"
        )

        return

    # --------------------------------------------------------
    # Chat
    # --------------------------------------------------------

    chat = message.get(
        "chat",
        {}
    )

    user = message.get(
        "from",
        {}
    )

    print(
        "CHAT:",
        chat
    )

    print(
        "USER:",
        user
    )

    print(
        "TEXT:",
        message.get("text")
    )

    chat_type = chat.get(
        "type"
    )

    print(
        "CHAT TYPE:",
        chat_type
    )

    # --------------------------------------------------------
    # 命令
    # --------------------------------------------------------

    text = message.get(
        "text",
        ""
    )

    if text.startswith("/"):

        print(
            "检测到 COMMAND"
        )

        handle_command(
            message
        )

        print(
            "COMMAND 处理完成"
        )

        return

    # --------------------------------------------------------
    # 普通群消息
    # --------------------------------------------------------

    if chat_type in (
        "group",
        "supergroup"
    ):

        print(
            "检测到普通群消息"
        )

        record_message(
            message
        )

        print(
            "消息记录完成"
        )

    else:

        print(
            "不是群消息，不统计"
        )


# ============================================================
# 获取 Bot 信息
# ============================================================

def check_bot():

    # --------------------------------------------------------
    # 这里只执行一次
    #
    # 绝对不能在这里 while True
    # --------------------------------------------------------

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
        bot.get(
            "can_join_groups"
        )
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


# ============================================================
# Long Polling
# ============================================================

def run():

    # --------------------------------------------------------
    # 检查 Token
    # --------------------------------------------------------

    if not BOT_TOKEN:

        raise RuntimeError(
            "请设置 SAFEW_BOT_TOKEN"
        )

    # --------------------------------------------------------
    # 初始化数据库
    # --------------------------------------------------------

    init_database()

    # --------------------------------------------------------
    # 检查 Bot
    #
    # 只运行一次
    # --------------------------------------------------------

    check_bot()

    # --------------------------------------------------------
    # 获取 offset
    # --------------------------------------------------------

    offset = get_offset()

    logger.info(
        "Starting polling... offset=%s",
        offset
    )

    # ========================================================
    # 真正的持续监听
    # ========================================================

    while True:

        try:

            # ------------------------------------------------
            # 获取新消息
            # ------------------------------------------------

            data = api_call(
                "getUpdates",

                {
                    "offset": offset,

                    "limit": UPDATE_LIMIT,

                    "timeout": POLL_TIMEOUT
                }
            )

            updates = data.get(
                "result",
                []
            )

            logger.info(
                "getUpdates returned %d updates",
                len(updates)
            )

            # ------------------------------------------------
            # 处理所有新消息
            # ------------------------------------------------

            for update in updates:

                update_id = update.get(
                    "update_id"
                )

                if update_id is None:

                    continue

                try:

                    # 处理
                    process_update(
                        update
                    )

                    # ------------------------------------------------
                    # 只有处理成功后才推进 offset
                    # ------------------------------------------------

                    offset = (
                        update_id + 1
                    )

                    save_offset(
                        offset
                    )

                except Exception:

                    logger.exception(
                        "Failed to process "
                        "update %s",
                        update_id
                    )

        # ----------------------------------------------------
        # 网络错误
        # ----------------------------------------------------

        except requests.RequestException as e:

            logger.error(
                "Network error: %s",
                e
            )

            time.sleep(
                RETRY_DELAY
            )

        # ----------------------------------------------------
        # 其他错误
        # ----------------------------------------------------

        except Exception as e:

            logger.exception(
                "Unexpected error: %s",
                e
            )

            time.sleep(
                RETRY_DELAY
            )


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    run()