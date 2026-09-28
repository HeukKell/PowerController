from __future__ import annotations

import ipaddress
import json
from collections.abc import Callable

from PyQt6.QtCore import QObject, QRunnable, QSettings, Qt, QThreadPool, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from pjlink import PJLinkClient, PJLinkError


class WorkerSignals(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)


class NetworkWorker(QRunnable):
    def __init__(self, action: Callable[[], object]) -> None:
        super().__init__()
        self.action = action
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            self.signals.succeeded.emit(self.action())
        except PJLinkError as exc:
            self.signals.failed.emit(str(exc))
        except Exception as exc:
            self.signals.failed.emit(f"예기치 않은 오류: {exc}")


class ProjectorRow(QFrame):
    remove_requested = pyqtSignal(str)
    STATE_TEXT = {"unknown": "확인 전", "checking": "확인 중…", "on": "전원 ON",
        "off": "대기 / OFF", "warming": "켜지는 중", "cooling": "꺼지는 중",
        "error": "연결 안 됨"}

    def __init__(self, device: dict[str, object], window: "MainWindow") -> None:
        super().__init__()
        self.device, self.window, self.busy = device, window, False
        self.device_id = str(device["id"])
        self.ip = str(device["ip"])
        self.port = int(device["port"])
        self.setObjectName("projectorRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 12, 12)
        layout.setSpacing(8)
        info = QVBoxLayout()
        name_label = QLabel(str(device["name"]))
        name_label.setObjectName("ipLabel")
        address_label = QLabel(f"{self.ip}:{self.port}")
        address_label.setObjectName("addressLabel")
        self.state_label = QLabel()
        info.addWidget(name_label)
        info.addWidget(address_label)
        info.addWidget(self.state_label)
        layout.addLayout(info, 1)
        self.refresh_button = QPushButton("↻")
        self.refresh_button.setToolTip("현재 상태 새로고침")
        self.refresh_button.setObjectName("smallButton")
        self.on_button = QPushButton("ON")
        self.on_button.setObjectName("onButton")
        self.off_button = QPushButton("OFF")
        self.off_button.setObjectName("offButton")
        self.delete_button = QPushButton("삭제")
        self.delete_button.setObjectName("deleteButton")
        for button in (self.refresh_button, self.on_button, self.off_button, self.delete_button):
            layout.addWidget(button)
        self.refresh_button.clicked.connect(self.refresh_status)
        self.on_button.clicked.connect(lambda: self.set_power(True))
        self.off_button.clicked.connect(lambda: self.set_power(False))
        self.delete_button.clicked.connect(lambda: self.remove_requested.emit(self.device_id))
        self.show_state("unknown")

    def show_state(self, state: str, detail: str = "") -> None:
        self.state_label.setText(self.STATE_TEXT[state] + (f" · {detail}" if detail else ""))
        self.state_label.setProperty("powerState", state)
        self.state_label.style().unpolish(self.state_label)
        self.state_label.style().polish(self.state_label)

    def set_busy(self, busy: bool) -> None:
        self.busy = busy
        for button in (self.refresh_button, self.on_button, self.off_button, self.delete_button):
            button.setDisabled(busy)

    def refresh_status(self) -> None:
        if self.busy:
            return
        self.set_busy(True)
        self.show_state("checking")
        worker = NetworkWorker(self.window.client_for(self.device).get_power_status)
        worker.signals.succeeded.connect(self._status_received)
        worker.signals.failed.connect(self._status_failed)
        self.window.thread_pool.start(worker)

    def _status_received(self, state: object) -> None:
        self.set_busy(False)
        self.show_state(str(state))

    def _status_failed(self, message: str) -> None:
        self.set_busy(False)
        self.show_state("error", message)

    def set_power(self, turn_on: bool) -> None:
        if self.busy:
            return
        self.set_busy(True)
        self.show_state("warming" if turn_on else "cooling")
        worker = NetworkWorker(lambda: self.window.client_for(self.device).set_power(turn_on))
        worker.signals.succeeded.connect(lambda _result: self._command_succeeded(turn_on))
        worker.signals.failed.connect(self._command_failed)
        self.window.thread_pool.start(worker)

    def _command_succeeded(self, turn_on: bool) -> None:
        self.set_busy(False)
        self.show_state("warming" if turn_on else "cooling")
        self.window.set_message(f"{self.ip} · POWER {'ON' if turn_on else 'OFF'} 명령 성공")
        QTimer.singleShot(2000, self.refresh_status)

    def _command_failed(self, message: str) -> None:
        self.set_busy(False)
        self.show_state("error", message)
        self.window.set_message(f"{self.ip} · {message}", error=True)


class MainWindow(QMainWindow):
    AUTO_REFRESH_MS = 10_000

    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings()
        self.thread_pool = QThreadPool.globalInstance()
        self.devices = self._load_devices()
        self.rows: dict[str, ProjectorRow] = {}
        self.setWindowTitle("PowerController_IP")
        self.setMinimumSize(680, 500)
        self.resize(760, 580)
        self._build_ui()
        self._apply_style()
        self._rebuild_list()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_all)
        self.refresh_timer.start(self.AUTO_REFRESH_MS)
        QTimer.singleShot(300, self.refresh_all)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        title = QLabel("PowerController_IP")
        title.setObjectName("title")
        layout.addWidget(title)
        subtitle = QLabel("등록된 프로젝터를 개별 제어합니다 · PJLink TCP 4352")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.addWidget(QLabel("프로젝터 등록"))
        input_row = QHBoxLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("이름 (예: 회의실 프로젝터)")
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("IP 주소 (예: 192.168.0.100)")
        self.ip_input.returnPressed.connect(self.add_projector)
        self.port_input = QLineEdit("4352")
        self.port_input.setPlaceholderText("포트 (기본 4352)")
        self.port_input.setMaximumWidth(125)
        self.add_button = QPushButton("IP 등록")
        self.add_button.setObjectName("addButton")
        self.add_button.clicked.connect(self.add_projector)
        input_row.addWidget(self.name_input, 1)
        input_row.addWidget(self.ip_input, 1)
        input_row.addWidget(self.port_input)
        input_row.addWidget(self.add_button)
        card_layout.addLayout(input_row)
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("공통 PJLink 비밀번호 (선택, 저장되지 않음)")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        card_layout.addWidget(self.password_input)
        layout.addWidget(card)
        header = QHBoxLayout()
        self.count_label = QLabel()
        self.count_label.setObjectName("sectionTitle")
        header.addWidget(self.count_label)
        header.addStretch()
        refresh_all = QPushButton("전체 새로고침")
        refresh_all.setObjectName("linkButton")
        refresh_all.clicked.connect(self.refresh_all)
        header.addWidget(refresh_all)
        layout.addLayout(header)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget = QWidget()
        self.list_widget.setObjectName("listWidget")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(8)
        scroll.setWidget(self.list_widget)
        layout.addWidget(scroll, 1)
        self.message_label = QLabel("IP를 등록하면 상태를 자동으로 확인합니다.")
        self.message_label.setObjectName("message")
        layout.addWidget(self.message_label)
        self.setCentralWidget(root)

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            QWidget { font-family: "Malgun Gothic"; font-size: 14px; color: #e8edf4; }
            QMainWindow, #root, #listWidget { background: #10151d; }
            #title { font-size: 27px; font-weight: 700; color: white; }
            #subtitle, #addressLabel { color: #8996a8; margin-bottom: 5px; }
            #sectionTitle, #ipLabel { font-weight: 700; color: white; }
            #card, #projectorRow { background: #19212c; border: 1px solid #2a3544; border-radius: 10px; }
            QLineEdit { background: #0f151d; border: 1px solid #344256; border-radius: 7px; padding: 9px 11px; }
            QLineEdit:focus { border-color: #4b91ff; }
            QPushButton { border: none; border-radius: 7px; padding: 9px 13px; font-weight: 700; }
            QPushButton:disabled { background: #2d3642; color: #687382; }
            #addButton { background: #2979ff; color: white; }
            #onButton { background: #20a66a; color: white; min-width: 44px; }
            #offButton { background: #d84e4e; color: white; min-width: 44px; }
            #smallButton, #deleteButton { background: #273345; color: #c8d3e2; }
            #deleteButton { color: #ee9999; }
            #linkButton { background: transparent; color: #7caeff; padding: 4px; font-weight: 500; }
            #message { background: #151d27; border-radius: 7px; color: #aab6c7; padding: 10px; }
            QLabel[powerState="on"] { color: #43d493; }
            QLabel[powerState="off"] { color: #9ba9ba; }
            QLabel[powerState="warming"] { color: #f0c15a; }
            QLabel[powerState="cooling"] { color: #75b8ff; }
            QLabel[powerState="error"] { color: #f17a7a; }
            QLabel[powerState="checking"] { color: #7caeff; }
        """)

    @staticmethod
    def _valid_ip(value: str) -> bool:
        try:
            ipaddress.ip_address(value)
            return True
        except ValueError:
            return False

    def _load_devices(self) -> list[dict[str, object]]:
        raw = self.settings.value("projectors", self.settings.value(
            "projector_ips", self.settings.value("recent_ips", "[]")))
        try:
            values = json.loads(str(raw))
            devices: list[dict[str, object]] = []
            for index, value in enumerate(values):
                if isinstance(value, str) and self._valid_ip(value):
                    devices.append({"id": f"legacy-{index}-{value}", "name": value,
                                    "ip": value, "port": 4352})
                elif isinstance(value, dict) and self._valid_ip(str(value.get("ip", ""))):
                    port = int(value.get("port", 4352))
                    if 1 <= port <= 65535:
                        devices.append({"id": str(value.get("id", f"device-{index}")),
                            "name": str(value.get("name") or value["ip"]),
                            "ip": str(value["ip"]), "port": port})
            return devices
        except (TypeError, ValueError):
            return []

    def _save_devices(self) -> None:
        self.settings.setValue("projectors", json.dumps(self.devices, ensure_ascii=False))

    def client_for(self, device: dict[str, object]) -> PJLinkClient:
        return PJLinkClient(str(device["ip"]), self.password_input.text(),
                            port=int(device["port"]))

    def add_projector(self) -> None:
        ip = self.ip_input.text().strip()
        name = self.name_input.text().strip()
        if not self._valid_ip(ip):
            QMessageBox.warning(self, "IP 확인", "올바른 IPv4 또는 IPv6 주소를 입력해 주세요.")
            self.ip_input.setFocus()
            return
        try:
            port = int(self.port_input.text().strip())
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "포트 확인", "포트는 1~65535 사이의 숫자로 입력해 주세요.")
            self.port_input.setFocus()
            return
        if any(item["ip"] == ip and item["port"] == port for item in self.devices):
            self.set_message(f"{ip}:{port}는 이미 등록되어 있습니다.", error=True)
            return
        device = {"id": f"device-{len(self.devices)}-{ip}-{port}", "name": name or ip,
                  "ip": ip, "port": port}
        self.devices.append(device)
        self._save_devices()
        self._rebuild_list()
        self.name_input.clear()
        self.ip_input.clear()
        self.port_input.setText("4352")
        self.rows[str(device["id"])].refresh_status()
        self.set_message(f"{device['name']} ({ip}:{port})를 등록했습니다.")

    def remove_projector(self, device_id: str) -> None:
        device = next(item for item in self.devices if item["id"] == device_id)
        self.devices.remove(device)
        self._save_devices()
        self._rebuild_list()
        self.set_message(f"{device['name']}을(를) 목록에서 삭제했습니다.")

    def _rebuild_list(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.rows = {}
        if not self.devices:
            empty = QLabel("등록된 프로젝터가 없습니다.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #718096; padding: 34px;")
            self.list_layout.addWidget(empty)
        else:
            for device in self.devices:
                row = ProjectorRow(device, self)
                row.remove_requested.connect(self.remove_projector)
                self.rows[str(device["id"])] = row
                self.list_layout.addWidget(row)
        self.list_layout.addStretch()
        self.count_label.setText(f"등록된 프로젝터 · {len(self.devices)}대")

    def refresh_all(self) -> None:
        for row in self.rows.values():
            row.refresh_status()

    def set_message(self, message: str, error: bool = False) -> None:
        self.message_label.setText(("✕ " if error else "✓ ") + message)
        self.message_label.setStyleSheet("color: #f17a7a;" if error else "color: #aab6c7;")
