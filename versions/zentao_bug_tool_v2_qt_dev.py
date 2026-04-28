#!/usr/bin/env python3
"""
禅道BUG分析工具 - Mac风格UI
"""

import csv
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QPushButton,
    QFileDialog, QMessageBox, QDialog, QCheckBox, QLineEdit,
    QSplitter, QStatusBar, QToolBar, QComboBox, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize, QUrl
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtGui import QDesktopServices


class ZentaoBugTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_stats = None
        self.focus_list = []
        self.bug_details = []

        self.init_ui()
        self.load_focus_list()

    def init_ui(self):
        self.setWindowTitle("禅道BUG分析")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(900, 600)

        # Mac风格样式
        self.set_mac_style()

        central = QWidget()
        self.setCentralWidget(central)
        central.setObjectName("central")

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 顶部工具栏
        toolbar = self.create_toolbar()
        main_layout.addWidget(toolbar)

        # 内容区域
        content = QSplitter(Qt.Orientation.Horizontal)

        # 左侧面板
        left_widget = QWidget()
        left_widget.setObjectName("panel")
        left_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)

        # 搜索框
        search_frame = QFrame()
        search_frame.setObjectName("searchFrame")
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(8, 6, 8, 6)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("搜索人员...")
        self.search_input.textChanged.connect(self.on_search_changed)
        search_layout.addWidget(self.search_input)
        left_layout.addWidget(search_frame)

        # 筛选条件
        filter_frame = QFrame()
        filter_frame.setObjectName("filterFrame")
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(8, 6, 8, 6)
        filter_layout.setSpacing(12)

        self.severity_filter = QComboBox()
        self.severity_filter.setObjectName("filterCombo")
        self.severity_filter.addItems(["全部", "A级", "B级", "C级", "D级"])
        self.severity_filter.setCurrentText("全部")
        self.severity_filter.currentTextChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(QLabel("严重:"))
        filter_layout.addWidget(self.severity_filter)

        self.status_filter = QComboBox()
        self.status_filter.setObjectName("filterCombo")
        self.status_filter.addItems(["全部", "激活", "已解决", "已关闭"])
        self.status_filter.setCurrentText("全部")
        self.status_filter.currentTextChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(QLabel("状态:"))
        filter_layout.addWidget(self.status_filter)

        filter_layout.addStretch()
        left_layout.addWidget(filter_frame)

        # 人员统计表格
        self.person_table = QTableWidget()
        self.person_table.setObjectName("dataTable")
        self.person_table.setColumnCount(6)
        self.person_table.setHorizontalHeaderLabels(["人员", "总数", "活跃", "A级", "B级", "C/D级"])
        # 设置列宽策略：前5列固定，最后一列拉伸填充
        for col in range(5):
            self.person_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        self.person_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.person_table.setColumnWidth(0, 100)  # 人员
        self.person_table.setColumnWidth(1, 50)   # 总数
        self.person_table.setColumnWidth(2, 50)   # 活跃
        self.person_table.setColumnWidth(3, 50)   # A级
        self.person_table.setColumnWidth(4, 50)   # B级
        self.person_table.horizontalHeader().setMinimumSectionSize(40)
        self.person_table.verticalHeader().setVisible(False)
        self.person_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.person_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.person_table.itemSelectionChanged.connect(self.on_person_selection_changed)
        self.person_table.setSortingEnabled(True)
        self.person_table.setShowGrid(False)
        self.person_table.setAlternatingRowColors(True)
        self.person_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        left_layout.addWidget(self.person_table)

        content.addWidget(left_widget)

        # 右侧面板
        right_widget = QWidget()
        right_widget.setObjectName("panel")
        right_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(12)

        # BUG详情标题
        self.detail_label = QLabel("BUG详情")
        self.detail_label.setObjectName("panelTitle")
        right_layout.addWidget(self.detail_label)

        # BUG详情表格
        self.bug_table = QTableWidget()
        self.bug_table.setObjectName("dataTable")
        self.bug_table.setColumnCount(4)
        self.bug_table.setHorizontalHeaderLabels(["Bug ID", "严重", "状态", "标题"])
        # 设置列宽策略：前3列固定，最后一列拉伸填充
        for col in range(3):
            self.bug_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        self.bug_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.bug_table.setColumnWidth(0, 80)   # Bug ID
        self.bug_table.setColumnWidth(1, 50)   # 严重
        self.bug_table.setColumnWidth(2, 80)   # 状态
        self.bug_table.horizontalHeader().setMinimumSectionSize(40)
        self.bug_table.verticalHeader().setVisible(False)
        self.bug_table.setSortingEnabled(True)
        self.bug_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.bug_table.setShowGrid(False)
        self.bug_table.setAlternatingRowColors(True)
        self.bug_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.bug_table.cellClicked.connect(self.on_bug_table_clicked)
        right_layout.addWidget(self.bug_table)

        content.addWidget(right_widget)
        content.setStretchFactor(0, 1)
        content.setStretchFactor(1, 2)

        main_layout.addWidget(content)

        # 底部状态栏
        self.status_bar = QStatusBar()
        self.status_bar.setObjectName("statusBar")
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    def set_mac_style(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f7;
            }
            #central {
                background-color: #f5f5f7;
            }
            QWidget#panel {
                background-color: #ffffff;
                border-radius: 12px;
            }
            QLabel {
                color: #1d1d1f;
                font-size: 13px;
            }
            #panelTitle {
                font-size: 16px;
                font-weight: 600;
                color: #1d1d1f;
            }
            QTableWidget#dataTable {
                background-color: #ffffff;
                border: 1px solid #e5e5e7;
                border-radius: 8px;
                padding: 4px;
                gridline-color: transparent;
                alternate-background-color: #fafafa;
            }
            QTableWidget#dataTable::item {
                padding: 10px 8px;
                color: #1d1d1f;
                background-color: #ffffff;
            }
            QTableWidget#dataTable::item:alternate {
                background-color: #f8f8fa;
            }
            QTableWidget#dataTable::item:selected {
                background-color: #e8f0fc;
                color: #1d1d1f;
                border: none;
                outline: none;
            }
            QTableWidget#dataTable::item:focus {
                border: none;
                outline: none;
            }
            QTableWidget#dataTable::item:selected:focus {
                background-color: #d0e0f0;
                border: none;
                outline: none;
            }
            QHeaderView::section {
                background-color: #fafafa;
                color: #6e6e73;
                padding: 10px 8px;
                border: none;
                border-bottom: 2px solid #e5e5e7;
                font-weight: 500;
                font-size: 11px;
                text-transform: uppercase;
            }
            QFrame#searchFrame {
                background-color: #f0f0f5;
                border-radius: 8px;
            }
            QFrame#filterFrame {
                background-color: #f0f0f5;
                border-radius: 8px;
            }
            QLineEdit#searchInput {
                background-color: transparent;
                border: none;
                padding: 8px;
                font-size: 13px;
                color: #1d1d1f;
            }
            QLineEdit#searchInput::placeholder {
                color: #86868b;
            }
            QComboBox#filterCombo {
                background-color: #ffffff;
                border: 1px solid #d1d1d6;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 12px;
                color: #1d1d1f;
            }
            QComboBox#filterCombo:hover {
                border-color: #b1b1b6;
            }
            QComboBox#filterCombo::drop-down {
                border: none;
                width: 18px;
            }
            QComboBox#filterCombo::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #6e6e73;
                margin-right: 4px;
            }
            QComboBox#filterCombo QAbstractItemView {
                background-color: #ffffff;
                border: 1px solid #e5e5e7;
                border-radius: 6px;
                selection-background-color: #007aff;
                color: #1d1d1f;
            }
            QComboBox#filterCombo QAbstractItemView::item {
                color: #1d1d1f;
                padding: 4px;
            }
            QPushButton {
                background-color: #007aff;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #0077ed;
            }
            QPushButton:pressed {
                background-color: #0064d9;
            }
            QPushButton[secondary="true"] {
                background-color: #f0f0f5;
                color: #1d1d1f;
            }
            QPushButton[secondary="true"]:hover {
                background-color: #e5e5ea;
            }
            QToolBar {
                background-color: #ffffff;
                border: none;
                padding: 8px 16px;
                spacing: 12px;
            }
            QStatusBar#statusBar {
                background-color: #f5f5f7;
                color: #6e6e73;
                border-top: 1px solid #e5e5e7;
            }
            QScrollBar:vertical {
                background-color: transparent;
                width: 8px;
                margin: 4px 0;
            }
            QScrollBar::handle:vertical {
                background-color: #c7c7cc;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #b0b0b5;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background-color: transparent;
                height: 8px;
                margin: 0 4px;
            }
            QScrollBar::handle:horizontal {
                background-color: #c7c7cc;
                border-radius: 4px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #b0b0b5;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QMessageBox {
                background-color: #ffffff;
            }
            QMessageBox QLabel {
                color: #1d1d1f;
                font-size: 13px;
                padding: 10px;
            }
            QMessageBox QPushButton {
                background-color: #007aff;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 6px;
                font-size: 13px;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: #0077ed;
            }
            QMessageBox QPushButton[text="否"] {
                background-color: #f0f0f5;
                color: #1d1d1f;
            }
            QMessageBox QPushButton[text="否"]:hover {
                background-color: #e5e5ea;
            }
        """)

    def create_toolbar(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)

        # 标题
        title = QLabel("禅道BUG分析")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: #1d1d1f; padding: 0 8px;")
        toolbar.addWidget(title)

        toolbar.addSeparator()

        # 按钮
        self.open_btn = QPushButton("📂 打开文件")
        self.open_btn.clicked.connect(self.open_file)
        toolbar.addWidget(self.open_btn)

        self.focus_btn = QPushButton("⭐ 关注人员")
        self.focus_btn.clicked.connect(self.open_focus_window)
        toolbar.addWidget(self.focus_btn)

        self.file_label = QLabel()
        self.file_label.setStyleSheet("color: #86868b; font-size: 12px; padding: 0 8px;")
        toolbar.addWidget(self.file_label)

        # 添加伸缩spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        # 统计
        self.stats_label = QLabel("总计: 0 BUG | 0 人")
        self.stats_label.setStyleSheet("color: #6e6e73; font-size: 12px;")
        toolbar.addWidget(self.stats_label)

        toolbar.addSeparator()

        self.export_btn = QPushButton("💾 导出")
        self.export_btn.setProperty("secondary", True)
        self.export_btn.clicked.connect(self.export_report)
        toolbar.addWidget(self.export_btn)

        return toolbar

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择BUG导出文件",
            str(Path.home() / "Desktop"),
            "Excel文件 (*.xlsx);;CSV文件 (*.csv);;所有文件 (*.*)"
        )
        if path:
            self.analyze_file(path)

    def analyze_file(self, path):
        try:
            rows, hi = self.read_excel_file(path) if path.endswith('.xlsx') else self.read_csv_file(path)

            headers = rows[hi]
            hi_map = self.parse_headers(headers)

            idx = {k: hi_map.get(k, -1) for k in ['id', 'title', 'priority', 'severity', 'assignedto', 'status']}

            bugs = []
            for row in rows[hi + 1:]:
                if not row or not any(v and v.strip() for v in row if v):
                    continue
                bug_id = row[idx['id']].strip() if idx['id'] >= 0 and idx['id'] < len(row) else ''
                if not bug_id:
                    continue
                bugs.append({
                    'id': bug_id,
                    'title': row[idx['title']].strip() if idx['title'] >= 0 and idx['title'] < len(row) else '',
                    'priority': self.parse_priority(row[idx['priority']].strip() if idx['priority'] >= 0 and idx['priority'] < len(row) else '3'),
                    'severity': self.parse_priority(row[idx['severity']].strip() if idx['severity'] >= 0 and idx['severity'] < len(row) else ''),
                    'assignedTo': row[idx['assignedto']].strip() if idx['assignedto'] >= 0 and idx['assignedto'] < len(row) else '未分配',
                    'status': row[idx['status']].strip() if idx['status'] >= 0 and idx['status'] < len(row) else ''
                })

            if not bugs:
                QMessageBox.warning(self, "警告", "未解析到有效BUG数据")
                return

            owner_stats = defaultdict(lambda: {"total": 0, "bugs": [], "severity_A": 0, "severity_B": 0, "severity_C": 0, "severity_D": 0, "active": 0, "resolved": 0, "closed": 0})
            for b in bugs:
                o = b['assignedTo']
                s = b.get('severity', 3)
                st = b.get('status', '').lower()
                # 活跃：不是closed也不是resolved
                is_act = 'closed' not in st and 'resolved' not in st
                # 已解决：包含resolved或"已解决"
                is_resolved = 'resolved' in st or '已解决' in st
                # 已关闭：包含closed
                is_closed = 'closed' in st
                owner_stats[o]["total"] += 1
                owner_stats[o]["bugs"].append(b)
                if s == 1: owner_stats[o]["severity_A"] += 1
                elif s == 2: owner_stats[o]["severity_B"] += 1
                elif s == 3: owner_stats[o]["severity_C"] += 1
                else: owner_stats[o]["severity_D"] += 1
                if is_act: owner_stats[o]["active"] += 1
                if is_resolved: owner_stats[o]["resolved"] += 1
                if is_closed: owner_stats[o]["closed"] += 1

            self.current_stats = {'bugs': bugs, 'owner_stats': dict(owner_stats), 'filename': os.path.basename(path)}
            self.file_label.setText(os.path.basename(path))
            self.stats_label.setText(f"总计: {len(bugs)} BUG | {len(owner_stats)} 人")

            self.update_person_table()
            self.update_focus_btn()
            self.auto_load_focus_list(path)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"解析文件失败:\n{str(e)}")

    def parse_headers(self, headers):
        hi_map = {}
        for i, h in enumerate(headers):
            hc = str(h).strip()
            if not hc:
                continue
            hl = hc.lower()
            hi_map[hc] = i
            for k, als in [('id', ['bug编号', 'Bug编号', '编号', 'id']),
                           ('title', ['bug标题', 'Bug标题', '标题', 'title']),
                           ('status', ['bug状态', 'Bug状态', '子状态', 'status', '状态']),
                           ('priority', ['优先级', 'Bug优先级', 'priority', 'pri']),
                           ('severity', ['严重程度', 'Bug严重程度', 'severity']),
                           ('assignedto', ['指派给', '批示复制', '指派人', '负责人', 'assignedto', 'assigned'])]:
                if k not in hi_map:
                    for a in als:
                        if hl == a.lower() or hl.endswith(a.lower()):
                            hi_map[k] = i
                            break
        return hi_map

    def read_excel_file(self, filepath):
        with zipfile.ZipFile(filepath, 'r') as z:
            strings = []
            if 'xl/sharedStrings.xml' in z.namelist():
                root = ET.fromstring(z.read('xl/sharedStrings.xml'))
                ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
                for si in root.findall(f'{{{ns}}}si'):
                    t = si.find(f'{{{ns}}}t')
                    if t is not None:
                        strings.append(t.text or '')
                    else:
                        parts = [r.find(f'{{{ns}}}t') for r in si.findall(f'{{{ns}}}r')]
                        strings.append(''.join(p.text for p in parts if p is not None))
            root = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
            ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
            rows = []
            for row in root.findall(f'.//{{{ns}}}row'):
                rd = []
                for c in row.findall(f'{{{ns}}}c'):
                    t, v = c.get('t'), c.find(f'{{{ns}}}v')
                    rd.append(strings[int(v.text)] if t == 's' and v is not None else (v.text or '' if v is not None else ''))
                rows.append(rd)
        hi, mne = 0, 0
        for i, r in enumerate(rows):
            ne = len([v for v in r if v and v.strip()])
            if ne > mne:
                mne, hi = ne, i
        return rows, hi

    def read_csv_file(self, filepath):
        with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
            rows = list(csv.reader(f))
        hi = 0
        for i, r in enumerate(rows):
            if any(v and v.strip() for v in r):
                hi = i
                break
        return rows, hi

    def parse_priority(self, s):
        if not s:
            return 3
        s = str(s).strip()
        import re
        m = re.search(r'#(\d+)', s)
        if m:
            return int(m.group(1))
        try:
            return int(s)
        except:
            return 3

    def update_person_table(self):
        if not self.current_stats:
            return

        owner_stats = self.current_stats['owner_stats']
        search = self.search_input.text().lower()
        severity_filter = self.severity_filter.currentText()
        status_filter = self.status_filter.currentText()

        if self.focus_list:
            display_stats = {k: v for k, v in owner_stats.items() if k in self.focus_list}
        else:
            display_stats = owner_stats

        if search:
            display_stats = {k: v for k, v in display_stats.items() if search in k.lower()}

        # 根据状态筛选人员
        if status_filter == "激活":
            display_stats = {k: v for k, v in display_stats.items() if v.get('active', 0) > 0}
        elif status_filter == "已解决":
            display_stats = {k: v for k, v in display_stats.items() if v.get('resolved', 0) > 0}
        elif status_filter == "已关闭":
            display_stats = {k: v for k, v in display_stats.items() if v.get('closed', 0) > 0}

        if severity_filter != "全部":
            sev_key = f"severity_{severity_filter[0]}"
            display_stats = {k: v for k, v in display_stats.items() if v.get(sev_key, 0) > 0}

        self.person_table.setSortingEnabled(False)
        self.person_table.setRowCount(len(display_stats))

        sorted_owners = sorted(display_stats.items(), key=lambda x: x[1]['total'], reverse=True)
        for row, (owner, data) in enumerate(sorted_owners):
            # 人员列左对齐
            item0 = QTableWidgetItem(owner)
            item0.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.person_table.setItem(row, 0, item0)
            # 数字列居中
            for col, val in [(1, data['total']), (2, data['active']), (3, data['severity_A']), (4, data['severity_B']), (5, data['severity_C'] + data['severity_D'])]:
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter)
                self.person_table.setItem(row, col, item)

            # 严重BUG高亮
            if data['severity_A'] > 0:
                for col in [3, 4, 5]:
                    itm = self.person_table.item(row, col)
                    if itm and int(itm.text()) > 0:
                        itm.setForeground(QColor('#ff3b30'))

        self.person_table.setSortingEnabled(True)
        self.person_table.sortItems(1, Qt.SortOrder.DescendingOrder)

        self.stats_label.setText(f"显示: {len(display_stats)}/{len(owner_stats)} 人")

    def on_person_selection_changed(self):
        selected = self.person_table.selectedItems()
        if not selected:
            self.bug_table.setRowCount(0)
            self.detail_label.setText("BUG详情")
            return

        selected_rows = set()
        for item in selected:
            selected_rows.add(item.row())

        owner_stats = self.current_stats['owner_stats']
        all_bugs = []
        selected_owners = []

        for row in selected_rows:
            owner = self.person_table.item(row, 0).text()
            selected_owners.append(owner)
            all_bugs.extend(owner_stats.get(owner, {}).get('bugs', []))

        status_filter = self.status_filter.currentText()
        severity_filter = self.severity_filter.currentText()

        bugs = all_bugs
        if status_filter == "激活":
            # 激活：既不是已关闭也不是已解决
            bugs = [b for b in bugs if 'closed' not in b.get('status', '').lower() and 'resolved' not in b.get('status', '').lower() and '已解决' not in b.get('status', '')]
        elif status_filter == "已解决":
            # 已解决：包含resolved或"已解决"
            bugs = [b for b in bugs if 'resolved' in b.get('status', '').lower() or '已解决' in b.get('status', '')]
        elif status_filter == "已关闭":
            bugs = [b for b in bugs if 'closed' in b.get('status', '').lower()]

        if severity_filter != "全部":
            sev_val = {'A级': 1, 'B级': 2, 'C级': 3, 'D级': 4}.get(severity_filter, 0)
            bugs = [b for b in bugs if b.get('severity', 3) == sev_val]

        self.bug_table.setSortingEnabled(False)
        self.bug_table.setRowCount(len(bugs))

        if len(selected_owners) == 1:
            owner_text = selected_owners[0]
        else:
            owner_text = f"{len(selected_owners)}人"
        self.detail_label.setText(f"BUG详情 - {owner_text} ({len(bugs)}条)")

        for i, b in enumerate(bugs):
            sev = 'A' if b.get('severity', 3) == 1 else 'B' if b.get('severity', 3) == 2 else 'C'
            # Bug ID居中
            item0 = QTableWidgetItem(b['id'])
            item0.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter)
            self.bug_table.setItem(i, 0, item0)
            # 严重居中
            item1 = QTableWidgetItem(sev)
            item1.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter)
            self.bug_table.setItem(i, 1, item1)
            # 状态居中
            item2 = QTableWidgetItem(b.get('status', ''))
            item2.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter)
            self.bug_table.setItem(i, 2, item2)
            # 标题左对齐
            item3 = QTableWidgetItem(b.get('title', '')[:80])
            item3.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.bug_table.setItem(i, 3, item3)

            if b.get('severity', 3) == 1:
                for col in range(4):
                    self.bug_table.item(i, col).setForeground(QColor('#ff3b30'))
                    self.bug_table.item(i, col).setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
            elif b.get('severity', 3) == 2:
                for col in range(4):
                    self.bug_table.item(i, col).setForeground(QColor('#ff9500'))

        self.bug_table.setSortingEnabled(True)

    def on_search_changed(self):
        self.update_person_table()

    def on_filter_changed(self):
        self.update_person_table()
        if self.person_table.selectedItems():
            self.on_person_selection_changed()

    def on_bug_table_clicked(self, row, column):
        """点击BUG详情打开禅道网页"""
        if row < 0:
            return
        bug_id_item = self.bug_table.item(row, 0)
        if bug_id_item is None:
            return
        bug_id = bug_id_item.text().strip()
        if bug_id:
            url = f"https://zd.bicv.com/bug-view-{bug_id}.html"
            reply = QMessageBox.question(
                self, '确认打开链接',
                f'确定要在浏览器中打开此BUG吗？\n\n{url}',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl(url))

    def open_focus_window(self):
        if not self.current_stats:
            QMessageBox.warning(self, "提示", "请先加载数据")
            return
        dialog = FocusPersonDialog(self, self.current_stats['owner_stats'], self.focus_list)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.focus_list = dialog.get_focus_list()
            self.update_person_table()
            self.update_focus_btn()
            self.save_focus_list()

    def update_focus_btn(self):
        count = len(self.focus_list) if self.focus_list else 0
        self.focus_btn.setText(f"⭐ 关注人员 ({count})" if count else "⭐ 关注人员")

    def auto_load_focus_list(self, file_path):
        """根据文件名自动加载对应的关注列表"""
        import re
        filename = os.path.basename(file_path)

        # 匹配项目标识：C62X、C52X、B30X-E11等
        # 优先匹配较长项目名，所以按长度降序排列
        patterns = [
            r'B\d+X?-E\d+',  # B30X-E11 格式
            r'C\d+X',         # C62X、C52X 格式
            r'\w+',           # 兜底匹配
        ]

        project_id = None
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                matched = match.group(0)
                # 跳过太短的匹配
                if len(matched) >= 4:
                    project_id = matched.upper()
                    break

        if project_id:
            list_file = Path(__file__).parent / f"{project_id}list.json"
            if list_file.exists():
                try:
                    with open(list_file, 'r', encoding='utf-8') as f:
                        loaded_list = json.load(f)
                    self.focus_list = loaded_list
                    self.update_person_table()
                    self.update_focus_btn()
                    self.status_bar.showMessage(f"已自动加载关注列表: {list_file.name}")
                    return
                except:
                    pass

        # 如果没有匹配的列表，清空关注列表
        self.focus_list = []

    def load_focus_list(self):
        default_path = Path(__file__).parent / "focus_list.json"
        if default_path.exists():
            try:
                with open(default_path, 'r', encoding='utf-8') as f:
                    self.focus_list = json.load(f)
            except:
                self.focus_list = []

    def save_focus_list(self):
        """根据当前文件名中的项目标识保存关注列表"""
        import re
        # 从当前文件名提取项目标识
        filename = self.current_stats.get('filename', '') if self.current_stats else ''

        project_id = None
        patterns = [
            r'B\d+X?-E\d+',  # B30X-E11 格式
            r'C\d+X',         # C62X、C52X 格式
        ]
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                matched = match.group(0)
                if len(matched) >= 4:
                    project_id = matched.upper()
                    break

        if project_id:
            list_path = Path(__file__).parent / f"{project_id}list.json"
        else:
            list_path = Path(__file__).parent / "focus_list.json"

        try:
            with open(list_path, 'w', encoding='utf-8') as f:
                json.dump(self.focus_list, f, ensure_ascii=False, indent=2)
            self.status_bar.showMessage(f"已保存关注列表: {list_path.name}")
        except Exception as e:
            QMessageBox.warning(self, "提示", f"保存失败:\n{str(e)}")

    def export_report(self):
        if not self.current_stats:
            QMessageBox.warning(self, "提示", "请先加载数据")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "导出报表",
            f"禅道BUG统计_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "文本文件 (*.txt)"
        )
        if not path:
            return

        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write("禅道BUG统计分析报告\n")
                f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"文件名: {self.current_stats['filename']}\n")
                f.write(f"BUG总数: {len(self.current_stats['bugs'])}\n\n")

                owner_stats = self.current_stats['owner_stats']
                display_stats = {k: v for k, v in owner_stats.items() if k in self.focus_list} if self.focus_list else owner_stats
                sorted_owners = sorted(display_stats.items(), key=lambda x: x[1]['total'], reverse=True)

                for owner, data in sorted_owners:
                    f.write(f"{owner}: {data['total']}个BUG")
                    if data['severity_A'] > 0:
                        f.write(f" [A级x{data['severity_A']}]")
                    f.write("\n")

            QMessageBox.information(self, "成功", f"报表已导出:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败:\n{str(e)}")


class FocusPersonDialog(QDialog):
    def __init__(self, parent, owner_stats, focus_list):
        super().__init__(parent)
        self.owner_stats = owner_stats
        self.focus_list = set(focus_list)
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("关注人员")
        self.setGeometry(200, 150, 700, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f7;
            }
            QWidget {
                background-color: #ffffff;
                color: #1d1d1f;
                font-family: -apple-system, BlinkMacSystemFont, Microsoft YaHei;
                font-size: 13px;
            }
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #e5e5e7;
                border-radius: 8px;
                padding: 4px;
                alternate-background-color: #f8f8fa;
            }
            QTableWidget::item:alternate {
                background-color: #f8f8fa;
            }
            QTableWidget::item:selected {
                background-color: #e8f0fc;
                color: #1d1d1f;
                border: none;
                outline: none;
            }
            QTableWidget::item:focus {
                border: none;
                outline: none;
            }
            QHeaderView::section {
                background-color: #fafafa;
                color: #6e6e73;
                padding: 10px 8px;
                border: none;
                border-bottom: 2px solid #e5e5e7;
                font-weight: 500;
                font-size: 11px;
            }
            QPushButton {
                background-color: #007aff;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #0077ed;
            }
            QCheckBox {
                spacing: 8px;
                color: #1d1d1f;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 2px solid #8e8e93;
                background-color: #ffffff;
            }
            QCheckBox::indicator:checked {
                background-color: #34c759;
                border-color: #34c759;
            }
            QCheckBox:hover::indicator {
                border-color: #007aff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 标题
        title = QLabel("选择关注人员")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: #1d1d1f;")
        layout.addWidget(title)

        # 工具栏
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.setProperty("secondary", True)
        self.select_all_btn.clicked.connect(self.select_all)
        toolbar_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("取消全选")
        self.deselect_all_btn.setProperty("secondary", True)
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        toolbar_layout.addWidget(self.deselect_all_btn)

        toolbar_layout.addStretch()

        self.count_label = QLabel(f"已选择: {len(self.focus_list)} 人")
        self.count_label.setStyleSheet("color: #86868b;")
        toolbar_layout.addWidget(self.count_label)

        layout.addWidget(toolbar)

        # 人员表格 - 第一列显示✔表示选中
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["", "人员", "BUG数"])
        for col in range(2):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 40)   # 勾选列
        self.table.setColumnWidth(1, 150)  # 人员
        self.table.horizontalHeader().setMinimumSectionSize(40)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(False)  # 禁用排序避免点击后行索引错乱
        self.table.setAlternatingRowColors(True)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        sorted_owners = sorted(self.owner_stats.items(), key=lambda x: x[1]['total'], reverse=True)
        self.table.setRowCount(len(sorted_owners))
        self.owner_by_row = {}
        self.check_items = {}

        for row, (owner, data) in enumerate(sorted_owners):
            self.owner_by_row[row] = owner

            # 第一列：显示✔或空白
            check_item = QTableWidgetItem("✔" if owner in self.focus_list else "")
            check_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            check_item.setFlags(check_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            check_item.setForeground(QColor('#34c759') if owner in self.focus_list else QColor('#1d1d1f'))
            self.table.setItem(row, 0, check_item)
            self.check_items[owner] = check_item

            # 人员左对齐
            name_item = QTableWidgetItem(owner)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, name_item)

            # BUG数居中
            count_item = QTableWidgetItem(str(data['total']))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter)
            count_item.setFlags(count_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, count_item)

        # 处理点击事件 - 使用item直接获取owner
        self.table.cellClicked.connect(self.on_table_cell_clicked)

        layout.addWidget(self.table)

        # 底部按钮
        bottom = QWidget()
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        save_btn = QPushButton("💾 保存列表")
        save_btn.setProperty("secondary", True)
        save_btn.clicked.connect(self.save_focus_list_dialog)
        bottom_layout.addWidget(save_btn)

        load_btn = QPushButton("📂 加载列表")
        load_btn.setProperty("secondary", True)
        load_btn.clicked.connect(self.load_focus_list_dialog)
        bottom_layout.addWidget(load_btn)

        bottom_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setProperty("secondary", True)
        cancel_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(ok_btn)

        layout.addWidget(bottom)

    def on_checkbox_changed(self, owner, state):
        if state:
            self.focus_list.add(owner)
        else:
            self.focus_list.discard(owner)
        self.count_label.setText(f"已选择: {len(self.focus_list)} 人")

    def on_table_cell_clicked(self, row, column):
        # 通过点击的item直接获取owner，避免排序后row索引错乱
        clicked_item = self.table.item(row, 1)  # 第2列是人员名称
        if clicked_item is None:
            return
        owner = clicked_item.text()
        if owner not in self.owner_stats:
            return
        if owner in self.focus_list:
            self.focus_list.discard(owner)
            self.check_items[owner].setText("")
            self.check_items[owner].setForeground(QColor('#1d1d1f'))
        else:
            self.focus_list.add(owner)
            self.check_items[owner].setText("✔")
            self.check_items[owner].setForeground(QColor('#34c759'))
        self.count_label.setText(f"已选择: {len(self.focus_list)} 人")

    def select_all(self):
        for owner in self.owner_stats.keys():
            self.focus_list.add(owner)
            if owner in self.check_items:
                self.check_items[owner].setText("✔")
                self.check_items[owner].setForeground(QColor("#34c759"))
        self.count_label.setText(f"已选择: {len(self.focus_list)} 人")

    def deselect_all(self):
        self.focus_list.clear()
        for item in self.check_items.values():
            item.setText("")
            item.setForeground(QColor('#1d1d1f'))
        self.count_label.setText(f"已选择: 0 人")

    def save_focus_list_dialog(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存关注列表",
            "focus_list.json",
            "JSON文件 (*.json)"
        )
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(list(self.focus_list), f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "成功", f"已保存到:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败:\n{str(e)}")

    def load_focus_list_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "加载关注列表",
            "",
            "JSON文件 (*.json)"
        )
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    loaded_list = json.load(f)
                self.focus_list = set(loaded_list)
                for owner, item in self.check_items.items():
                    item.setText("✔" if owner in self.focus_list else "")
                    item.setForeground(QColor('#34c759') if owner in self.focus_list else QColor('#1d1d1f'))
                self.count_label.setText(f"已选择: {len(self.focus_list)} 人")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载失败:\n{str(e)}")

    def get_focus_list(self):
        return list(self.focus_list)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("禅道BUG分析")
    window = ZentaoBugTool()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
