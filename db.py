from datetime import datetime
from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine

from config import database_url


class HeroBase(SQLModel):
    name: str = Field(index=True)
    secret_name: str
    age: Optional[int] = Field(default=None, index=True)


class Hero(HeroBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class HeroCreate(HeroBase):
    pass


class HeroRead(HeroBase):
    id: int


class HeroUpdate(SQLModel):
    name: Optional[str] = None
    secret_name: Optional[str] = None
    age: Optional[int] = None


class ReminderBase(SQLModel):
    line_to: str
    name: str
    time: datetime


class Reminder(ReminderBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class ReminderCreate(ReminderBase):
    pass


class ReminderRead(ReminderBase):
    id: int


class ReminderUpdate(SQLModel):
    line_to: Optional[str] = None
    name: Optional[str] = None
    time: Optional[datetime] = None


connect_args = {}
if database_url.startswith("sqlite"):
    # allow multiple connections to sqlite
    connect_args = {"check_same_thread": False}
engine = create_engine(database_url, echo=True, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
