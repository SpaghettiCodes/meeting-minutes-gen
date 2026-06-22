from __future__ import annotations

import json

from fastapi import WebSocket

from backend.schemas import TaskSummary


class TaskBroadcaster:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def send_snapshot(self, websocket: WebSocket, tasks: list[TaskSummary]) -> None:
        await websocket.send_text(self._encode_snapshot(tasks))

    async def broadcast_snapshot(self, tasks: list[TaskSummary]) -> None:
        if not self._connections:
            return

        message = self._encode_snapshot(tasks)
        dead: list[WebSocket] = []
        for websocket in self._connections:
            try:
                await websocket.send_text(message)
            except Exception:
                dead.append(websocket)

        for websocket in dead:
            self._connections.discard(websocket)

    @staticmethod
    def _encode_snapshot(tasks: list[TaskSummary]) -> str:
        payload = {
            "type": "snapshot",
            "tasks": [task.model_dump(mode="json") for task in tasks],
        }
        return json.dumps(payload)
