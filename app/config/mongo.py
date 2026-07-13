from pymongo import MongoClient
from app.config.settings import settings

client = MongoClient(
    settings.MONGODB_URI
)
db = client[
    settings.MONGODB_DATABASE
]