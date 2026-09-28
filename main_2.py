from __future__ import annotations

import argparse
import ipaddress
import sys
import time

from pjlink import PJLinkClient, PJLinkError


def valid_ip(value: str) -> str:
    try:
        ipaddress.ip_address(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"올바르지 않은 IP 주소입니다: {value}") from exc
    return value


def valid_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("포트는 숫자여야 합니다.") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("포트는 1~65535 사이여야 합니다.")
    return port


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Barco 프로젝터에 PJLink 전원 명령을 전송합니다."
    )
    parser.add_argument("--ip", required=True, type=valid_ip, help="프로젝터 IP 주소")
    parser.add_argument(
        "--port", type=valid_port, default=4352, help="PJLink TCP 포트 (기본값: 4352)"
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--on", action="store_true", help="전원 ON 명령 전송")
    action.add_argument("--off", action="store_true", help="전원 OFF 명령 전송")
    parser.add_argument("--password", default="", help="PJLink 비밀번호 (선택)")
    parser.add_argument(
        "--retries", type=int, default=1, help="실패 시 총 시도 횟수 (기본값: 1)"
    )
    parser.add_argument(
        "--delay", type=float, default=5.0, help="재시도 간격(초, 기본값: 5)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.retries < 1:
        print("오류: --retries는 1 이상이어야 합니다.", file=sys.stderr)
        return 2
    if args.delay < 0:
        print("오류: --delay는 0 이상이어야 합니다.", file=sys.stderr)
        return 2

    state = "ON" if args.on else "OFF"
    for attempt in range(1, args.retries + 1):
        try:
            client = PJLinkClient(
                args.ip, password=args.password, port=args.port, timeout=4.0
            )
            client.set_power(args.on)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] {args.ip}:{args.port} POWER {state} 명령 성공")
            return 0
        except PJLinkError as exc:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"[{timestamp}] 시도 {attempt}/{args.retries} 실패: {exc}",
                file=sys.stderr,
            )
            if attempt < args.retries:
                time.sleep(args.delay)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
