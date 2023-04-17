import os

from dotenv import load_dotenv

load_dotenv()
# try get port from env, defaults to 8000
port = int(os.getenv("PORT", 8000))
