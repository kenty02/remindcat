# Create Rocketry app
from datetime import datetime

from linebot.models import TextSendMessage
from rocketry import Rocketry
from db import db
from api import line_bot_api

app = Rocketry(execution="async")


# Create some tasks

@app.task('every 1 minutes')
async def check_reminders():
    reminders = db['reminders']
    for reminder in reminders:
        if reminder['time'] > datetime.now():
            continue
        # todo: 1分以上遅れた場合は謝罪を添える
        # push line message
        reminders.delete(id=reminder['id'])
        to = reminder['to']
        text = f"'{reminder['text']}'のお時間です"
        print(f"Pushing message to {to}: {text}")
        line_bot_api.push_message(to, TextSendMessage(text=text))


if __name__ == "__main__":
    app.run()
