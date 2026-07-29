from pymongo import MongoClient
from app.config.settings import settings

client = MongoClient(
    settings.MONGODB_AI_URI
)
db = client[
    settings.MONGODB_AI_DATABASE
]

planifier_db_client = MongoClient(
    settings.MONGODB_URI
)
planifier_db = planifier_db_client[
    settings.MONGODB_DATABASE
]