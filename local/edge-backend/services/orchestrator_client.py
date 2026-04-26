import time
import json

import httpx
import websockets

from config import settings
from models import ChatResponse, RemoteChatRequest
from services.observability import edge_observability


class RemoteServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 502) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class OrchestratorClient:
    def __init__(self) -> None:
        self._base_url = settings.cloud_api_base
        self._ws_chat_endpoint = settings.cloud_ws_chat_endpoint
        self._remote_transport = settings.remote_transport
        self._timeout = settings.request_timeout_seconds

    async def send_chat(self, request: RemoteChatRequest, *, request_id: str) -> ChatResponse:
        request_payload = request.model_dump() if hasattr(request, "model_dump") else request.dict()

        transport = self._remote_transport
        if transport == "websocket":
            return await self._send_chat_websocket(request_payload, request_id=request_id)
        if transport == "auto":
            try:
                return await self._send_chat_websocket(request_payload, request_id=request_id)
            except RemoteServiceError as exc:
                if exc.status_code not in {502, 504}:
                    raise

        return await self._send_chat_http(request_payload, request_id=request_id)

    async def _send_chat_http(self, request_payload: dict, *, request_id: str) -> ChatResponse:
        url = f"{self._base_url}/chat"
        started_at = time.perf_counter()
        edge_observability.log_bridge_outbound(request_id, url, request_payload)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=request_payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            edge_observability.log_bridge_error(
                request_id,
                latency_ms=int((time.perf_counter() - started_at) * 1000),
                detail="Remote orchestrator timed out.",
                status_code=504,
                payload=request_payload,
            )
            raise RemoteServiceError(
                detail="Remote orchestrator timed out.",
                status_code=504,
            ) from exc
        except httpx.HTTPStatusError as exc:
            detail = _parse_remote_error(exc.response)
            edge_observability.log_bridge_error(
                request_id,
                latency_ms=int((time.perf_counter() - started_at) * 1000),
                detail=detail,
                status_code=exc.response.status_code,
                payload=request_payload,
            )
            raise RemoteServiceError(detail=detail, status_code=exc.response.status_code) from exc
        except httpx.RequestError as exc:
            edge_observability.log_bridge_error(
                request_id,
                latency_ms=int((time.perf_counter() - started_at) * 1000),
                detail="Remote orchestrator is unreachable.",
                status_code=502,
                payload=request_payload,
            )
            raise RemoteServiceError(
                detail="Remote orchestrator is unreachable.",
                status_code=502,
            ) from exc

        response_payload = response.json()
        edge_observability.log_bridge_inbound(
            request_id,
            status_code=response.status_code,
            latency_ms=int((time.perf_counter() - started_at) * 1000),
            payload=response_payload,
        )
        if hasattr(ChatResponse, "model_validate"):
            return ChatResponse.model_validate(response_payload)
        return ChatResponse(**response_payload)

    async def _send_chat_websocket(self, request_payload: dict, *, request_id: str) -> ChatResponse:
        ws_url = self._ws_chat_endpoint
        if not ws_url:
            raise RemoteServiceError(detail="Remote websocket endpoint is not configured.", status_code=502)

        started_at = time.perf_counter()
        edge_observability.log_bridge_outbound(request_id, ws_url, request_payload)

        try:
            async with websockets.connect(ws_url, open_timeout=self._timeout, close_timeout=2.0, max_size=None) as socket:
                await socket.send(json.dumps(request_payload, ensure_ascii=False))
                raw_message = await socket.recv()
        except TimeoutError as exc:
            edge_observability.log_bridge_error(
                request_id,
                latency_ms=int((time.perf_counter() - started_at) * 1000),
                detail="Remote websocket orchestrator timed out.",
                status_code=504,
                payload=request_payload,
            )
            raise RemoteServiceError(detail="Remote websocket orchestrator timed out.", status_code=504) from exc
        except Exception as exc:  # noqa: BLE001
            edge_observability.log_bridge_error(
                request_id,
                latency_ms=int((time.perf_counter() - started_at) * 1000),
                detail=f"Remote websocket orchestrator is unreachable: {exc}",
                status_code=502,
                payload=request_payload,
            )
            raise RemoteServiceError(detail="Remote websocket orchestrator is unreachable.", status_code=502) from exc

        if isinstance(raw_message, bytes):
            message_text = raw_message.decode("utf-8", errors="replace")
        else:
            message_text = str(raw_message)

        try:
            response_payload = json.loads(message_text)
        except ValueError as exc:
            edge_observability.log_bridge_error(
                request_id,
                latency_ms=int((time.perf_counter() - started_at) * 1000),
                detail="Remote websocket orchestrator returned non-JSON payload.",
                status_code=502,
                payload={"raw_message": message_text[:400]},
            )
            raise RemoteServiceError(detail="Remote websocket orchestrator returned non-JSON payload.") from exc

        if isinstance(response_payload, dict) and response_payload.get("detail"):
            status_code = int(response_payload.get("status_code") or 502)
            detail = str(response_payload.get("detail"))
            edge_observability.log_bridge_error(
                request_id,
                latency_ms=int((time.perf_counter() - started_at) * 1000),
                detail=detail,
                status_code=status_code,
                payload=request_payload,
            )
            raise RemoteServiceError(detail=detail, status_code=status_code)

        edge_observability.log_bridge_inbound(
            request_id,
            status_code=200,
            latency_ms=int((time.perf_counter() - started_at) * 1000),
            payload=response_payload,
        )
        if hasattr(ChatResponse, "model_validate"):
            return ChatResponse.model_validate(response_payload)
        return ChatResponse(**response_payload)


def _parse_remote_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return "Remote orchestrator returned a non-JSON error."

    detail = payload.get("detail")
    if isinstance(detail, str) and detail:
        return detail

    return "Remote orchestrator returned an unexpected error."


orchestrator_client = OrchestratorClient()
