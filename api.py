import os
from datetime import timedelta, datetime
from typing import List

import requests
from fastapi import FastAPI, Header, HTTPException, Request, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)
from pydantic import BaseModel
from sqlmodel import Session, select
from starlette import status

from db import get_session, engine, create_db_and_tables, HeroRead, HeroCreate, Hero, HeroUpdate, Reminder, ReminderRead
from lc import get_agent_executor

app = FastAPI()

origins = [
    "https://remindcat-webui.vercel.app"
]
if os.getenv("ENV") == "dev":
    origins.append(f"http://localhost:{9002}")
    origins.append(f"https://remindcat-web-dev.hu2ty.net")

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
    with Session(engine) as session:
        if event.message.text == 'ls':
            reminders = session.exec(select(Reminder).where(Reminder.line_to == event.source.user_id)).all()
            text = "設定されているリマインダー一覧："
            for reminder in reminders:
                text += f"{reminder.time}: {reminder.name}\n"
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=text))
            return
        if event.message.text == 'dbg':
            reminder = Reminder(line_to=event.source.user_id, name='test', time=datetime.now() + timedelta(seconds=10))
            session.add(reminder)
            session.commit()
            session.refresh(reminder)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text='testリマインダーを設定しました'))
            return

        # execute chain
        output = get_agent_executor(to=event.source.user_id).run(event.message.text)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=output))


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


class LineUser(BaseModel):
    id: str
    name: str


# LINE_LOGIN_SECRET_KEY = os.getenv("LINE_LOGIN_CHANNEL_SECRET")
SECRET_KEY = os.getenv("SECRET_KEY")


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


async def get_line_user(authorization: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = authorization.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        # check expiration
        expires: datetime = payload.get("exp")
        if expires < datetime.utcnow():
            raise credentials_exception
        token_data = LineUser(id=user_id, name=payload.get("name"))
    except JWTError:
        raise credentials_exception
    return token_data


@app.get("/reminders/me/", response_model=List[ReminderRead])
def read_reminders_me(
        *,
        session: Session = Depends(get_session),
        line_user: str = Depends(get_line_user),
        offset: int = 0,
        limit: int = Query(default=100, lte=100),
):
    reminders = session.exec(select(Reminder).where(Reminder.line_to == line_user).offset(offset).limit(limit)).all()
    return reminders


@app.post("/heroes/", response_model=HeroRead)
def create_hero(*, session: Session = Depends(get_session), hero: HeroCreate):
    db_hero = Hero.from_orm(hero)
    session.add(db_hero)
    session.commit()
    session.refresh(db_hero)
    return db_hero


@app.get("/heroes/", response_model=List[HeroRead])
def read_heroes(
        *,
        session: Session = Depends(get_session),
        offset: int = 0,
        limit: int = Query(default=100, lte=100),
):
    heroes = session.exec(select(Hero).offset(offset).limit(limit)).all()
    return heroes


@app.get("/heroes/{hero_id}", response_model=HeroRead)
def read_hero(*, session: Session = Depends(get_session), hero_id: int):
    hero = session.get(Hero, hero_id)
    if not hero:
        raise HTTPException(status_code=404, detail="Hero not found")
    return hero


@app.patch("/heroes/{hero_id}", response_model=HeroRead)
def update_hero(
        *, session: Session = Depends(get_session), hero_id: int, hero: HeroUpdate
):
    db_hero = session.get(Hero, hero_id)
    if not db_hero:
        raise HTTPException(status_code=404, detail="Hero not found")
    hero_data = hero.dict(exclude_unset=True)
    for key, value in hero_data.items():
        setattr(db_hero, key, value)
    session.add(db_hero)
    session.commit()
    session.refresh(db_hero)
    return db_hero


@app.delete("/heroes/{hero_id}")
def delete_hero(*, session: Session = Depends(get_session), hero_id: int):
    hero = session.get(Hero, hero_id)
    if not hero:
        raise HTTPException(status_code=404, detail="Hero not found")
    session.delete(hero)
    session.commit()
    return {"ok": True}


@app.get("/users/me/", response_model=LineUser)
async def read_users_me(current_user: LineUser = Depends(get_line_user)):
    return current_user


@app.get("/users/me/items/")
async def read_own_items(current_user: LineUser = Depends(get_line_user)):
    pass


fake_users_db = {}


@app.post("/login/line", response_model=str)
async def login_line(authorization: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = authorization.credentials
    url = "https://api.line.me/oauth2/v2.1/verify"
    payload = {'id_token': token, 'client_id': os.getenv("LINE_LOGIN_CHANNEL_ID")}
    try:
        response = requests.post(url, data=payload)
        response = response.json()
        if 'error' in response:
            raise credentials_exception
        user = LineUser(id=response['sub'], name=response['name'])
    except Exception as e:
        raise credentials_exception

    payload = {
        "sub": user.id,
        "name": user.name,
        "exp": datetime.utcnow() + timedelta(minutes=15)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    fake_users_db[token] = user
    return token
