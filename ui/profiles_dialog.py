from core.config import (
    add_to_favorites,
    clear_history,
    get_favorites,
    get_history,
    remove_from_favorites,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class ProfilesAndHistoryDialog(QDialog):

    def __init__(self, on_apply_callback, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DriftLink — Профили и история тестов")
        self.setFixedSize(600, 480)
        self.on_apply_callback = on_apply_callback

        self.favorites_data: list[dict] = []
        self.history_data: list[dict] = []

        self.setup_ui()
        self.apply_styles()
        self.reload_all()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self.tabs = QTabWidget()

        # --- Вкладка 1: Избранное ---
        fav_tab = QWidget()
        fav_layout = QVBoxLayout(fav_tab)
        fav_layout.setContentsMargins(8, 12, 8, 8)
        fav_layout.setSpacing(10)

        self.fav_table = QTableWidget(0, 2)
        self.fav_table.setHorizontalHeaderLabels(
            ["Название профиля", "Метод / Параметры"]
        )
        self.fav_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.fav_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.fav_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.fav_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.fav_table.verticalHeader().setVisible(False)
        self.fav_table.itemSelectionChanged.connect(self.update_buttons_state)

        fav_btns = QHBoxLayout()
        self.apply_fav_btn = QPushButton("✅ Применить")
        self.apply_fav_btn.setObjectName("PrimaryBtn")
        self.apply_fav_btn.setFixedHeight(36)
        self.apply_fav_btn.clicked.connect(self.apply_selected_favorite)

        self.del_fav_btn = QPushButton("🗑 Удалить")
        self.del_fav_btn.setObjectName("DangerBtn")
        self.del_fav_btn.setFixedHeight(36)
        self.del_fav_btn.clicked.connect(self.delete_selected_favorite)

        fav_btns.addWidget(self.apply_fav_btn, stretch=1)
        fav_btns.addWidget(self.del_fav_btn)

        fav_layout.addWidget(self.fav_table, stretch=1)
        fav_layout.addLayout(fav_btns)

        # --- Вкладка 2: История тестов ---
        hist_tab = QWidget()
        hist_layout = QVBoxLayout(hist_tab)
        hist_layout.setContentsMargins(8, 12, 8, 8)
        hist_layout.setSpacing(10)

        self.hist_table = QTableWidget(0, 3)
        self.hist_table.setHorizontalHeaderLabels(
            ["Стратегия", "Пинг", "Время теста"]
        )
        self.hist_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.hist_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.hist_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.hist_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.hist_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.hist_table.verticalHeader().setVisible(False)
        self.hist_table.itemSelectionChanged.connect(self.update_buttons_state)

        hist_btns = QHBoxLayout()
        self.apply_hist_btn = QPushButton("✅ Применить")
        self.apply_hist_btn.setObjectName("PrimaryBtn")
        self.apply_hist_btn.setFixedHeight(36)
        self.apply_hist_btn.clicked.connect(self.apply_selected_history)

        self.move_fav_btn = QPushButton("⭐ В избранное")
        self.move_fav_btn.setObjectName("SecondaryBtn")
        self.move_fav_btn.setFixedHeight(36)
        self.move_fav_btn.clicked.connect(self.move_history_to_favorites)

        self.clear_hist_btn = QPushButton("Очистить историю")
        self.clear_hist_btn.setObjectName("SecondaryBtn")
        self.clear_hist_btn.setFixedHeight(36)
        self.clear_hist_btn.clicked.connect(self.clear_all_history)

        hist_btns.addWidget(self.apply_hist_btn, stretch=1)
        hist_btns.addWidget(self.move_fav_btn)
        hist_btns.addWidget(self.clear_hist_btn)

        hist_layout.addWidget(self.hist_table, stretch=1)
        hist_layout.addLayout(hist_btns)

        self.tabs.addTab(fav_tab, "⭐ Избранное")
        self.tabs.addTab(hist_tab, "🕒 История тестов")
        self.tabs.currentChanged.connect(self.update_buttons_state)

        layout.addWidget(self.tabs, stretch=1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Закрыть")
        close_btn.setObjectName("SecondaryBtn")
        close_btn.setFixedHeight(34)
        close_btn.clicked.connect(self.close)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

    def apply_styles(self):
        self.setStyleSheet("""
            QDialog, QWidget {
                background-color: #111318;
                color: #e2e2e9;
                font-family: 'Segoe UI', sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #282c37;
                border-radius: 10px;
                background-color: #161920;
            }
            QTabBar::tab {
                background-color: #1b1e26;
                color: #9aa0a6;
                padding: 8px 18px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 4px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background-color: #252b38;
                color: #ffffff;
                border-bottom: 2px solid #3b82f6;
            }
            QTableWidget {
                background-color: #111318;
                border: 1px solid #252934;
                border-radius: 8px;
                gridline-color: #20242e;
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
            #DangerBtn {
                background-color: #3b1d1e;
                color: #f28b82;
                border: 1px solid #5c2b2d;
                border-radius: 8px;
                padding: 0px 14px;
            }
            #DangerBtn:hover {
                background-color: #4f2527;
            }
            #DangerBtn:disabled {
                background-color: #1b1e26;
                color: #5f6368;
                border-color: #252830;
            }
        """)

    def reload_all(self):
        self.favorites_data = get_favorites()
        self.fav_table.setRowCount(0)
        for strat in self.favorites_data:
            row = self.fav_table.rowCount()
            self.fav_table.insertRow(row)
            stype = strat.get("type", "cascade")
            ttl = strat.get("ttl_list", "—")
            info = (
                f"{stype} | TTL: {ttl}"
                if stype != "multisplit"
                else "Clean MultiSplit"
            )
            self.fav_table.setItem(
                row, 0, QTableWidgetItem(f"⭐ {strat.get('name', 'Профиль')}")
            )
            self.fav_table.setItem(row, 1, QTableWidgetItem(info))

        self.history_data = get_history()
        self.hist_table.setRowCount(0)
        for item in self.history_data:
            row = self.hist_table.rowCount()
            self.hist_table.insertRow(row)
            strat = item.get("strategy", {})
            ms = item.get("ping_ms", 0)
            ts = item.get("timestamp", "—")

            ping_item = QTableWidgetItem(f"{ms} мс")
            ping_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            ping_item.setForeground(QColor("#81c995"))

            self.hist_table.setItem(
                row, 0, QTableWidgetItem(strat.get("name", "Тест"))
            )
            self.hist_table.setItem(row, 1, ping_item)
            self.hist_table.setItem(row, 2, QTableWidgetItem(ts))

        self.update_buttons_state()

    def update_buttons_state(self):
        fav_sel = len(self.fav_table.selectionModel().selectedRows()) > 0
        self.apply_fav_btn.setEnabled(fav_sel)
        self.del_fav_btn.setEnabled(fav_sel)

        hist_sel = len(self.hist_table.selectionModel().selectedRows()) > 0
        self.apply_hist_btn.setEnabled(hist_sel)
        self.move_fav_btn.setEnabled(hist_sel)

    def apply_selected_favorite(self):
        rows = self.fav_table.selectionModel().selectedRows()
        if rows:
            strat = self.favorites_data[rows.row()]
            self.on_apply_callback(strat)
            self.accept()

    def delete_selected_favorite(self):
        rows = self.fav_table.selectionModel().selectedRows()
        if rows:
            strat = self.favorites_data[rows.row()]
            remove_from_favorites(strat.get("name", ""))
            self.reload_all()

    def apply_selected_history(self):
        rows = self.hist_table.selectionModel().selectedRows()
        if rows:
            strat = self.history_data[rows.row()].get("strategy")
            if strat:
                self.on_apply_callback(strat)
                self.accept()

    def move_history_to_favorites(self):
        rows = self.hist_table.selectionModel().selectedRows()
        if rows:
            strat = self.history_data[rows.row()].get("strategy")
            if strat:
                add_to_favorites(strat)
                self.reload_all()
                self.tabs.setCurrentIndex(0)

    def clear_all_history(self):
        clear_history()
        self.reload_all()
