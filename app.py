import logging

from flask import (
    Flask,
    jsonify,
    request
)

from config import (
    HOST,
    PORT,
    WEBHOOK_PATH,
    SAFEW_WEBHOOK_URL,
)

from database import (
    init_database
)

from processor import (
    process_update
)

from safew_api import (
    check_bot,
    set_webhook,

)


# ============================================================
# Logging
# ============================================================

logging.basicConfig(

    level=logging.INFO,

    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(message)s"
    )
)

logger = logging.getLogger(
    "safew-bot"
)


# ============================================================
# Flask
# ============================================================

app = Flask(
    __name__
)


# ============================================================
# Health Check
# ============================================================

@app.route(
    "/",
    methods=["GET"]
)
def index():

    return jsonify(
        {
            "ok": True,
            "service": "safew-bot",
            "status": "running"
        }
    )


@app.route(
    "/health",
    methods=["GET"]
)
def health():

    return jsonify(
        {
            "ok": True
        }
    )


# ============================================================
# SafeW Webhook
# ============================================================

@app.route(
    WEBHOOK_PATH,
    methods=["POST"]
)
def safew_webhook():

    try:

        update = request.get_json(
            silent=True
        )

        if not update:

            logger.warning(
                "Webhook received empty JSON"
            )

            return jsonify(
                {
                    "ok": False,
                    "error": "empty json"
                }
            ), 400

        logger.info(
            "Webhook update received"
        )

        # ====================================================
        # 处理 Update
        # ====================================================

        process_update(
            update
        )

        # ====================================================
        # 告诉 SafeW 已成功收到
        # ====================================================

        return jsonify(
            {
                "ok": True
            }
        ), 200

    except Exception as e:

        logger.exception(
            "Webhook processing error"
        )

        return jsonify(
            {
                "ok": False,
                "error": str(e)
            }
        ), 500


# ============================================================
# Startup
# ============================================================

def startup():

    logger.info(
        "Initializing database..."
    )

    init_database()

    logger.info(
        "Checking SafeW bot..."
    )

    check_bot()

     # 注册 Webhook
    webhook_url = SAFEW_WEBHOOK_URL

    if not webhook_url:
        raise RuntimeError(
            "SAFEW_WEBHOOK_URL 没有设置，请检查 .env 文件"
        )

    logger.info("Setting webhook: %s", webhook_url)

    result = set_webhook(webhook_url)

    logger.info("Webhook registered successfully: %s", result)

    logger.info("SafeW bot startup completed.")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    startup()

    logger.info(
        "Starting Flask server..."
    )

    app.run(
        host=HOST,
        port=PORT
    )