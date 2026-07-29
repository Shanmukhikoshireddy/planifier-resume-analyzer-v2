from app.config.mongo import db, planifier_db
from app.config.logging import logger
class BaseRepository:

    use_planifier_db = False

    def __init__(self):
        if self.use_planifier_db:
            self.db = planifier_db
            logger.info(f"Database Name: {self.db.name}")
            logger.info(f"Client: {self.db.client}")
            logger.info(f"Nodes: {self.db.client.nodes}")
        else:
            self.db = db