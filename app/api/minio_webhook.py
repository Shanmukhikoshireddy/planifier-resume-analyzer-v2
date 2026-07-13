from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.config.logging import logger
from app.dto.request.minio_event import MinioEvent
from app.services.minio.webhook_service import WebhookService
router = APIRouter(
    prefix="/api/cv-service/minio",
    tags=["MinIO Webhook"],
)
webhook_service = WebhookService()

# MinIO Webhook
@router.post("/webhook")
async def minio_webhook(
    event: MinioEvent,
    background_tasks: BackgroundTasks,
):
    """
    Receives MinIO ObjectCreated event.
    """
    try: 
        logger.info(
            f"Webhook Received : {event.object_name}"
        )
        background_tasks.add_task(
            webhook_service.process_event,
            event,
        )
        return {
            "success": True,
            "message": "Webhook received.",
            "object": event.object_name,
        }

    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )