import asyncio
import os

import sentry_sdk
import uvicorn

from api import app as app_fastapi
from config import port
from scheduler import app as app_rocketry

sentry_sdk.init(
    dsn="https://1bf65e21867e4356a57c11f3d6e90fef@o4504839999848448.ingest.sentry.io/4505034968203264",

    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    # We recommend adjusting this value in production,
    traces_sample_rate=1.0,
    environment=os.getenv("ENV", "dev"),
)


class Server(uvicorn.Server):
    """Customized uvicorn.Server

    Uvicorn server overrides signals and we need to include
    Rocketry to the signals."""

    def handle_exit(self, sig: int, frame) -> None:
        app_rocketry.session.shut_down()
        return super().handle_exit(sig, frame)


async def main():
    "Run scheduler and the API"
    server = Server(config=uvicorn.Config(app_fastapi, workers=1, loop="asyncio", port=port, host="0.0.0.0"))

    api = asyncio.create_task(server.serve())
    sched = asyncio.create_task(app_rocketry.serve())

    await asyncio.wait([sched, api])


if __name__ == "__main__":
    asyncio.run(main())
