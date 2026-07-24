from datetime import datetime
from bson import ObjectId

from app.repository.base_repository import BaseRepository


class ConversationMessageRepository(BaseRepository):

    def __init__(self):
        super().__init__()
        self.collection = self.db["conversation_messages"]

    ####################################################
    # Create Conversation Message
    ####################################################

    def create_message(
        self,
        conversation_id: str,
        user_prompt: str,
        intent: str,
        assistant_message: str = "",
        metadata: dict | None = None,
    ):

        document = {

            "conversation_id": ObjectId(conversation_id),

            "user_prompt": user_prompt,

            "intent": intent,

            "assistant_message": assistant_message,

            "metadata": metadata or {},

            "created_at": datetime.utcnow(),

            "updated_at": datetime.utcnow(),

        }

        result = self.collection.insert_one(document)

        return str(result.inserted_id)
    

    ####################################################
    # Conversation History
    ####################################################

    def get_messages(
        self,
        conversation_id: str,
    ):

        messages = list(

            self.collection.find(

                {

                    "conversation_id": ObjectId(conversation_id),

                }

            ).sort(

                "created_at",

                1,

            )

        )

        for message in messages:

            message["_id"] = str(message["_id"])

            message["conversation_id"] = str(
                message["conversation_id"]
            )

        return messages
    


    def update_message(
        self,
        message_id: str,
        assistant_message: dict,
    ):
        self.collection.update_one(
            {
                "_id": ObjectId(message_id),
            },
            {
                "$set": {
                    "assistant_message": assistant_message,
                    "updated_at": datetime.utcnow(),
                }
            },
        )


    