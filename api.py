import os
from datetime import timedelta, datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)

from db import db
from lc import get_agent_executor

load_dotenv()  # take envi

app = FastAPI()

origins = [
    "http://localhost:3000",  # todo: dev only.
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^https://(.*)-kenty02.vercel.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


@app.post("/callback/line")
async def line_callback(x_line_signature: str = Header(default=None), request: Request = None):
    body = (await request.body()).decode('utf-8')

    # handle webhook body
    try:
        handler.handle(body, x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    if event.message.text == 'ls':
        reminders = db['reminders'].find(to=event.source.user_id)
        text = "設定されているリマインダー一覧："
        for reminder in reminders:
            text += f"{reminder['time']}: {reminder['text']}\n"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=text))
        return
    if event.message.text == 'dbg':
        reminders = db['reminders']
        reminders.insert(dict(to=event.source.user_id, text='test', time=datetime.now() + timedelta(seconds=10)))
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='testリマインダーを設定しました'))
        return

    # execute chain
    output = get_agent_executor(to=event.source.user_id).run(event.message.text)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=output))
