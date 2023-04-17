# Create Rocketry app
from datetime import datetime

from linebot.models import TextSendMessage
from rocketry import Rocketry
from sqlmodel import select

from api import line_bot_api
from db import engine, Session, Reminder

app = Rocketry(execution="async")


# Create some tasks

@app.task('every 1 minutes')
async def check_reminders():
    with Session(engine) as session:
        reminders = session.exec(select(Reminder)).all()

        for reminder in reminders:
            if reminder.time > datetime.now():
                continue
            # todo: 1分以上遅れた場合は謝罪を添える
            # push line message
            to = reminder['to']
            text = f"'{reminder['text']}'のお時間です"
            print(f"Pushing message to {to}: {text}")
            line_bot_api.push_message(to, TextSendMessage(text=text))
            # 送信できたのを確認したらDBから削除
            session.delete(reminder)
            session.commit()


if __name__ == "__main__":
    app.run()
