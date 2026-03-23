"""
WhatsApp webhook — main entry point.

Flow:
1. GET / — Meta webhook verification
2. POST / — Incoming messages routed through Redis-backed state machine
3. Admin replies — admin prefixes their reply with the customer phone number:
       380671234567 Hey, your table is confirmed!
   The bot strips the prefix and forwards the rest to that customer.
"""

import hashlib
import hmac
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response

from app import settings
from app.db import async_sessionmaker, engine
from fastapi.middleware.cors import CORSMiddleware
from app.routers.main_router import router as main_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(main_router)
