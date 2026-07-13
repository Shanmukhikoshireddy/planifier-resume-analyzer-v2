from app.config.mongo import db

class BaseRepository:
    def __init__(self):
        self.db = db