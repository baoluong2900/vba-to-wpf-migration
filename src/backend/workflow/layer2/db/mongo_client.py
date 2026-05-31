"""
db/mongo_client.py — MongoDB connection singleton
"""
from __future__ import annotations

from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

from common.config import MONGO_DB, MONGO_URI


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    return MongoClient(MONGO_URI)


def get_db() -> Database:
    return get_client()[MONGO_DB]
