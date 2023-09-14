from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI

from routes.routes import setup_routes
from utils.db import generate_tables

app : FastAPI = FastAPI()

setup_routes(app)

# generate_tables()

