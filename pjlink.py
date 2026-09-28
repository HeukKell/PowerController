from __future__ import annotations

import hashlib
import socket


class PJLinkError(RuntimeError):
    """Raised when a projector rejects or cannot complete a PJLink request."""


ERROR_MESSAGES = {
    "ERR1": "지원하지 않는 명령입니다.",
    "ERR2": "명령 파라미터가 올바르지 않습니다.",
    "ERR3": "현재 상태에서는 명령을 실행할 수 없습니다.",
    "ERR4": "프로젝터 오류로 명령을 실행할 수 없습니다.",
}


class PJLinkClient:
    PORT = 4352

    def __init__(
        self, host: str, password: str = "", timeout: float = 4.0, port: int = PORT
    ) -> None:
        self.host = host
        self.password = password
        self.timeout = timeout
        self.port = port

    @staticmethod
    def _receive_line(connection: socket.socket, limit: int = 1024) -> str:
        data = bytearray()
        while len(data) < limit:
            chunk = connection.recv(1)
            if not chunk:
                break
            data.extend(chunk)
            if chunk in (b"\r", b"\n"):
                break
        if not data:
            raise PJLinkError("프로젝터가 응답하지 않았습니다.")
        return data.decode("ascii", errors="replace").strip()

    def _execute(self, command: str) -> str:
        try:
            with socket.create_connection((self.host, self.port), self.timeout) as connection:
                connection.settimeout(self.timeout)
                greeting = self._receive_line(connection)
                if greeting == "PJLINK 0":
                    payload = command
                elif greeting.startswith("PJLINK 1 "):
                    nonce = greeting.removeprefix("PJLINK 1 ").strip()
                    if not nonce:
                        raise PJLinkError("PJLink 인증 응답이 올바르지 않습니다.")
                    digest = hashlib.md5(
                        (nonce + self.password).encode("utf-8")
                    ).hexdigest()
                    payload = digest + command
                else:
                    raise PJLinkError(f"알 수 없는 PJLink 응답: {greeting}")
                connection.sendall(payload.encode("ascii"))
                response = self._receive_line(connection)
        except socket.timeout as exc:
            raise PJLinkError("연결 시간이 초과되었습니다.") from exc
        except OSError as exc:
            raise PJLinkError(f"프로젝터에 연결할 수 없습니다: {exc}") from exc

        if response == "PJLINK ERRA":
            raise PJLinkError("PJLink 비밀번호가 올바르지 않습니다.")
        if not response.startswith("%1POWR="):
            raise PJLinkError(f"예상하지 못한 응답: {response}")
        result = response.partition("=")[2]
        if result.startswith("ERR"):
            raise PJLinkError(ERROR_MESSAGES.get(result, f"명령 실패: {result}"))
        return result

    def set_power(self, turn_on: bool) -> str:
        result = self._execute(f"%1POWR {'1' if turn_on else '0'}\r")
        if result != "OK":
            raise PJLinkError(f"예상하지 못한 전원 제어 응답: {result}")
        return "%1POWR=OK"

    def get_power_status(self) -> str:
        states = {"0": "off", "1": "on", "2": "cooling", "3": "warming"}
        result = self._execute("%1POWR ?\r")
        if result not in states:
            raise PJLinkError(f"알 수 없는 전원 상태: {result}")
        return states[result]
