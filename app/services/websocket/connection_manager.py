import asyncio
from collections import defaultdict
from typing import Optional

from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.config.logging import logger
from app.utils.json_utils import json_safe


class ConnectionManager:

    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._channels: dict[str, set[WebSocket]] = defaultdict(set)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def attach_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._connections.add(websocket)

        logger.info(
            "WebSocket connected. Active: %s",
            len(self._connections),
        )

    def disconnect(self, websocket: WebSocket):
        self._connections.discard(websocket)

        empty_channels = []

        for channel, sockets in self._channels.items():
            sockets.discard(websocket)

            if not sockets:
                empty_channels.append(channel)

        for channel in empty_channels:
            self._channels.pop(channel, None)

        logger.info(
            "WebSocket disconnected. Active: %s",
            len(self._connections),
        )

    def subscribe(self, websocket: WebSocket, channel: str):
        if not channel:
            return

        self._channels[channel].add(websocket)

    def unsubscribe(self, websocket: WebSocket, channel: str):
        sockets = self._channels.get(channel)

        if not sockets:
            return

        sockets.discard(websocket)

        if not sockets:
            self._channels.pop(channel, None)

    async def send_json(self, websocket: WebSocket, data: dict):
        if websocket.client_state != WebSocketState.CONNECTED:
            return

        try:
            await websocket.send_json(json_safe(data))
        except (WebSocketDisconnect, RuntimeError) as exc:
            logger.warning("WebSocket send failed: %s", exc)
            self.disconnect(websocket)

    async def broadcast(self, channel: str, data: dict):
        sockets = list(self._channels.get(channel, set()))

        for websocket in sockets:
            await self.send_json(websocket, data)

    async def broadcast_all(self, data: dict):
        sockets = list(self._connections)

        for websocket in sockets:
            await self.send_json(websocket, data)

    def broadcast_from_thread(self, channel: str, data: dict):
        if not self._loop or self._loop.is_closed():
            return

        asyncio.run_coroutine_threadsafe(
            self.broadcast(channel, data),
            self._loop,
        )

    def broadcast_all_from_thread(self, data: dict):
        if not self._loop or self._loop.is_closed():
            return

        asyncio.run_coroutine_threadsafe(
            self.broadcast_all(data),
            self._loop,
        )


connection_manager = ConnectionManager()
