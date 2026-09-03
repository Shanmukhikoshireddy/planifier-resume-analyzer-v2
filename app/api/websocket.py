import asyncio
import traceback
from typing import Optional

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import WebSocket
from fastapi import WebSocketDisconnect

from app.config.logging import logger
from app.config.settings import settings
from app.dto.request.search_request import SearchRequest
from app.repository.search_repository import SearchRepository
from app.services.assistant.assistant_service import AssistantService
from app.services.search.search_service import SearchService
from app.services.websocket.connection_manager import connection_manager

router = APIRouter(
    tags=["WebSocket"],
)

assistant_service = AssistantService()
search_service = SearchService()
search_repository = SearchRepository()


def _message(event: str, payload: dict, extra: Optional[dict] = None) -> dict:
    data = {"event": event, **(extra or {})}
    request_id = payload.get("request_id")

    if request_id:
        data["request_id"] = request_id

    return data


def _origin_allowed(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin")

    if not origin:
        return True

    return origin in settings.cors_origins_list


def _as_int(value, default: int, minimum: int = 1, maximum: Optional[int] = None) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default

    if number < minimum:
        return default

    if maximum is not None and number > maximum:
        return maximum

    return number


async def _handle_search(websocket: WebSocket, payload: dict):
    request = SearchRequest(
        prompt=payload.get("prompt") or "",
        search_id=payload.get("search_id"),
        job_position_id=payload.get("job_position_id"),
        received_within=payload.get("received_within") or "ALL",
        global_search_allowed=payload.get(
            "global_search_allowed",
            True,
        ),
    )

    page = _as_int(payload.get("page"), 1, minimum=1)
    page_size = _as_int(
        payload.get("page_size"),
        20,
        minimum=1,
        maximum=100,
    )

    if not request.prompt.strip():
        await connection_manager.send_json(
            websocket,
            _message(
                "error",
                payload,
                {
                    "action": "search",
                    "detail": "prompt is required.",
                },
            ),
        )
        return

    await connection_manager.send_json(
        websocket,
        _message(
            "processing",
            payload,
            {
                "action": "search",
                "search_id": request.search_id,
                "message": "Search started.",
            },
        ),
    )

    try:
        response = await asyncio.to_thread(
            assistant_service.process,
            request,
            page,
            page_size,
        )
    except HTTPException as exc:
        await connection_manager.send_json(
            websocket,
            _message(
                "error",
                payload,
                {
                    "action": "search",
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                },
            ),
        )
        return

    search_id = None

    if isinstance(response, dict):
        search_id = response.get("search_id")

    if search_id:
        connection_manager.subscribe(
            websocket,
            f"search:{search_id}",
        )

    await connection_manager.send_json(
        websocket,
        _message(
            "result",
            payload,
            {
                "action": "search",
                "data": response,
            },
        ),
    )


async def _handle_history(websocket: WebSocket, payload: dict):
    search_id = payload.get("search_id")

    if not search_id:
        await connection_manager.send_json(
            websocket,
            _message(
                "error",
                payload,
                {
                    "action": "history",
                    "detail": "search_id is required.",
                },
            ),
        )
        return

    conversation = await asyncio.to_thread(
        search_repository.get_chat,
        search_id,
    )

    if conversation is None:
        await connection_manager.send_json(
            websocket,
            _message(
                "error",
                payload,
                {
                    "action": "history",
                    "status_code": 404,
                    "detail": "Conversation not found.",
                },
            ),
        )
        return

    await connection_manager.send_json(
        websocket,
        _message(
            "result",
            payload,
            {
                "action": "history",
                "data": conversation,
            },
        ),
    )


async def _handle_reasoning(websocket: WebSocket, payload: dict):
    search_id = payload.get("search_id")
    profile_id = payload.get("profile_id")

    if not search_id or not profile_id:
        await connection_manager.send_json(
            websocket,
            _message(
                "error",
                payload,
                {
                    "action": "reasoning",
                    "detail": "search_id and profile_id are required.",
                },
            ),
        )
        return

    await connection_manager.send_json(
        websocket,
        _message(
            "processing",
            payload,
            {
                "action": "reasoning",
                "message": "Generating candidate reasoning.",
            },
        ),
    )

    response = await asyncio.to_thread(
        search_service.get_candidate_reasoning,
        search_id,
        profile_id,
    )

    await connection_manager.send_json(
        websocket,
        _message(
            "result",
            payload,
            {
                "action": "reasoning",
                "data": response,
            },
        ),
    )


async def _handle_subscribe(websocket: WebSocket, payload: dict):
    channels = []

    search_id = payload.get("search_id")
    job_position_id = payload.get("job_position_id")
    applicant_id = payload.get("applicant_id")

    if search_id:
        channels.append(f"search:{search_id}")

    if job_position_id:
        channels.append(f"resume:job:{job_position_id}")

    if applicant_id:
        channels.append(f"resume:applicant:{applicant_id}")

    if payload.get("resume_feed"):
        channels.append("resume:all")

    if not channels:
        await connection_manager.send_json(
            websocket,
            _message(
                "error",
                payload,
                {
                    "action": "subscribe",
                    "detail": (
                        "Provide search_id, job_position_id, "
                        "applicant_id, or resume_feed=true."
                    ),
                },
            ),
        )
        return

    for channel in channels:
        connection_manager.subscribe(websocket, channel)

    await connection_manager.send_json(
        websocket,
        _message(
            "subscribed",
            payload,
            {
                "action": "subscribe",
                "channels": channels,
            },
        ),
    )


async def _dispatch(websocket: WebSocket, payload: dict):
    action = str(payload.get("action") or "search").strip().lower()

    if action == "ping":
        await connection_manager.send_json(
            websocket,
            _message("pong", payload),
        )
        return

    if action == "search":
        await _handle_search(websocket, payload)
        return

    if action == "history":
        await _handle_history(websocket, payload)
        return

    if action == "reasoning":
        await _handle_reasoning(websocket, payload)
        return

    if action == "subscribe":
        await _handle_subscribe(websocket, payload)
        return

    await connection_manager.send_json(
        websocket,
        _message(
            "error",
            payload,
            {
                "action": action,
                "detail": (
                    "Unknown action. Use search, history, "
                    "reasoning, subscribe, or ping."
                ),
            },
        ),
    )


@router.websocket("/ws/cv-service")
async def cv_service_socket(websocket: WebSocket):
    if not _origin_allowed(websocket):
        await websocket.close(code=1008)
        return

    await connection_manager.connect(websocket)

    await connection_manager.send_json(
        websocket,
        {
            "event": "connected",
            "message": "WebSocket ready.",
            "actions": [
                "search",
                "history",
                "reasoning",
                "subscribe",
                "ping",
            ],
        },
    )

    try:
        while True:
            payload = await websocket.receive_json()

            if not isinstance(payload, dict):
                await connection_manager.send_json(
                    websocket,
                    {
                        "event": "error",
                        "detail": "Message must be a JSON object.",
                    },
                )
                continue

            try:
                await _dispatch(websocket, payload)
            except HTTPException as exc:
                await connection_manager.send_json(
                    websocket,
                    _message(
                        "error",
                        payload,
                        {
                            "action": payload.get("action"),
                            "status_code": exc.status_code,
                            "detail": exc.detail,
                        },
                    ),
                )
            except Exception as exc:
                logger.exception("WebSocket action failed.")
                logger.info(traceback.format_exc())

                await connection_manager.send_json(
                    websocket,
                    _message(
                        "error",
                        payload,
                        {
                            "action": payload.get("action"),
                            "detail": str(exc),
                        },
                    ),
                )

    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)

    except Exception:
        logger.exception("WebSocket connection failed.")
        connection_manager.disconnect(websocket)
