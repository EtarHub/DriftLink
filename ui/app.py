import socket
import sys
import threading
import time
from core.config import add_to_favorites
from drivers.win_divert import start_windows_engine
import psutil
from PySide6.QtCore import QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from ui.profiles_dialog import ProfilesAndHistoryDialog
from ui.test_dialog import StrategyTestDialog


class EngineSignals(QObject):
    """Сигналы для безопасного обновления интерфейса из фоновых потоков."""

    log_received = Signal(str)
    strategy_changed = Signal(str)
    ping_updated = Signal(str)


class DriftLinkWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DriftLink")
        self.setFixedSize(820, 560)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self.drag_pos: QPoint | None = None
        self.is_running = False
        self.stop_event = threading.Event()
        self.engine_thread: threading.Thread | None = None
        self.manager_holder: dict = {}
        self.active_strategy_dict: dict | None = None

        self._last_net = psutil.net_io_counters()
        self._last_net_time = time.monotonic()

        self.signals = EngineSignals()
        self.signals.log_received.connect(self.append_log)
        self.signals.strategy_changed.connect(self.on_strategy_updated)
        self.signals.ping_updated.connect(self.on_ping_updated)

        self.setup_ui()
        self.apply_styles()
        self.print_welcome_logs()

        self.net_timer = QTimer(self)
        self.net_timer.timeout.connect(self.update_network_stats)
        self.net_timer.start(1000)

        self.measure_ping()

    def setup_ui(self):
        central = QWidget()
        central.setObjectName("MainCanvas")
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        top_bar.setFixedHeight(48)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(18, 0, 14, 0)
        top_layout.setSpacing(16)

        brand_label = QLabel("DriftLink")
        brand_label.setObjectName("BrandTitle")

        self.dot_net = QLabel("● Сеть")
        self.dot_net.setObjectName("DotGreen")

        self.dot_yt = QLabel("● YouTube")
        self.dot_yt.setObjectName("DotGray")

        self.dot_tg = QLabel("● TgProxy")
        self.dot_tg.setObjectName("DotGray")

        self.profiles_btn = QPushButton("📂 Профили")
        self.profiles_btn.setObjectName("NavButton")
        self.profiles_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.profiles_btn.clicked.connect(self.open_profiles_window)

        self.diag_btn = QPushButton("⚡ Тестирование")
        self.diag_btn.setObjectName("NavButton")
        self.diag_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.diag_btn.clicked.connect(self.open_test_window)

        min_btn = QPushButton("—")
        min_btn.setObjectName("WinCtrlBtn")
        min_btn.setFixedSize(30, 30)
        min_btn.clicked.connect(self.showMinimized)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("WinCloseBtn")
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(self.close)

        top_layout.addWidget(brand_label)
        top_layout.addSpacing(8)
        top_layout.addWidget(self.dot_net)
        top_layout.addWidget(self.dot_yt)
        top_layout.addWidget(self.dot_tg)
        top_layout.addStretch()
        top_layout.addWidget(self.profiles_btn)
        top_layout.addWidget(self.diag_btn)
        top_layout.addSpacing(8)
        top_layout.addWidget(min_btn)
        top_layout.addWidget(close_btn)

        root_layout.addWidget(top_bar)

        hero_area = QWidget()
        hero_area.setObjectName("HeroArea")
        hero_layout = QVBoxLayout(hero_area)
        hero_layout.setContentsMargins(24, 18, 24, 18)
        hero_layout.setSpacing(12)

        hero_title = QLabel("⚡ Умный обход ограничений сети")
        hero_title.setObjectName("HeroTitle")
        hero_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.hero_sub = QLabel(
            "Нажмите кнопку ниже для запуска защиты трафика YouTube"
        )
        self.hero_sub.setObjectName("HeroSub")
        self.hero_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hero_layout.addWidget(hero_title)
        hero_layout.addWidget(self.hero_sub)

        center_row = QHBoxLayout()
        center_row.setSpacing(20)

        left_spacer = QWidget()
        left_spacer.setFixedWidth(160)

        outer_ring = QFrame()
        outer_ring.setObjectName("OuterRingOff")
        outer_ring.setFixedSize(164, 164)
        ring_layout = QVBoxLayout(outer_ring)
        ring_layout.setContentsMargins(14, 14, 14, 14)

        self.power_btn = QPushButton("⏻\nВключить")
        self.power_btn.setObjectName("PowerBtnOff")
        self.power_btn.setFixedSize(136, 136)
        self.power_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.power_btn.clicked.connect(self.toggle_connection)
        ring_layout.addWidget(self.power_btn)

        stats_card = QFrame()
        stats_card.setObjectName("StatsCard")
        stats_card.setFixedWidth(160)
        stats_layout = QVBoxLayout(stats_card)
        stats_layout.setContentsMargins(14, 12, 14, 12)
        stats_layout.setSpacing(10)

        self.dl_label = QLabel("↓  0.0 Мбит/с\n    Входящий")
        self.dl_label.setObjectName("StatText")

        self.ul_label = QLabel("↑  0.0 Мбит/с\n    Исходящий")
        self.ul_label.setObjectName("StatText")

        ping_row = QHBoxLayout()
        self.ping_label = QLabel("⏳ Пинг: — мс")
        self.ping_label.setObjectName("StatTextBold")

        refresh_ping_btn = QPushButton("↻")
        refresh_ping_btn.setObjectName("MiniIconBtn")
        refresh_ping_btn.setFixedSize(22, 22)
        refresh_ping_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_ping_btn.clicked.connect(self.measure_ping)

        ping_row.addWidget(self.ping_label)
        ping_row.addWidget(refresh_ping_btn)

        stats_layout.addWidget(self.dl_label)
        stats_layout.addWidget(self.ul_label)
        stats_layout.addLayout(ping_row)

        center_row.addWidget(left_spacer)
        center_row.addStretch()
        center_row.addWidget(outer_ring)
        center_row.addStretch()
        center_row.addWidget(stats_card)

        hero_layout.addLayout(center_row)

        self.strategy_badge = QLabel("Профиль: Авто-режим (ожидание)")
        self.strategy_badge.setObjectName("StrategyPill")
        self.strategy_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(
            self.strategy_badge, alignment=Qt.AlignmentFlag.AlignCenter
        )

        self.outer_ring = outer_ring
        root_layout.addWidget(hero_area)

        log_panel = QFrame()
        log_panel.setObjectName("LogPanel")
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(20, 12, 20, 14)
        log_layout.setSpacing(8)

        log_header = QHBoxLayout()
        log_title = QLabel("Журнал работы")
        log_title.setObjectName("LogHeaderTitle")

        self.fav_save_btn = QPushButton("⭐ В избранное")
        self.fav_save_btn.setObjectName("LogActionBtn")
        self.fav_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fav_save_btn.clicked.connect(self.save_current_to_favorites)

        copy_btn = QPushButton("Скопировать")
        copy_btn.setObjectName("LogActionBtn")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(self.copy_logs)

        clear_btn = QPushButton("Очистить")
        clear_btn.setObjectName("LogActionBtn")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(lambda: self.log_box.clear())

        log_header.addWidget(log_title)
        log_header.addStretch()
        log_header.addWidget(self.fav_save_btn)
        log_header.addSpacing(12)
        log_header.addWidget(copy_btn)
        log_header.addSpacing(12)
        log_header.addWidget(clear_btn)

        self.log_box = QTextEdit()
        self.log_box.setObjectName("LogBox")
        self.log_box.setReadOnly(True)
        self.log_box.setFont(QFont("Consolas", 9))

        log_layout.addLayout(log_header)
        log_layout.addWidget(self.log_box, stretch=1)

        root_layout.addWidget(log_panel, stretch=1)

    def apply_styles(self):
        self.setStyleSheet("""
            #MainCanvas {
                background-color: #12141a;
                border: 1px solid #252934;
            }
            #TopBar {
                background-color: #0e1015;
                border-bottom: 1px solid #1e222b;
            }
            #BrandTitle {
                font-size: 16px;
                font-weight: 700;
                color: #ffffff;
            }
            #DotGreen {
                color: #4ade80;
                font-size: 12px;
                font-weight: 600;
            }
            #DotGray {
                color: #6b7280;
                font-size: 12px;
                font-weight: 600;
            }
            #NavButton {
                background-color: #191d26;
                color: #d1d5db;
                border: 1px solid #282e3c;
                border-radius: 7px;
                padding: 5px 12px;
                font-size: 12px;
                font-weight: 500;
            }
            #NavButton:hover {
                background-color: #232936;
                color: #ffffff;
                border-color: #3b82f6;
            }
            #WinCtrlBtn, #WinCloseBtn {
                background: transparent;
                color: #9ca3af;
                border: none;
                border-radius: 6px;
                font-size: 13px;
            }
            #WinCtrlBtn:hover {
                background-color: #1f2430;
                color: #ffffff;
            }
            #WinCloseBtn:hover {
                background-color: #dc2626;
                color: #ffffff;
            }
            #HeroArea {
                background: qradialgradient(
                    cx:0.5, cy:0.5, radius:0.75,
                    fx:0.5, fy:0.5,
                    stop:0 #1d2436,
                    stop:1 #12141a
                );
            }
            #HeroTitle {
                font-size: 19px;
                font-weight: 700;
                color: #f3f4f6;
                background: transparent;
            }
            #HeroSub {
                font-size: 12px;
                color: #9ca3af;
                background: transparent;
            }
            #OuterRingOff {
                background-color: rgba(59, 130, 246, 0.08);
                border: 1px solid rgba(59, 130, 246, 0.25);
                border-radius: 82px;
            }
            #OuterRingOn {
                background-color: rgba(74, 222, 128, 0.10);
                border: 1px solid rgba(74, 222, 128, 0.35);
                border-radius: 82px;
            }
            #PowerBtnOff {
                background-color: #1a2030;
                color: #60a5fa;
                border: 2px solid #2b354d;
                border-radius: 68px;
                font-size: 14px;
                font-weight: 600;
            }
            #PowerBtnOff:hover {
                background-color: #21293d;
                border-color: #60a5fa;
                color: #ffffff;
            }
            #PowerBtnOn {
                background-color: #132e22;
                color: #4ade80;
                border: 2px solid #22c55e;
                border-radius: 68px;
                font-size: 14px;
                font-weight: 600;
            }
            #PowerBtnOn:hover {
                background-color: #183b2b;
                border-color: #4ade80;
                color: #ffffff;
            }
            #StatsCard {
                background-color: rgba(20, 24, 33, 0.75);
                border: 1px solid #242936;
                border-radius: 12px;
            }
            #StatText {
                font-size: 12px;
                color: #9ca3af;
                background: transparent;
            }
            #StatTextBold {
                font-size: 12px;
                font-weight: 600;
                color: #e5e7eb;
                background: transparent;
            }
            #MiniIconBtn {
                background-color: #1f2430;
                color: #9ca3af;
                border: 1px solid #2e3545;
                border-radius: 6px;
                font-size: 12px;
            }
            #MiniIconBtn:hover {
                color: #ffffff;
                border-color: #60a5fa;
            }
            #StrategyPill {
                background-color: #191e29;
                color: #93c5fd;
                border: 1px solid #263147;
                border-radius: 12px;
                padding: 4px 16px;
                font-size: 12px;
                font-weight: 500;
            }
            #LogPanel {
                background-color: #0e1015;
                border-top: 1px solid #1e222b;
            }
            #LogHeaderTitle {
                font-size: 13px;
                font-weight: 600;
                color: #9ca3af;
                background: transparent;
            }
            #LogActionBtn {
                background: transparent;
                color: #60a5fa;
                border: none;
                font-size: 12px;
                font-weight: 500;
            }
            #LogActionBtn:hover {
                color: #93c5fd;
                text-decoration: underline;
            }
            #LogBox {
                background-color: #0a0c10;
                border: 1px solid #1b1f29;
                border-radius: 10px;
                padding: 8px;
                color: #d1d5db;
            }
        """)

    def mousePressEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and event.position().y() <= 48
        ):
            self.drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if self.drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self.drag_pos)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None

    def print_welcome_logs(self):
        self.append_log("🛡️ Добро пожаловать в DriftLink!")
        self.append_log(
            "[INFO] Ядро десинхронизации готово к работе (Windows WinDivert)."
        )
        self.append_log("[STATUS] Обход YouTube: [ ВЫКЛЮЧЕН ]")
        self.append_log(
            "[STATUS] Telegram Proxy: [ В РАЗРАБОТКЕ ]\n"
        )

    def append_log(self, text: str):
        self.log_box.append(text)
        if self.log_box.document().blockCount() > 250:
            cursor = self.log_box.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def copy_logs(self):
        QApplication.clipboard().setText(self.log_box.toPlainText())
        self.append_log("[INFO] Журнал скопирован в буфер обмена.")

    def update_network_stats(self):
        now = time.monotonic()
        curr = psutil.net_io_counters()
        dt = max(now - self._last_net_time, 0.1)

        dl_mbps = ((curr.bytes_recv - self._last_net.bytes_recv) * 8) / (
            dt * 1_000_000
        )
        ul_mbps = ((curr.bytes_sent - self._last_net.bytes_sent) * 8) / (
            dt * 1_000_000
        )

        self.dl_label.setText(f"↓  {dl_mbps:.1f} Мбит/с\n    Входящий")
        self.ul_label.setText(f"↑  {ul_mbps:.1f} Мбит/с\n    Исходящий")

        self._last_net = curr
        self._last_net_time = now

    def measure_ping(self):
        def worker():
            try:
                t0 = time.perf_counter()
                with socket.create_connection(("77.88.8.8", 53), timeout=1.5):
                    pass
                ms = int((time.perf_counter() - t0) * 1000)
                self.signals.ping_updated.emit(f"⏳ Пинг: {ms} мс")
            except Exception:
                self.signals.ping_updated.emit("⏳ Пинг: н/д")

        threading.Thread(target=worker, daemon=True).start()

    def on_ping_updated(self, text: str):
        self.ping_label.setText(text)

    def on_strategy_updated(self, name: str):
        self.strategy_badge.setText(f"Профиль: {name}")

    def open_profiles_window(self):
        dlg = ProfilesAndHistoryDialog(
            on_apply_callback=self.apply_selected_strategy,
            parent=self,
        )
        dlg.exec()

    def open_test_window(self):
        if not self.is_running:
            self.append_log(
                "[WARN] Сначала нажмите центральную кнопку «Включить» для"
                " запуска драйвера."
            )
            return

        manager = self.manager_holder.get("manager")
        if not manager:
            return

        dlg = StrategyTestDialog(
            manager=manager,
            on_apply_callback=self.apply_selected_strategy,
            on_save_fav_callback=self.save_current_to_favorites,
            parent=self,
        )
        dlg.exec()

    def apply_selected_strategy(self, strategy: dict):
        self.active_strategy_dict = strategy
        manager = self.manager_holder.get("manager")
        if manager:
            manager.set_strategy(strategy)
        self.on_strategy_updated(strategy["name"])
        self.append_log(f"[OK] Активирован профиль: {strategy['name']}")

    def save_current_to_favorites(self, preset_strat: dict | None = None):
        manager = self.manager_holder.get("manager")
        strat_to_save = (
            preset_strat
            or (manager.current_strategy if manager else None)
            or self.active_strategy_dict
        )

        if not strat_to_save:
            self.append_log(
                "[WARN] Нет активной стратегии для сохранения. Запустите обход"
                " или диагностику."
            )
            return

        default_name = strat_to_save.get("name", "Мой профиль")
        name, ok = QInputDialog.getText(
            self,
            "Сохранить в Избранное",
            "Введите название профиля (например, Дом Wi-Fi):",
            text=default_name,
        )
        if ok and name.strip():
            saved_copy = dict(strat_to_save)
            saved_copy["name"] = name.strip()
            add_to_favorites(saved_copy)
            self.append_log(
                f"[⭐] Профиль «{saved_copy['name']}» сохранён в Избранное!"
            )

    def toggle_connection(self):
        if not self.is_running:
            self.is_running = True
            self.stop_event.clear()

            self.power_btn.setText("⏻\nОтключить")
            self.power_btn.setObjectName("PowerBtnOn")
            self.power_btn.style().unpolish(self.power_btn)
            self.power_btn.style().polish(self.power_btn)

            self.outer_ring.setObjectName("OuterRingOn")
            self.outer_ring.style().unpolish(self.outer_ring)
            self.outer_ring.style().polish(self.outer_ring)

            self.dot_yt.setObjectName("DotGreen")
            self.dot_yt.style().unpolish(self.dot_yt)
            self.dot_yt.style().polish(self.dot_yt)

            self.hero_sub.setText(
                "Защита активна • Трафик YouTube десинхронизируется"
            )

            self.engine_thread = threading.Thread(
                target=start_windows_engine,
                args=(
                    self.stop_event,
                    self.signals.log_received.emit,
                    self.signals.strategy_changed.emit,
                    self.manager_holder,
                ),
                daemon=True,
            )
            self.engine_thread.start()

            if self.active_strategy_dict is not None:
                threading.Timer(
                    0.2,
                    lambda: (
                        self.manager_holder.get("manager").set_strategy(
                            self.active_strategy_dict
                        )
                        if self.manager_holder.get("manager")
                        else None
                    ),
                ).start()
        else:
            self.is_running = False
            self.stop_event.set()

            self.power_btn.setText("⏻\nВключить")
            self.power_btn.setObjectName("PowerBtnOff")
            self.power_btn.style().unpolish(self.power_btn)
            self.power_btn.style().polish(self.power_btn)

            self.outer_ring.setObjectName("OuterRingOff")
            self.outer_ring.style().unpolish(self.outer_ring)
            self.outer_ring.style().polish(self.outer_ring)

            self.dot_yt.setObjectName("DotGray")
            self.dot_yt.style().unpolish(self.dot_yt)
            self.dot_yt.style().polish(self.dot_yt)

            self.hero_sub.setText(
                "Нажмите кнопку ниже для запуска защиты трафика YouTube"
            )
            self.strategy_badge.setText("Профиль: остановлено")


def start_app():
    app = QApplication(sys.argv)
    window = DriftLinkWindow()
    window.show()
    sys.exit(app.exec())
