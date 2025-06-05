import os
import uvicorn
from fastapi import FastAPI

from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

from src.api import main_router

load_dotenv()

app = FastAPI()

DEBUG = os.getenv("DEBUG", "False") == "True"

app.include_router(main_router)

origins = [
    "http://localhost",
    "http://localhost:5175",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5176",
    "http://tasks.s-device.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8002)