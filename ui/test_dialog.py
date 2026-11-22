import threading
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from core.config import add_to_history
from core.generator import build_test_suite
from core.tester import test_current_connection


class TestSignals(QObject):
    progress = Signal(int, int, str)
    row_result = Signal(dict, bool, int, str)
    finished = Signal(object)


class StrategyTestDialog(QDialog):

    def __init__(
        self,
        manager,
        on_apply_callback,
        on_save_fav_callback,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("DriftLink — Автоподбор и тест стратегий")
        self.setFixedSize(560, 480)
        self.manager = manager
        self.on_apply_callback = on_apply_callback
        self.on_save_fav_callback = on_save_fav_callback

        self.original_strategy = manager.forced_strategy
        self.stop_flag = threading.Event()
        self.tested_strategies: list[dict] = []
        self.best_strategy: dict | None = None

        self.signals = TestSignals()
        self.signals.progress.connect(self.on_progress)
        self.signals.row_result.connect(self.on_row_result)
        self.signals.finished.connect(self.on_finished)

        self.setup_ui()
        self.apply_styles()
        self.start_testing()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self.status_label = QLabel("Генерация и проверка стратегий под текущую сеть...")
        self.status_label.setObjectName("StatusText")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        layout.addWidget(self.progress_bar)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Стратегия", "Статус", "Пинг"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.table, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.apply_btn = QPushButton("✅ Применить выбранную")
        self.apply_btn.setObjectName("PrimaryBtn")
        self.apply_btn.setFixedHeight(38)
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self.apply_selected)

        self.fav_btn = QPushButton("⭐ В избранное")
        self.fav_btn.setObjectName("SecondaryBtn")
        self.fav_btn.setFixedHeight(38)
        self.fav_btn.setEnabled(False)
        self.fav_btn.clicked.connect(self.save_selected)

        self.close_btn = QPushButton("Закрыть")
        self.close_btn.setObjectName("SecondaryBtn")
        self.close_btn.setFixedHeight(38)
        self.close_btn.clicked.connect(self.close)

        btn_layout.addWidget(self.apply_btn, stretch=1)
        btn_layout.addWidget(self.fav_btn)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

    def apply_styles(self):
        self.setStyleSheet("""
            QDialog, QWidget {
                background-color: #111318;
                color: #e2e2e9;
                font-family: 'Segoe UI', sans-serif;
            }
            #StatusText {
                font-size: 13px;
                font-weight: 600;
                color: #8ab4f8;
            }
            QProgressBar {
                background-color: #1b1e26;
                border-radius: 4px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #1a73e8;
                border-radius: 4px;
            }
            QTableWidget {
                background-color: #161920;
                border: 1px solid #282c37;
                border-radius: 10px;
                gridline-color: #232732;
                font-size: 13px;
            }
            QTableWidget::item {
                padding: 6px;
            }
            QTableWidget::item:selected {
                background-color: #1d3152;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #1b1e26;
                color: #9aa0a6;
                border: none;
                border-bottom: 1px solid #282c37;
                padding: 6px;
                font-weight: 600;
            }
            #PrimaryBtn {
                background-color: #1a73e8;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-weight: 600;
                padding: 0px 14px;
            }
            #PrimaryBtn:hover {
                background-color: #1b66c9;
            }
            #PrimaryBtn:disabled {
                background-color: #1b1e26;
                color: #5f6368;
            }
            #SecondaryBtn {
                background-color: #252934;
                color: #e2e2e9;
                border: 1px solid #323746;
                border-radius: 8px;
                padding: 0px 14px;
            }
            #SecondaryBtn:hover {
                background-color: #2f3442;
            }
            #SecondaryBtn:disabled {
                color: #5f6368;
                border-color: #252830;
            }
        """)

    def start_testing(self):
        def worker():
            suite = build_test_suite(extra_random=8)
            total = len(suite)
            best_strat = None
            best_ms = 99999

            for idx, candidate in enumerate(suite, start=1):
                if self.stop_flag.is_set():
                    break
                self.signals.progress.emit(idx, total, candidate["name"])
                self.manager.set_strategy(candidate)

                ok, ms, msg = test_current_connection(timeout=2.2)
                if ok:
                    add_to_history(candidate, ms)
                self.signals.row_result.emit(candidate, ok, ms, msg)

                if ok and ms < best_ms:
                    best_ms = ms
                    best_strat = candidate

            self.signals.finished.emit(best_strat)

        threading.Thread(target=worker, daemon=True).start()

    def on_progress(self, idx: int, total: int, name: str):
        pct = int((idx / total) * 100)
        self.progress_bar.setValue(pct)
        self.status_label.setText(f"[{idx}/{total}] Проверка: {name}...")

    def on_row_result(self, strategy: dict, ok: bool, ms: int, msg: str):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.tested_strategies.append(strategy)

        name_item = QTableWidgetItem(strategy["name"])
        status_item = QTableWidgetItem("OK" if ok else f"FAIL ({msg})")
        ping_item = QTableWidgetItem(f"{ms} мс" if ok else "—")
        ping_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        if ok:
            status_item.setForeground(QColor("#81c995"))
            ping_item.setForeground(QColor("#81c995"))
        else:
            status_item.setForeground(QColor("#f28b82"))
            ping_item.setForeground(QColor("#7a8089"))

        self.table.setItem(row, 0, name_item)
        self.table.setItem(row, 1, status_item)
        self.table.setItem(row, 2, ping_item)
        self.table.scrollToBottom()

    def on_finished(self, best_strat):
        self.best_strategy = best_strat
        if best_strat:
            self.status_label.setText(f"✅ Готово! Лучшая стратегия: {best_strat['name']}")
            self.manager.set_strategy(best_strat)
            self.on_apply_callback(best_strat)
            for i, s in enumerate(self.tested_strategies):
                if s["name"] == best_strat["name"]:
                    self.table.selectRow(i)
                    break
        else:
            self.status_label.setText("❌ Ни одна стратегия не подошла. Возвращён исходный профиль.")
            self.manager.set_strategy(self.original_strategy)

    def on_selection_changed(self):
        has_sel = len(self.table.selectedItems()) > 0
        self.apply_btn.setEnabled(has_sel)
        self.fav_btn.setEnabled(has_sel)

    def _get_selected_strategy(self) -> dict | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return self.tested_strategies[rows[0].row()]

    def apply_selected(self):
        strat = self._get_selected_strategy()
        if strat:
            self.on_apply_callback(strat)
            self.accept()

    def save_selected(self):
        strat = self._get_selected_strategy()
        if strat:
            self.on_save_fav_callback(preset_strat=strat)

    def closeEvent(self, event):
        self.stop_flag.set()
        super().closeEvent(event)
