import os
import sqlite3
import logging

from config import DB_FILE


logger = logging.getLogger("safew-bot")


# ============================================================
# Database
# ============================================================

def get_db():
    """
    获取 SQLite connection。
    """

    # 确保 data 目录存在
    directory = os.path.dirname(DB_FILE)

    if directory:
        os.makedirs(
            directory,
            exist_ok=True
        )

    conn = sqlite3.connect(
        DB_FILE,
        timeout=30
    )

    conn.row_factory = sqlite3.Row

    return conn


# ============================================================
# 初始化数据库
# ============================================================

def init_database():
    """
    初始化 SQLite 数据库。
    """

    conn = get_db()

    cursor = conn.cursor()

    # ========================================================
    # 每天 / 每群 / 每用户一条记录
    # ========================================================

    cursor.execute(
        """
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
        """
    )

    # ========================================================
    # 查询索引
    # ========================================================

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_activity_date_chat

        ON daily_activity (
            activity_date,
            chat_id,
            message_count DESC
        )
        """
    )

    conn.commit()

    conn.close()

    logger.info(
        "Database initialized: %s",
        DB_FILE
    )


# ============================================================
# 记录消息
# ============================================================

def record_message(
    activity_date,
    chat_id,
    chat_title,
    user_id,
    username,
    display_name,
    message_time
):
    """
    给指定用户当天消息数量 +1。
    """

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute(
        """
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
        """,
        (
            activity_date,
            str(chat_id),
            chat_title,
            str(user_id),
            username,
            display_name,
            message_time
        )
    )

    conn.commit()

    conn.close()


# ============================================================
# 获取某个群当天全部用户
# ============================================================

def get_ranking(
    chat_id,
    activity_date
):
    """
    获取指定群指定日期的全部活跃用户。

    不再限制 Top 10 / Top 100。
    """

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute(
        """
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
            message_count DESC,
            last_message_at ASC
        """,
        (
            activity_date,
            str(chat_id)
        )
    )

    rows = cursor.fetchall()

    conn.close()

    return rows


# ============================================================
# 查询某个用户
# ============================================================

def get_user_activity(
    chat_id,
    user_id,
    activity_date
):
    """
    查询某个用户当天的数据。
    """

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT

            username,
            display_name,
            message_count,
            last_message_at

        FROM daily_activity

        WHERE activity_date = ?

        AND chat_id = ?

        AND user_id = ?
        """,
        (
            activity_date,
            str(chat_id),
            str(user_id)
        )
    )

    row = cursor.fetchone()

    conn.close()

    return row


def get_group_info(chat_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            chat_id,
            chat_title
        FROM daily_activity
        WHERE chat_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (str(chat_id),))

    row = cursor.fetchone()

    conn.close()
    return row