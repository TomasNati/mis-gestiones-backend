from dotenv import load_dotenv
import os
from sqlalchemy import create_engine

load_dotenv()

class Database():

    def __init__(self):
        DATABASE_URL = os.getenv("DATABASE_URL")
        self.engine = create_engine(DATABASE_URL)

database = Database()


