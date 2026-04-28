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
from datetime import datetime, timedelta
from pathlib import Path
import threading
import time
import logging

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QPushButton,
    QFileDialog, QMessageBox, QDialog, QCheckBox, QLineEdit,
    QSplitter, QStatusBar, QToolBar, QComboBox, QFrame, QSizePolicy,
    QProgressBar, QProgressDialog, QScrollArea
)
from PyQt6.QtCore import Qt, QSize, QUrl, QTimer, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QGraphicsOpacityEffect

# 项目配置文件路径
CONFIG_DIR = os.path.dirname(__file__)
PROJECT_CONFIG_FILE = os.path.join(CONFIG_DIR, "import_projects.json")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
LOG_DIR = os.path.join(CONFIG_DIR, "logs")

# 默认下载目录
DEFAULT_DOWNLOAD_DIR = os.path.join(CONFIG_DIR, "downloads")

def get_download_dir():
    """获取下载目录（从设置文件读取或使用默认值）"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                download_dir = settings.get('download_dir', DEFAULT_DOWNLOAD_DIR)
                if os.path.exists(download_dir):
                    return download_dir
        except:
            pass
    return DEFAULT_DOWNLOAD_DIR

def set_download_dir(path):
    """保存下载目录到设置文件"""
    try:
        settings = {}
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        settings['download_dir'] = path
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存下载目录失败: {e}")
        return False

def get_download_dir_display():
    """获取下载目录的显示名称"""
    download_dir = get_download_dir()
    if download_dir == DEFAULT_DOWNLOAD_DIR:
        return "默认目录"
    return download_dir

# 配置日志
def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"app_{datetime.now().strftime('%Y%m%d')}.log")

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

def log_action(action, details=""):
    """记录用户操作"""
    msg = f"[操作] {action}"
    if details:
        msg += f" - {details}"
    logger.info(msg)


def load_import_projects():
    """加载预设项目列表，返回扁平格式 {'项目名': {'url': '...', 'focus': false}}"""
    if os.path.exists(PROJECT_CONFIG_FILE):
        try:
            with open(PROJECT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 如果是嵌套格式 {"projects": [{"name": "...", "url": "..."}]}，转为扁平格式
            if isinstance(data, dict) and 'projects' in data and isinstance(data['projects'], list):
                result = {}
                for p in data['projects']:
                    if isinstance(p, dict) and 'name' in p:
                        result[p['name']] = {'url': p.get('url', ''), 'focus': p.get('focus', False)}
                return result
            return data
        except:
            return {}
    return {}


def save_import_projects(projects):
    """保存预设项目列表，转为嵌套格式存储"""
    data = {'projects': []}
    for name, info in projects.items():
        data['projects'].append({
            'name': name,
            'url': info.get('url', ''),
            'focus': info.get('focus', False)
        })
    with open(PROJECT_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class ImportThread(QThread):
    """导入线程 - 用于非阻塞导入"""
    progress = pyqtSignal(str, int)  # 消息, 进度
    finished = pyqtSignal(str)  # 文件路径
    error = pyqtSignal(str)  # 错误信息

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url
        self.importer = None
        self._closed = False  # 防止重复关闭

    def run(self):
        """执行导入"""
        print("[ImportThread] 线程开始")
        try:
            from zentao_importer import ZentaoImporter

            print("[ImportThread] 正在导入 ZentaoImporter")
            self.progress.emit("正在连接禅道...", 5)

            self.importer = ZentaoImporter()
            if not self.importer.connect():
                self.error.emit("连接禅道失败")
                return

            def progress_callback(msg, prog):
                print(f"[ImportThread Progress] {msg} ({prog}%)")
                self.progress.emit(msg, prog)

            print("[ImportThread] 调用 navigate_and_export")
            result = self.importer.navigate_and_export(self.url, progress_callback)
            print(f"[ImportThread] navigate_and_export 返回: {result}")

            if result and os.path.exists(result):
                self.progress.emit("导入完成!", 100)
                self.finished.emit(result)
            else:
                self.error.emit("导入失败，未获取到文件")
        except Exception as e:
            print(f"[ImportThread] Exception: {e}")
            import traceback
            traceback.print_exc()
            self.error.emit(f"导入出错: {str(e)}")
        finally:
            self._safe_close()

    def _safe_close(self):
        """安全关闭，只关闭一次"""
        if not self._closed and self.importer:
            self._closed = True
            self.importer.close()
            print("[ImportThread] 浏览器已关闭")

    def cancel(self):
        """取消导入"""
        print("[ImportThread] 取消导入")
        if self.importer:
            self.importer.cancel()


class BatchDownloadThread(QThread):
    """批量下载线程 - 支持选择性下载、取消、失败记录、状态更新"""
    progress = pyqtSignal(str, int, int, int)  # 消息, 当前索引, 总数, 进度百分比
    project_status = pyqtSignal(str, str, str)  # 项目名称, 状态, 消息
    finished = pyqtSignal(list, list, float)  # 成功列表, 失败列表, 耗时(秒)
    error = pyqtSignal(str)  # 错误信息

    def __init__(self, projects, focus_list=None, parent=None):
        """
        projects: 要下载的项目列表，格式 [(project_name, url), ...]
        focus_list: 关注人员列表，用于智能排序（关注项目优先）
        """
        super().__init__(parent)
        self.projects = projects  # [(name, url), ...]
        self.focus_list = focus_list or []
        self._cancelled = False
        self._lock = threading.Lock()
        self.importer = None
        self._closed = False
        self.start_time = None

    def _is_cancelled(self):
        with self._lock:
            return self._cancelled

    def cancel(self):
        with self._lock:
            self._cancelled = True
        if self.importer:
            self.importer.cancel()

    def _get_project_priority(self, name):
        """获取项目优先级，关注项目优先返回较小数字"""
        if name in self.focus_list:
            return 0
        return 1

    def run(self):
        """执行批量下载"""
        print(f"[BatchDownload] 开始批量下载，共 {len(self.projects)} 个项目")
        self.start_time = time.time()

        # 按优先级排序：关注项目优先
        sorted_projects = sorted(self.projects, key=lambda x: (self._get_project_priority(x[0]), x[0]))
        total = len(sorted_projects)
        success_list = []
        fail_list = []

        try:
            from zentao_importer import ZentaoImporter

            for idx, (project_name, url) in enumerate(sorted_projects):
                if self._is_cancelled():
                    print("[BatchDownload] 用户取消")
                    break

                # 发送状态更新：下载中
                self.project_status.emit(project_name, 'downloading', '⬇️ 下载中')
                # 发送初始进度（当前项目刚开始，进度为0）
                self.progress.emit(f"正在下载 {idx+1}/{total}: {project_name}", idx + 1, total, 0)

                try:
                    self.importer = ZentaoImporter()
                    if not self.importer.connect():
                        fail_list.append((project_name, "连接禅道失败"))
                        self.project_status.emit(project_name, 'failed', '❌ 连接失败')
                        # 连接失败，发送进度更新（当前项目进度为0）
                        self.progress.emit(f"连接失败 {idx+1}/{total}: {project_name}", idx + 1, total, 0)
                        continue

                    result = None
                    def progress_callback(msg, prog):
                        self.progress.emit(f"正在下载 {idx+1}/{total}: {project_name}", idx + 1, total, prog)

                    result = self.importer.navigate_and_export(url, progress_callback)

                    if self._is_cancelled():
                        print("[BatchDownload] 用户取消")
                        break

                    if result and os.path.exists(result):
                        # 复制到downloads目录
                        date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                        backup_name = f"{project_name}_{date_str}.xlsx"
                        download_dir = get_download_dir()
                        os.makedirs(download_dir, exist_ok=True)
                        backup_path = os.path.join(download_dir, backup_name)
                        import shutil
                        shutil.copy2(result, backup_path)

                        # 计算文件大小
                        file_size = os.path.getsize(backup_path)
                        size_str = self._format_size(file_size)

                        success_list.append((project_name, backup_path))
                        self.project_status.emit(project_name, 'success', f'✅ {size_str}')
                        # 下载完成，发送最终进度（当前项目进度为100）
                        self.progress.emit(f"下载完成 {idx+1}/{total}: {project_name}", idx + 1, total, 100)
                    else:
                        fail_list.append((project_name, "未获取到文件"))
                        self.project_status.emit(project_name, 'failed', '❌ 无文件')
                        # 未获取到文件，发送进度更新
                        self.progress.emit(f"下载失败 {idx+1}/{total}: {project_name}", idx + 1, total, 0)

                except Exception as e:
                    error_msg = str(e)
                    print(f"[BatchDownload] 项目 {project_name} 下载失败: {error_msg}")
                    fail_list.append((project_name, error_msg))
                    self.project_status.emit(project_name, 'failed', f'❌ {error_msg[:15]}')
                    # 异常，发送进度更新
                    self.progress.emit(f"下载异常 {idx+1}/{total}: {project_name}", idx + 1, total, 0)
                finally:
                    self._safe_close()

                # 短暂休息，避免请求过快
                time.sleep(0.5)

        except Exception as e:
            print(f"[BatchDownload] 批量下载异常: {e}")
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))

        # 计算总耗时
        elapsed = time.time() - self.start_time
        print(f"[BatchDownload] 完成: 成功 {len(success_list)}, 失败 {len(fail_list)}, 耗时 {elapsed:.1f}秒")
        self.finished.emit(success_list, fail_list, elapsed)

    def _format_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.1f}KB"
        else:
            return f"{size_bytes/1024/1024:.1f}MB"

    def _safe_close(self):
        """安全关闭导入器"""
        if not self._closed and self.importer:
            self._closed = True
            try:
                self.importer.close()
            except:
                pass
            self.importer = None
            self._closed = False


class HealthCheckThread(QThread):
    """健康检测线程 - 检测网络和禅道连通性"""
    finished = pyqtSignal(bool, str)  # 是否健康, 错误信息

    def run(self):
        """检测网络连通性"""
        print("[HealthCheck] 开始健康检测...")
        try:
            import urllib.request
            import urllib.error

            # 检测网络连通性
            test_urls = [
                ('https://www.baidu.com', '网络'),
                ('https://zd.bicv.com', '禅道网站'),
            ]

            for url, name in test_urls:
                try:
                    req = urllib.request.Request(url, method='HEAD')
                    req.add_header('User-Agent', 'Mozilla/5.0')
                    urllib.request.urlopen(req, timeout=5)
                    print(f"[HealthCheck] {name} 可达")
                except urllib.error.URLError as e:
                    print(f"[HealthCheck] {name} 不可达: {e}")
                    self.finished.emit(False, f"{name}无法访问，请检查网络")
                    return
                except Exception as e:
                    print(f"[HealthCheck] {name} 检测异常: {e}")
                    self.finished.emit(False, f"{name}检测异常")
                    return

            self.finished.emit(True, "")
            print("[HealthCheck] 健康检测通过")

        except Exception as e:
            print(f"[HealthCheck] 健康检测异常: {e}")
            self.finished.emit(False, f"健康检测异常: {str(e)}")


class ZentaoBugTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_stats = None
        self.focus_list = []
        self.bug_details = []
        self.import_projects = load_import_projects()

        # 批量下载相关
        self.batch_thread = None
        self.batch_success_list = []
        self.batch_fail_list = []
        self.batch_download_dialog = None
        self.batch_progress_dialog = None
        self.history_manager = DownloadHistoryManager()
        self.notification_manager = SystemNotificationManager()

        # 缓存策略设置
        self.cache_strategy = 'by_days'  # by_days, by_project, by_size
        self.cache_days = 7
        self.cache_size_mb = 500
        self.load_cache_settings()

        self.init_ui()
        self.load_focus_list()
        self.check_and_prompt_batch_download()

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

        # 刷新导入项目下拉框
        self.refresh_import_combo()

    def set_mac_style(self):
        # Apple Design System 配色
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
                background-color: #0071e3;
                color: #ffffff;
                border: none;
                outline: none;
            }
            QTableWidget#dataTable::item:focus {
                border: none;
                outline: none;
            }
            QHeaderView::section {
                background-color: #fafafa;
                color: rgba(0, 0, 0, 0.48);
                padding: 10px 8px;
                border: none;
                border-bottom: 1px solid #e5e5e7;
                font-weight: 600;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: -0.224px;
            }
            QFrame#searchFrame {
                background-color: #f0f0f5;
                border-radius: 11px;
            }
            QFrame#filterFrame {
                background-color: #f0f0f5;
                border-radius: 11px;
            }
            QLineEdit#searchInput {
                background-color: transparent;
                border: none;
                padding: 8px;
                font-size: 17px;
                color: #1d1d1f;
            }
            QLineEdit#searchInput::placeholder {
                color: rgba(0, 0, 0, 0.48);
            }
            QComboBox#filterCombo {
                background-color: #fafafc;
                border: 1px solid rgba(0, 0, 0, 0.04);
                border-radius: 11px;
                padding: 0px 14px;
                font-size: 14px;
                color: rgba(0, 0, 0, 0.8);
            }
            QComboBox#filterCombo:hover {
                border-color: rgba(0, 0, 0, 0.08);
            }
            QComboBox#filterCombo::drop-down {
                border: none;
                width: 18px;
            }
            QComboBox#filterCombo::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid rgba(0, 0, 0, 0.48);
                margin-right: 4px;
            }
            QComboBox#filterCombo QAbstractItemView {
                background-color: #ffffff;
                border: 1px solid #e5e5e7;
                border-radius: 8px;
                selection-background-color: #0071e3;
                selection-color: #ffffff;
                color: #1d1d1f;
            }
            QPushButton {
                background-color: #0071e3;
                color: #ffffff;
                border: none;
                padding: 8px 15px;
                border-radius: 8px;
                font-size: 17px;
                font-weight: 400;
            }
            QPushButton:hover {
                background-color: #0077ed;
            }
            QPushButton:pressed {
                background-color: #0064d9;
            }
            QPushButton:focus {
                outline: none;
            }
            QPushButton[secondary="true"] {
                background-color: #fafafc;
                color: rgba(0, 0, 0, 0.8);
                border: 1px solid rgba(0, 0, 0, 0.04);
            }
            QPushButton[secondary="true"]:hover {
                background-color: #f0f0f5;
            }
            QPushButton[secondary="true"]:pressed {
                background-color: #ededf2;
            }
            QToolBar {
                background-color: rgba(0, 0, 0, 0.8);
                border: none;
                padding: 12px 16px;
                spacing: 12px;
            }
            QToolBar QLabel {
                color: #ffffff;
            }
            QToolBar QPushButton {
                background-color: transparent;
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.32);
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 14px;
            }
            QToolBar QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QToolBar QPushButton[secondary="true"] {
                background-color: rgba(255, 255, 255, 0.15);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.32);
            }
            QToolBar QPushButton[secondary="true"]:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QStatusBar#statusBar {
                background-color: #f5f5f7;
                color: rgba(0, 0, 0, 0.48);
                border-top: 1px solid #e5e5e7;
            }
            QScrollBar:vertical {
                background-color: transparent;
                width: 8px;
                margin: 4px 0;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(0, 0, 0, 0.22);
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(0, 0, 0, 0.32);
            }
            QScrollBar:horizontal {
                background-color: transparent;
                height: 8px;
                margin: 0 4px;
            }
            QScrollBar::handle:horizontal {
                background-color: rgba(0, 0, 0, 0.22);
                border-radius: 4px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: rgba(0, 0, 0, 0.32);
            }
            QMessageBox {
                background-color: #ffffff;
                border-radius: 12px;
            }
            QMessageBox QLabel {
                color: #1d1d1f;
                font-size: 17px;
                padding: 10px;
            }
            QMessageBox QPushButton {
                background-color: #0071e3;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 8px;
                font-size: 17px;
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

        # 标题 - Apple风格
        title = QLabel("禅道BUG分析")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: #ffffff; padding: 0 8px;")
        toolbar.addWidget(title)

        toolbar.addSeparator()

        # 按钮
        self.open_btn = QPushButton("📂 打开文件")
        self.open_btn.clicked.connect(self.open_file)
        toolbar.addWidget(self.open_btn)

        # 禅道导入下拉框 - 深色工具栏风格
        self.import_combo = QComboBox()
        self.import_combo.setObjectName("importCombo")
        self.import_combo.setMinimumWidth(150)
        self.import_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(255, 255, 255, 0.15);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.32);
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 14px;
            }
            QComboBox:hover {
                background-color: rgba(255, 255, 255, 0.25);
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid rgba(255, 255, 255, 0.7);
                margin-right: 4px;
            }
            QComboBox QAbstractItemView {
                background-color: #272729;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                selection-background-color: #0071e3;
                color: #ffffff;
            }
        """)
        self.import_combo.currentIndexChanged.connect(self.on_import_project_changed)
        toolbar.addWidget(self.import_combo)

        self.import_btn = QPushButton("⚙")
        self.import_btn.setToolTip("管理禅道导入项目")
        self.import_btn.clicked.connect(self.open_import_project_manager)
        toolbar.addWidget(self.import_btn)

        # 批量下载按钮
        self.batch_download_btn = QPushButton("⬇️ 批量下载")
        self.batch_download_btn.setToolTip("手动触发批量下载所有项目")
        self.batch_download_btn.clicked.connect(self.manual_batch_download)
        toolbar.addWidget(self.batch_download_btn)

        # 设置按钮
        self.settings_btn = QPushButton("🔧 设置")
        self.settings_btn.setToolTip("下载设置")
        self.settings_btn.clicked.connect(self.open_settings)
        toolbar.addWidget(self.settings_btn)

        # 清理缓存按钮
        self.clean_cache_btn = QPushButton("🗑️ 清理")
        self.clean_cache_btn.setToolTip("清理下载缓存")
        self.clean_cache_btn.clicked.connect(self.clean_download_cache)
        toolbar.addWidget(self.clean_cache_btn)

        # 关注人员按钮
        self.focus_btn = QPushButton("⭐ 关注人员")
        self.focus_btn.clicked.connect(self.open_focus_window)
        toolbar.addWidget(self.focus_btn)

        self.file_label = QLabel()
        self.file_label.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 12px; padding: 0 8px;")
        toolbar.addWidget(self.file_label)

        # 添加伸缩spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        # 统计
        self.stats_label = QLabel("总计: 0 BUG | 0 人")
        self.stats_label.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 12px;")
        toolbar.addWidget(self.stats_label)

        toolbar.addSeparator()

        self.export_btn = QPushButton("💾 导出")
        self.export_btn.setProperty("secondary", True)
        self.export_btn.clicked.connect(self.export_report)
        toolbar.addWidget(self.export_btn)

        return toolbar

    def open_file(self):
        log_action("打开文件", "用户点击打开文件按钮")
        path, _ = QFileDialog.getOpenFileName(
            self, "选择BUG导出文件",
            str(Path.home() / "Desktop"),
            "Excel文件 (*.xlsx);;CSV文件 (*.csv);;所有文件 (*.*)"
        )
        if path:
            log_action("选择文件", f"文件路径: {path}")
            self.analyze_file(path)

    def analyze_file(self, path):
        log_action("分析文件", f"开始分析: {path}")
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
                log_action("分析失败", "未解析到有效BUG数据")
                QMessageBox.warning(self, "警告", "未解析到有效BUG数据")
                return

            owner_stats = defaultdict(lambda: {"total": 0, "bugs": [], "severity_A": 0, "severity_B": 0, "severity_C": 0, "severity_D": 0, "active": 0, "resolved": 0, "closed": 0})
            log_action("分析成功", f"共 {len(bugs)} 个BUG, {len(owner_stats)} 人")
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

        # 按严重程度排序，S最高（数字1）在最上面
        bugs.sort(key=lambda b: b.get('severity', 3))

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

    def closeEvent(self, event):
        """关闭窗口时取消批量下载"""
        if self.batch_thread and self.batch_thread.isRunning():
            self.batch_thread.cancel()
            self.batch_thread.wait(3000)  # 等待最多3秒
        event.accept()

    def refresh_import_combo(self):
        """刷新导入下拉框的项目列表"""
        self.import_combo.blockSignals(True)
        self.import_combo.clear()
        self.import_combo.addItems(["从禅道导入...", "---"])
        for name in self.import_projects.keys():
            self.import_combo.addItem(name)
        self.import_combo.blockSignals(False)

    def on_import_project_changed(self, index):
        """下拉框选项改变时触发"""
        log_action("下拉框改变", f"索引: {index}")
        if index == 0:  # "从禅道导入..."
            return
        if index == 1:  # 分隔符
            self.import_combo.setCurrentIndex(0)
            return

        project_name = self.import_combo.currentText()
        log_action("选择项目", f"项目名: {project_name}")
        if project_name in self.import_projects:
            self.import_from_zentao(project_name)

    def import_from_zentao(self, project_name):
        """从禅道导入指定项目 - 使用QThread非阻塞"""
        url = self.import_projects[project_name].get('url')
        if not url:
            QMessageBox.warning(self, "警告", f"项目 {project_name} 未配置URL")
            return

        log_action("开始导入", f"项目: {project_name}, URL: {url}")

        # 确保下载目录存在
        download_dir = get_download_dir()
        os.makedirs(download_dir, exist_ok=True)

        # 检查今天是否已下载过该项目的文件
        today_str = datetime.now().strftime('%Y%m%d')
        today_pattern = f"{project_name}_{today_str}_"  # 文件名格式：项目名_日期_时间.xlsx
        today_files = []
        if os.path.exists(download_dir):
            for f in os.listdir(download_dir):
                if f.startswith(today_pattern) and f.endswith('.xlsx'):
                    today_files.append(f)

        if today_files:
            reply = QMessageBox.question(
                self, "今日已下载",
                f"发现今天已下载过该项目:\n{today_files[0]}\n\n确定要重新下载吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                # 使用最新的已下载文件进行分析
                latest_file = os.path.join(download_dir, today_files[0])
                print(f"[使用现有文件] {latest_file}")
                try:
                    self.analyze_file(latest_file)
                    self.status_bar.showMessage(f"已加载: {today_files[0]}")
                    log_action("加载已有文件", latest_file)
                except Exception as e:
                    print(f"[错误] 分析出错: {e}")
                self.import_combo.setCurrentIndex(0)
                return

        # 创建进度对话框（非模态，可以关闭）
        self.progress_dialog = QDialog(self)
        self.progress_dialog.setWindowTitle(f"正在导入: {project_name}")
        self.progress_dialog.setGeometry(400, 400, 450, 180)
        self.progress_dialog.setModal(False)  # 非模态，不会阻塞
        self.progress_dialog.setStyleSheet("""
            QDialog { background-color: #f5f5f7; }
            QLabel { color: #1d1d1f; background-color: transparent; }
        """)
        layout = QVBoxLayout(self.progress_dialog)

        self.progress_label = QLabel(f"正在导入: {project_name}")
        self.progress_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.progress_label)

        # 状态文本
        self.progress_status = QLabel("准备开始...")
        self.progress_status.setStyleSheet("color: #6e6e73; font-size: 12px;")
        layout.addWidget(self.progress_status)

        # 使用QProgressBar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(25)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #d2d2d7;
                border-radius: 12px;
                background-color: #e5e5ea;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #0077ed;
                border-radius: 12px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # 详细日志区域
        self.progress_log = QLabel("")
        self.progress_log.setStyleSheet("color: #86868b; font-size: 11px;")
        self.progress_log.setWordWrap(True)
        self.progress_log.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.progress_log)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f5;
                color: #1d1d1f;
                border: 1px solid rgba(0,0,0,0.04);
                padding: 8px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #e5e5ea;
            }
            QPushButton:focus {
                outline: none;
            }
        """)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

        # 显示对话框
        self.progress_dialog.show()

        # 创建导入线程
        self.import_thread = ImportThread(url)
        self.import_thread.progress.connect(self.on_import_progress)
        self.import_thread.finished.connect(lambda path: self.on_import_finished(project_name, path))
        self.import_thread.error.connect(self.on_import_error)
        self.cancel_btn.clicked.connect(self.on_import_cancelled)

        # 启动导入
        self.import_thread.start()
        log_action("导入线程已启动", f"项目: {project_name}")

    def on_import_progress(self, msg, prog):
        """导入进度更新"""
        self.progress_status.setText(msg)
        self.progress_bar.setValue(prog)
        self.progress_log.setText(msg)
        # 实时打印到控制台
        print(f"[进度 {prog}%] {msg}")

    def on_import_finished(self, project_name, path):
        """导入完成"""
        print(f"[完成] 导入完成: {path}")
        self.progress_dialog.close()

        if path and os.path.exists(path):
            # 复制到downloads目录作为备份
            date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{project_name}_{date_str}.xlsx"
            download_dir = get_download_dir()
            backup_path = os.path.join(download_dir, backup_name)
            import shutil
            shutil.copy2(path, backup_path)
            print(f"[完成] 已备份到: {backup_path}")

            # 导入后自动分析
            print(f"[完成] 开始分析文件...")
            try:
                self.analyze_file(backup_path)
                print(f"[完成] 分析完成")
            except Exception as e:
                print(f"[错误] 分析出错: {e}")
                import traceback
                traceback.print_exc()
            self.status_bar.showMessage(f"已导入: {backup_name}")
            log_action("导入成功", backup_path)
        else:
            print(f"[警告] 文件不存在: {path}")
            QMessageBox.warning(self, "导入失败", f"无法从 {project_name} 获取文件")
            log_action("导入失败", "文件不存在")

        self.import_combo.setCurrentIndex(0)

    def on_import_error(self, error_msg):
        """导入出错"""
        print(f"[错误] {error_msg}")
        self.progress_dialog.close()
        QMessageBox.critical(self, "导入失败", error_msg)
        log_action("导入出错", error_msg)
        self.import_combo.setCurrentIndex(0)

    def on_import_cancelled(self):
        """取消导入"""
        print("[取消] 用户取消导入")
        if self.import_thread and self.import_thread.isRunning():
            self.import_thread.cancel()
            self.import_thread.wait()
        self.progress_dialog.close()
        log_action("取消导入", "用户取消")
        self.import_combo.setCurrentIndex(0)

    def get_file_hash(self, filepath):
        """计算文件的MD5值"""
        import hashlib
        hash_md5 = hashlib.md5()
        try:
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except:
            return None

    def find_existing_download(self, project_name, download_dir):
        """查找该项目的现有下载文件（按时间返回最新的一个）"""
        if not os.path.exists(download_dir):
            return None
        prefix = f"{project_name}_"
        matching_files = []
        for f in os.listdir(download_dir):
            if f.startswith(prefix) and f.endswith('.xlsx'):
                path = os.path.join(download_dir, f)
                file_hash = self.get_file_hash(path)
                if file_hash:
                    matching_files.append((path, os.path.getmtime(path), file_hash))
        if matching_files:
            # 返回最新的文件（包含hash）
            matching_files.sort(key=lambda x: x[1], reverse=True)
            return matching_files[0]  # (path, mtime, hash)
        return None

    def open_import_project_manager(self):
        """打开项目管理对话框"""
        dialog = ImportProjectDialog(self, self.import_projects)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.import_projects = dialog.get_projects()
            save_import_projects(self.import_projects)
            self.refresh_import_combo()

    def open_settings(self):
        """打开设置对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("下载设置")
        dialog.setFixedSize(500, 300)
        dialog.setStyleSheet("""
            QDialog { background-color: #f5f5f7; }
            QLabel { color: #1d1d1f; background-color: transparent; }
            QLineEdit {
                border: 1px solid #d2d2d7;
                border-radius: 6px;
                padding: 8px;
                background-color: #ffffff;
                color: #1d1d1f;
            }
            QPushButton {
                background-color: #0071e3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #0077ed; }
            QPushButton[secondary="true"] {
                background-color: #f0f0f5;
                color: #1d1d1f;
            }
            QPushButton[secondary="true"]:hover { background-color: #e5e5ea; }
            QCheckBox {
                spacing: 8px;
                color: #1d1d1f;
            }
            QComboBox {
                border: 1px solid #d2d2d7;
                border-radius: 6px;
                padding: 8px;
                background-color: #ffffff;
                color: #1d1d1f;
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: #0077ed;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                border: 1px solid #d2d2d7;
                border-radius: 6px;
                color: #1d1d1f;
                selection-background-color: #0077ed;
                selection-color: #ffffff;
            }
        """)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)

        # 下载目录
        dir_layout = QHBoxLayout()
        dir_label = QLabel("下载目录:")
        dir_label.setFixedWidth(80)
        dir_layout.addWidget(dir_label)

        current_dir = get_download_dir()
        self.settings_dir_input = QLineEdit(current_dir)
        self.settings_dir_input.setReadOnly(True)
        dir_layout.addWidget(self.settings_dir_input)

        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(lambda: self.browse_download_dir(dialog))
        dir_layout.addWidget(browse_btn)
        layout.addLayout(dir_layout)

        # 当前状态
        status_label = QLabel(f"默认目录: {DEFAULT_DOWNLOAD_DIR}")
        status_label.setStyleSheet("color: #86868b; font-size: 12px;")
        layout.addWidget(status_label)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("border: none; border-top: 1px solid #e5e5e7;")
        layout.addWidget(line)

        # 缓存策略
        cache_label = QLabel("缓存清理策略:")
        cache_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(cache_label)

        cache_strategy_layout = QHBoxLayout()
        self.cache_strategy_combo = QComboBox()
        self.cache_strategy_combo.addItems(["按时间清理（保留最近N天）", "按项目清理（每个项目保留最新）", "按大小清理（超过上限时清理）"])
        self.cache_strategy_combo.setCurrentIndex(
            0 if self.cache_strategy == 'by_days' else
            1 if self.cache_strategy == 'by_project' else 2
        )
        cache_strategy_layout.addWidget(self.cache_strategy_combo)
        layout.addLayout(cache_strategy_layout)

        # 系统通知
        notify_layout = QHBoxLayout()
        self.notify_checkbox = QCheckBox("批量下载完成时发送系统通知")
        self.notify_checkbox.setChecked(self.notification_manager.enabled)
        notify_layout.addWidget(self.notify_checkbox)
        layout.addLayout(notify_layout)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        reset_btn = QPushButton("恢复默认")
        reset_btn.setProperty("secondary", True)
        reset_btn.clicked.connect(lambda: self.reset_download_dir(dialog))
        btn_layout.addWidget(reset_btn)

        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(lambda: self.save_settings_and_close(dialog))
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

        dialog.exec()

    def save_settings_and_close(self, dialog):
        """保存设置并关闭"""
        # 保存缓存策略
        idx = self.cache_strategy_combo.currentIndex()
        self.cache_strategy = 'by_days' if idx == 0 else 'by_project' if idx == 1 else 'by_size'
        self.save_cache_settings()

        # 保存通知设置
        self.notification_manager.enabled = self.notify_checkbox.isChecked()
        self.notification_manager.save_settings()

        dialog.close()

    def browse_download_dir(self, dialog):
        """浏览选择下载目录"""
        dir_path = QFileDialog.getExistingDirectory(
            dialog, "选择下载目录",
            get_download_dir()
        )
        if dir_path:
            self.settings_dir_input.setText(dir_path)
            set_download_dir(dir_path)
            self.status_bar.showMessage(f"下载目录已设置为: {dir_path}")

    def reset_download_dir(self, dialog):
        """恢复默认下载目录"""
        set_download_dir(DEFAULT_DOWNLOAD_DIR)
        self.settings_dir_input.setText(DEFAULT_DOWNLOAD_DIR)
        self.status_bar.showMessage("下载目录已恢复为默认")

    def clean_download_cache(self):
        """清理下载缓存 - 清理downloads目录中的旧文件"""
        download_dir = get_download_dir()

        if not os.path.exists(download_dir):
            QMessageBox.information(self, "清理缓存", "下载目录不存在，无需清理")
            return

        # 统计今日之前的文件
        today_str = datetime.now().strftime('%Y%m%d')
        total_size = 0
        count = 0
        files_to_clean = []

        for f in os.listdir(download_dir):
            if f.endswith('.xlsx'):
                # 检查文件名是否包含今日日期
                if today_str not in f:
                    path = os.path.join(download_dir, f)
                    try:
                        size = os.path.getsize(path)
                        total_size += size
                        count += 1
                        files_to_clean.append((f, size))
                    except:
                        pass

        if count == 0:
            QMessageBox.information(self, "清理缓存", "没有需要清理的旧文件（只有今日文件）")
            return

        size_mb = total_size / 1024 / 1024
        msg = f"发现 {count} 个旧文件，共 {size_mb:.1f} MB。\n\n确定要清理吗？"

        reply = QMessageBox.question(self, "确认清理", msg,
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            cleaned = 0
            for f, size in files_to_clean:
                path = os.path.join(download_dir, f)
                try:
                    os.remove(path)
                    cleaned += 1
                except:
                    pass
            self.status_bar.showMessage(f"已清理 {cleaned} 个旧文件")
            log_action("清理缓存", f"清理了 {cleaned} 个文件")

    # ==================== 批量下载相关方法 ====================

    def load_cache_settings(self):
        """加载缓存策略设置"""
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.cache_strategy = settings.get('cache_strategy', 'by_days')
                    self.cache_days = settings.get('cache_days', 7)
                    self.cache_size_mb = settings.get('cache_size_mb', 500)
            except:
                pass

    def save_cache_settings(self):
        """保存缓存策略设置"""
        try:
            settings = {}
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            settings['cache_strategy'] = self.cache_strategy
            settings['cache_days'] = self.cache_days
            settings['cache_size_mb'] = self.cache_size_mb
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except:
            pass

    def manual_batch_download(self):
        """手动触发批量下载"""
        if not self.import_projects:
            QMessageBox.information(self, "提示", "没有已保存的禅道项目，请先添加项目")
            return

        # 检查是否有下载线程在运行
        if self.batch_thread and self.batch_thread.isRunning():
            QMessageBox.warning(self, "提示", "批量下载进行中，请等待完成")
            return

        # 弹出批量下载对话框
        projects_list = [(name, info.get('url', '')) for name, info in self.import_projects.items()]
        self.batch_download_dialog = BatchDownloadDialog(self, projects_list, self.focus_list)

        if self.batch_download_dialog.exec() == QDialog.DialogCode.Accepted:
            selected = self.batch_download_dialog.get_selected_projects()
            if selected:
                # 开始批量下载
                self.start_batch_download(selected)

    def check_and_prompt_batch_download(self):
        """检查是否需要提示批量下载（每日首次启动）"""
        today_str = datetime.now().strftime('%Y%m%d')
        last_prompt_file = os.path.join(CONFIG_DIR, ".batch_prompt_date")

        # 检查是否今日已提示
        if os.path.exists(last_prompt_file):
            try:
                with open(last_prompt_file, 'r') as f:
                    last_date = f.read().strip()
                if last_date == today_str:
                    return  # 今日已提示，不重复提示
            except:
                pass

        # 检查是否有项目
        if not self.import_projects:
            return

        # 弹出批量下载对话框
        projects_list = [(name, info.get('url', '')) for name, info in self.import_projects.items()]
        self.batch_download_dialog = BatchDownloadDialog(self, projects_list, self.focus_list)

        if self.batch_download_dialog.exec() == QDialog.DialogCode.Accepted:
            selected = self.batch_download_dialog.get_selected_projects()
            if selected:
                # 标记今日已提示
                try:
                    with open(last_prompt_file, 'w') as f:
                        f.write(today_str)
                except:
                    pass

                # 开始批量下载
                self.start_batch_download(selected)

    def start_batch_download(self, projects):
        """开始批量下载"""
        if self.batch_thread and self.batch_thread.isRunning():
            QMessageBox.warning(self, "提示", "批量下载进行中，请等待完成")
            return

        self.batch_success_list = []
        self.batch_fail_list = []
        self.batch_projects = projects  # 保存项目列表用于进度显示

        # 先进行健康检测
        self.status_bar.showMessage("正在进行网络检测...")
        self.health_thread = HealthCheckThread()
        self.health_thread.finished.connect(lambda healthy, err: self.on_health_checked(healthy, err, projects))
        self.health_thread.start()
        log_action("批量下载开始", f"项目数: {len(projects)}")

    def on_health_checked(self, healthy, error_msg, projects):
        """健康检测完成后"""
        if not healthy:
            self.status_bar.showMessage("网络检测失败")
            QMessageBox.warning(self, "网络检测失败", error_msg)
            return

        # 健康检测通过，开始批量下载
        self.status_bar.showMessage("正在批量下载...")

        # 创建进度对话框
        self.batch_progress_dialog = BatchDownloadProgressDialog(self, len(projects))
        self.batch_progress_dialog.show()

        # 创建并启动批量下载线程
        self.batch_thread = BatchDownloadThread(projects, self.focus_list)
        self.batch_thread.progress.connect(self.on_batch_download_progress)
        self.batch_thread.project_status.connect(self.on_batch_project_status)
        self.batch_thread.finished.connect(self.on_batch_download_finished)
        self.batch_thread.error.connect(self.on_batch_download_error)
        self.batch_thread.start()

    def on_batch_download_progress(self, msg, current, total, prog):
        """批量下载进度更新"""
        # 更新状态栏
        self.status_bar.showMessage(f"{msg} [{current}/{total}]")

        # 更新进度对话框
        if hasattr(self, 'batch_progress_dialog') and self.batch_progress_dialog:
            # 从消息中提取项目名
            project_name = msg.split(": ")[-1] if ": " in msg else ""
            # 计算总体进度：(已完成项目数 * 100 + 当前项目进度) / 总项目数
            # current是从1开始的索引，所以已完成项目数是current-1
            completed_projects = current - 1
            overall_progress = (completed_projects * 100 + prog) / total
            self.batch_progress_dialog.update_progress(current, total, project_name, prog, overall_progress)

    def on_batch_project_status(self, project_name, status, message):
        """项目状态更新 - 更新批量下载对话框中的状态标记"""
        if hasattr(self, 'batch_download_dialog') and self.batch_download_dialog:
            self.batch_download_dialog.update_project_status(project_name, status, message)

    def on_batch_download_finished(self, success_list, fail_list, elapsed_time=0):
        """批量下载完成"""
        self.batch_success_list = success_list
        self.batch_fail_list = fail_list
        self.batch_elapsed_time = elapsed_time

        # 关闭进度对话框
        if hasattr(self, 'batch_progress_dialog') and self.batch_progress_dialog:
            self.batch_progress_dialog.download_finished(len(success_list), len(fail_list))

        # 更新状态栏
        self.status_bar.showMessage(f"批量下载完成: 成功 {len(success_list)} 个, 失败 {len(fail_list)} 个")

        # 记录历史
        today_str = datetime.now().strftime('%Y%m%d')
        self.history_manager.record(today_str, len(success_list), len(fail_list))

        # 发送系统通知
        if len(success_list) > 0:
            self.notification_manager.notify(
                "批量下载完成",
                f"成功 {len(success_list)} 个, 失败 {len(fail_list)} 个"
            )

        # 记录日志
        log_action("批量下载完成", f"成功: {len(success_list)}, 失败: {len(fail_list)}")

        # 刷新下拉框
        self.refresh_import_combo()

        # 数据预热：自动加载第一个成功下载的项目
        if success_list:
            first_project, first_path = success_list[0]
            try:
                self.analyze_file(first_path)
                self.status_bar.showMessage(f"已自动加载: {first_project}")
                log_action("数据预热", f"已加载: {first_project}")
            except Exception as e:
                print(f"[数据预热] 加载失败: {e}")

        # 显示结果对话框
        self.show_batch_result_dialog(success_list, fail_list, elapsed_time)

    def on_batch_download_error(self, error_msg):
        """批量下载出错"""
        # 关闭进度对话框
        if hasattr(self, 'batch_progress_dialog') and self.batch_progress_dialog:
            self.batch_progress_dialog.close()

        self.status_bar.showMessage(f"批量下载出错: {error_msg}")
        QMessageBox.critical(self, "错误", f"批量下载出错:\n{error_msg}")
        log_action("批量下载出错", error_msg)

    def show_batch_result_dialog(self, success_list, fail_list, elapsed_time=0):
        """显示批量下载结果对话框"""
        def on_retry():
            if fail_list:
                # 重试失败项目
                retry_projects = []
                for name, _ in fail_list:
                    if name in self.import_projects:
                        url = self.import_projects[name].get('url', '')
                        if url:
                            retry_projects.append((name, url))
                if retry_projects:
                    self.start_batch_download(retry_projects)

        def on_clean():
            self.clean_old_downloads_gui()

        dialog = BatchResultDialog(self, success_list, fail_list, elapsed_time=elapsed_time, on_retry=on_retry, on_clean=on_clean)
        dialog.exec()

    def retry_failed_batch_download(self):
        """重试上次失败的项目"""
        if not self.batch_fail_list:
            QMessageBox.information(self, "提示", "没有失败的项目需要重试")
            return

        retry_projects = []
        for name, _ in self.batch_fail_list:
            if name in self.import_projects:
                url = self.import_projects[name].get('url', '')
                if url:
                    retry_projects.append((name, url))

        if retry_projects:
            self.start_batch_download(retry_projects)

    def clean_old_downloads_gui(self):
        """清理旧下载文件的GUI进度显示"""
        today_str = datetime.now().strftime('%Y%m%d')
        download_dir = get_download_dir()

        if not os.path.exists(download_dir):
            return

        # 找出今日之前的xlsx文件
        files_to_clean = []
        total_size = 0
        for f in os.listdir(download_dir):
            if f.endswith('.xlsx'):
                path = os.path.join(download_dir, f)
                mtime = datetime.fromtimestamp(os.path.getmtime(path))
                file_date = mtime.strftime('%Y%m%d')
                if file_date < today_str:
                    try:
                        size = os.path.getsize(path)
                        files_to_clean.append((path, size))
                        total_size += size
                    except:
                        pass

        if not files_to_clean:
            QMessageBox.information(self, "提示", "没有需要清理的文件")
            return

        # 显示清理进度对话框
        dialog = BatchCleanProgressDialog(self, files_to_clean)
        dialog.show()

        # 在主窗口事件循环中执行清理
        def do_clean():
            cleaned_count = 0
            cleaned_size = 0
            for idx, (filepath, size) in enumerate(files_to_clean):
                if dialog.is_cancelled():
                    break

                try:
                    os.remove(filepath)
                    cleaned_count += 1
                    cleaned_size += size
                except:
                    pass

                # 更新进度
                filename = os.path.basename(filepath)
                QTimer.singleShot(0, lambda i=idx+1, fn=filename: dialog.update_progress(i, len(files_to_clean), fn))

            QTimer.singleShot(0, lambda: dialog.cleanup_finished(cleaned_size))
            log_action("清理缓存", f"清理了 {cleaned_count} 个文件，释放 {cleaned_size/1024/1024:.1f} MB")

        # 使用QTimer延后执行，避免阻塞UI
        QTimer.singleShot(100, do_clean)

    def get_old_download_files(self):
        """获取需要清理的旧文件列表"""
        today_str = datetime.now().strftime('%Y%m%d')
        download_dir = get_download_dir()
        files_to_clean = []

        if os.path.exists(download_dir):
            for f in os.listdir(download_dir):
                if f.endswith('.xlsx'):
                    path = os.path.join(download_dir, f)
                    mtime = datetime.fromtimestamp(os.path.getmtime(path))
                    file_date = mtime.strftime('%Y%m%d')
                    if file_date < today_str:
                        try:
                            size = os.path.getsize(path)
                            files_to_clean.append((path, size))
                        except:
                            pass

        return files_to_clean


class ImportProjectDialog(QDialog):
    """禅道导入项目管理对话框"""

    def __init__(self, parent, projects):
        super().__init__(parent)
        self.projects = dict(projects)
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("管理禅道导入项目")
        self.setGeometry(300, 200, 500, 400)
        self.setStyleSheet("""
            QDialog { background-color: #f5f5f7; }
            QWidget { background-color: #ffffff; color: #1d1d1f; }
            QLabel { color: #1d1d1f; background-color: transparent; }
            QPushButton {
                background-color: #0071e3;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #0077ed; }
            QLineEdit {
                border: 1px solid #d2d2d7;
                border-radius: 6px;
                padding: 6px;
                background-color: #ffffff;
                color: #1d1d1f;
            }
        """)

        layout = QVBoxLayout(self)

        # 项目列表
        self.project_list = QTableWidget()
        self.project_list.setColumnCount(3)
        self.project_list.setHorizontalHeaderLabels(["项目名", "URL", "操作"])
        self.project_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.project_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.project_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.project_list.setColumnWidth(0, 120)
        self.project_list.setColumnWidth(2, 120)
        self.project_list.verticalHeader().setVisible(False)
        self.project_list.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.project_list.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.project_list.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                color: #1d1d1f;
                border: 1px solid #d2d2d7;
                border-radius: 8px;
            }
            QTableWidget::item {
                color: #1d1d1f;
            }
            QTableWidget::item:selected {
                background-color: #0071e3;
                color: #ffffff;
            }
            QHeaderView {
                background-color: #f5f5f7;
            }
            QHeaderView::section {
                background-color: #f5f5f7;
                color: #1d1d1f;
                border: none;
                padding: 8px;
            }
        """)
        layout.addWidget(self.project_list)

        # 按钮行
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("+ 添加项目")
        add_btn.clicked.connect(self.add_project)
        btn_layout.addWidget(add_btn)

        import_btn = QPushButton("📋 剪贴板导入")
        import_btn.clicked.connect(self.import_from_clipboard)
        btn_layout.addWidget(import_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f5;
                color: #1d1d1f;
            }
            QPushButton:hover {
                background-color: #e5e5ea;
            }
        """)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        self.load_projects()

    def load_projects(self):
        self.project_list.setRowCount(0)
        for name, data in self.projects.items():
            row = self.project_list.rowCount()
            self.project_list.insertRow(row)

            name_item = QTableWidgetItem(name)
            url_item = QTableWidgetItem(data.get('url', ''))

            self.project_list.setItem(row, 0, name_item)
            self.project_list.setItem(row, 1, url_item)

            # 操作按钮
            op_widget = QWidget()
            op_layout = QHBoxLayout(op_widget)
            op_layout.setContentsMargins(4, 4, 4, 4)
            op_layout.setSpacing(8)

            edit_btn = QPushButton("编辑")
            edit_btn.setFixedWidth(50)
            edit_btn.setToolTip("修改项目名称和URL")
            edit_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0077ed;
                    color: white;
                    border: none;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #0071e3;
                }
            """)
            edit_btn.clicked.connect(lambda _, r=row: self.edit_project(r))

            delete_btn = QPushButton("删除")
            delete_btn.setFixedWidth(50)
            delete_btn.setToolTip("删除此项目")
            delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ff3b30;
                    color: white;
                    border: none;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #d63030;
                }
            """)
            delete_btn.clicked.connect(lambda _, r=row: self.delete_project(r))

            op_layout.addWidget(edit_btn)
            op_layout.addWidget(delete_btn)
            self.project_list.setCellWidget(row, 2, op_widget)

    def add_project(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("添加项目")
        dialog.setFixedSize(500, 180)
        dialog.setStyleSheet("""
            QDialog { background-color: #f5f5f7; }
            QLabel { color: #1d1d1f; background-color: transparent; }
            QLineEdit {
                border: 1px solid #d2d2d7;
                border-radius: 6px;
                padding: 8px;
                background-color: #ffffff;
                color: #1d1d1f;
            }
            QLineEdit:focus {
                border: 1px solid #0071e3;
            }
            QLineEdit::placeholder {
                color: #86868b;
            }
            QPushButton {
                background-color: #0071e3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #0071e3; }
            QPushButton[secondary=\"true\"] {
                background-color: #f0f0f5;
                color: #1d1d1f;
            }
            QPushButton[secondary=\"true\"]:hover { background-color: #e5e5ea; }
        """)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)

        # 项目名行
        name_layout = QHBoxLayout()
        name_label = QLabel("项目名:")
        name_label.setFixedWidth(60)
        name_layout.addWidget(name_label)
        name_input = QLineEdit()
        name_input.setPlaceholderText("例如: C62X-E19")
        name_layout.addWidget(name_input)
        layout.addLayout(name_layout)

        # URL行
        url_layout = QHBoxLayout()
        url_label = QLabel("URL:")
        url_label.setFixedWidth(60)
        url_layout.addWidget(url_label)
        url_input = QLineEdit()
        url_input.setPlaceholderText("例如: https://zd.bicv.com/bug-browse-304-...")
        url_layout.addWidget(url_input)
        layout.addLayout(url_layout)

        # 按钮行
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(lambda: self.save_new_project(dialog, name_input.text(), url_input.text()))
        cancel_btn = QPushButton("取消")
        cancel_btn.setProperty("secondary", True)
        cancel_btn.clicked.connect(dialog.close)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

        dialog.exec()

    def save_new_project(self, dialog, name, url):
        if not name or not url:
            QMessageBox.warning(dialog, "警告", "项目名和URL不能为空")
            return
        if name in self.projects:
            QMessageBox.warning(dialog, "警告", "项目名已存在")
            return
        self.projects[name] = {'url': url}
        self.load_projects()
        dialog.close()

    def edit_project(self, row):
        name = self.project_list.item(row, 0).text()
        url = self.project_list.item(row, 1).text()

        dialog = QDialog(self)
        dialog.setWindowTitle(f"编辑项目: {name}")
        dialog.setFixedSize(500, 180)
        dialog.setStyleSheet("""
            QDialog { background-color: #f5f5f7; }
            QLabel { color: #1d1d1f; background-color: transparent; }
            QLineEdit {
                border: 1px solid #d2d2d7;
                border-radius: 6px;
                padding: 8px;
                background-color: #ffffff;
                color: #1d1d1f;
            }
            QLineEdit:focus {
                border: 1px solid #0071e3;
            }
            QLineEdit::placeholder {
                color: #86868b;
            }
            QPushButton {
                background-color: #0071e3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #0071e3; }
            QPushButton[secondary="true"] {
                background-color: #f0f0f5;
                color: #1d1d1f;
            }
            QPushButton[secondary="true"]:hover { background-color: #e5e5ea; }
        """)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)

        # 项目名行
        name_layout = QHBoxLayout()
        name_label = QLabel("项目名:")
        name_label.setFixedWidth(60)
        name_layout.addWidget(name_label)
        name_input = QLineEdit(name)
        name_layout.addWidget(name_input)
        layout.addLayout(name_layout)

        # URL行
        url_layout = QHBoxLayout()
        url_label = QLabel("URL:")
        url_label.setFixedWidth(60)
        url_layout.addWidget(url_label)
        url_input = QLineEdit(url)
        url_layout.addWidget(url_input)
        layout.addLayout(url_layout)

        # 按钮行
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("保存")
        ok_btn.clicked.connect(lambda: self.save_edited_project(dialog, row, name_input.text(), url_input.text()))
        cancel_btn = QPushButton("取消")
        cancel_btn.setProperty("secondary", True)
        cancel_btn.clicked.connect(dialog.close)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

        dialog.exec()

    def save_edited_project(self, dialog, row, new_name, new_url):
        old_name = self.project_list.item(row, 0).text()
        if new_name != old_name and new_name in self.projects:
            QMessageBox.warning(dialog, "警告", "项目名已存在")
            return
        if new_name != old_name:
            del self.projects[old_name]
        self.projects[new_name] = {'url': new_url}
        self.load_projects()
        dialog.close()

    def delete_project(self, row):
        name = self.project_list.item(row, 0).text()
        reply = QMessageBox.question(self, "确认删除", f"确定删除项目 '{name}' 吗?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            del self.projects[name]
            self.load_projects()

    def import_from_clipboard(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()
        if not text:
            QMessageBox.information(self, "提示", "剪贴板为空")
            return

        # 尝试解析 - 支持多种格式
        lines = text.split('\n')
        added = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 格式1: 项目名,URL
            if ',' in line:
                parts = line.split(',', 1)
                name = parts[0].strip()
                url = parts[1].strip()
            # 格式2: URL (用URL作为项目名)
            elif line.startswith('http'):
                name = line.split('/')[-1][:20]  # 用URL最后一部分作为名字
                url = line
            else:
                continue

            if url.startswith('http'):
                self.projects[name] = {'url': url}
                added += 1

        if added > 0:
            self.load_projects()
            QMessageBox.information(self, "成功", f"已导入 {added} 个项目")
        else:
            QMessageBox.warning(self, "失败", "无法从剪贴板解析出有效的项目信息")

    def get_projects(self):
        """返回编辑后的项目列表"""
        return self.projects


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
                background-color: #0071e3;
                color: #ffffff;
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
                background-color: #0071e3;
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


class BatchDownloadDialog(QDialog):
    """批量下载选择对话框 - 支持分组显示和状态标记"""

    def __init__(self, parent, projects, focus_list=None):
        super().__init__(parent)
        self.projects = projects  # [(name, url), ...]
        self.focus_list = focus_list or []
        self.selected_projects = []
        self.status_labels = {}  # 存储每个项目的状态标签
        self.project_widgets = {}  # 存储每个项目的容器widget
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("批量下载")
        self.setFixedSize(650, 550)
        self.setStyleSheet("""
            QDialog { background-color: #f5f5f7; }
            QWidget { background-color: #ffffff; color: #1d1d1f; }
            QLabel { color: #1d1d1f; background-color: transparent; }
            QPushButton {
                background-color: #0071e3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #0077ed; }
            QPushButton:focus { outline: none; }
            QPushButton[secondary="true"] {
                background-color: #f0f0f5;
                color: #1d1d1f;
                border: 1px solid rgba(0,0,0,0.04);
            }
            QPushButton[secondary="true"]:hover { background-color: #e5e5ea; }
            QCheckBox {
                spacing: 10px;
                color: #1d1d1f;
                padding: 6px 8px;
                border: 1px solid #d2d2d7;
                border-radius: 6px;
                background-color: #ffffff;
            }
            QCheckBox:hover {
                background-color: #f0f0f5;
                border-color: #0077ed;
            }
            QCheckBox:checked {
                background-color: #e8f4fd;
                border-color: #0077ed;
            }
            QLabel[groupTitle="true"] {
                font-size: 12px;
                font-weight: 600;
                color: #86868b;
                padding: 8px 4px 4px 4px;
            }
            QLabel[status="waiting"] { color: #86868b; }
            QLabel[status="downloading"] { color: #0077ed; }
            QLabel[status="success"] { color: #34c759; }
            QLabel[status="failed"] { color: #ff3b30; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # 标题
        title = QLabel("批量下载 BUG 数据")
        title.setStyleSheet("font-size: 20px; font-weight: 600; color: #1d1d1f;")
        layout.addWidget(title)

        # 说明
        focus_count = len([p for p in self.projects if p[0] in self.focus_list])
        normal_count = len(self.projects) - focus_count
        desc_text = f"检测到 {len(self.projects)} 个已保存项目"
        if focus_count > 0:
            desc_text += f"（{focus_count} 个关注项目，{normal_count} 个普通项目）"
        desc = QLabel(desc_text)
        desc.setStyleSheet("color: #6e6e73; font-size: 14px;")
        layout.addWidget(desc)

        # 全选/取消全选按钮
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        select_all_btn = QPushButton("全选")
        select_all_btn.setProperty("secondary", True)
        select_all_btn.clicked.connect(self.select_all)
        btn_layout.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("取消全选")
        deselect_all_btn.setProperty("secondary", True)
        deselect_all_btn.clicked.connect(self.deselect_all)
        btn_layout.addWidget(deselect_all_btn)

        btn_layout.addStretch()

        self.count_label = QLabel(f"已选择: 0/{len(self.projects)} 个")
        self.count_label.setStyleSheet("color: #6e6e73; font-size: 13px;")
        btn_layout.addWidget(self.count_label)

        layout.addWidget(btn_row)

        # 项目列表（使用滚动区域）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #fafafa;
                border: 1px solid #e5e5e7;
                border-radius: 8px;
            }
            QScrollArea QWidget {
                background-color: #fafafa;
            }
        """)

        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(8, 8, 8, 8)
        list_layout.setSpacing(2)

        self.checkboxes = {}
        self.checkbox_by_name = {}
        self._updating = False  # 防止信号递归

        # 分组：关注项目和普通项目
        focus_projects = [(name, url) for name, url in self.projects if name in self.focus_list]
        normal_projects = [(name, url) for name, url in self.projects if name not in self.focus_list]

        # 关注项目分组
        if focus_projects:
            focus_header = QLabel(f"⭐ 关注项目 ({len(focus_projects)})")
            focus_header.setProperty("groupTitle", True)
            list_layout.addWidget(focus_header)

            for name, url in sorted(focus_projects, key=lambda x: x[0]):
                self._add_project_item(list_layout, name, url, is_focus=True)

        # 普通项目分组
        if normal_projects:
            normal_header = QLabel(f"📋 其他项目 ({len(normal_projects)})")
            normal_header.setProperty("groupTitle", True)
            list_layout.addWidget(normal_header)

            for name, url in sorted(normal_projects, key=lambda x: x[0]):
                self._add_project_item(list_layout, name, url, is_focus=False)

        # 初始化selected_projects
        self.selected_projects = [name for name, _ in self.projects]

        list_layout.addStretch()

        scroll.setWidget(list_widget)
        layout.addWidget(scroll, stretch=1)

        # 按钮行
        bottom = QWidget()
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        bottom_layout.addStretch()

        self.cancel_btn = QPushButton("稍后再说")
        self.cancel_btn.setProperty("secondary", True)
        self.cancel_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(self.cancel_btn)

        self.start_btn = QPushButton(f"开始下载 ({len(self.projects)})")
        self.start_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(self.start_btn)

        layout.addWidget(bottom)

        # 添加淡入动画
        self._setup_animation()

    def _setup_animation(self):
        """设置对话框淡入动画"""
        # 设置初始透明度为0
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)

        # 创建淡入动画
        self.fade_in_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in_animation.setDuration(300)  # 300毫秒
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        # 延迟启动动画
        QTimer.singleShot(50, self.fade_in_animation.start)

    def _add_project_item(self, layout, name, url, is_focus):
        """添加单个项目条目，包含复选框和状态标签"""
        item_widget = QWidget()
        item_layout = QHBoxLayout(item_widget)
        item_layout.setContentsMargins(4, 2, 4, 2)
        item_layout.setSpacing(8)

        cb = QCheckBox(name)
        cb.setChecked(True)
        cb.stateChanged.connect(lambda s, n=name: self.on_check_changed(n, s))
        item_layout.addWidget(cb, stretch=1)

        # 状态标签
        status_label = QLabel("⏳ 等待")
        status_label.setProperty("status", "waiting")
        status_label.setStyleSheet("font-size: 11px; padding: 2px 6px; border-radius: 4px; background-color: #f0f0f5;")
        status_label.setFixedWidth(70)
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        item_layout.addWidget(status_label)

        layout.addWidget(item_widget)

        self.checkboxes[name] = cb
        self.checkbox_by_name[name] = cb
        self.status_labels[name] = status_label
        self.project_widgets[name] = item_widget

    def update_project_status(self, name, status, message=""):
        """更新项目状态
        status: 'waiting', 'downloading', 'success', 'failed'
        """
        if name not in self.status_labels:
            return

        label = self.status_labels[name]
        widget = self.project_widgets[name]

        status_map = {
            'waiting': ('⏳ 等待', 'waiting', '#f0f0f5'),
            'downloading': ('⬇️ 下载中', 'downloading', '#e8f4fd'),
            'success': ('✅ 成功', 'success', '#e8f8e8'),
            'failed': ('❌ 失败', 'failed', '#fde8e8'),
        }

        text, status_type, bg_color = status_map.get(status, ('⏳ 等待', 'waiting', '#f0f0f5'))
        if message:
            text = message

        label.setText(text)
        label.setProperty("status", status_type)
        label.setStyleSheet(f"font-size: 11px; padding: 2px 6px; border-radius: 4px; background-color: {bg_color};")

        # 下载中时高亮显示
        if status == 'downloading':
            widget.setStyleSheet("background-color: #f0f7ff; border-radius: 4px;")
        elif status == 'success':
            widget.setStyleSheet("background-color: #f0fff0; border-radius: 4px;")
        elif status == 'failed':
            widget.setStyleSheet("background-color: #fff0f0; border-radius: 4px;")
        else:
            widget.setStyleSheet("")

    def on_check_changed(self, name, state):
        if self._updating:
            return
        if state:
            if name not in self.selected_projects:
                self.selected_projects.append(name)
        else:
            if name in self.selected_projects:
                self.selected_projects.remove(name)
        self.count_label.setText(f"已选择: {len(self.selected_projects)}/{len(self.projects)} 个")
        self.start_btn.setText(f"开始下载 ({len(self.selected_projects)})")

    def select_all(self):
        self._updating = True
        self.selected_projects = [name for name, _ in self.projects]
        for cb in self.checkboxes.values():
            cb.setChecked(True)
        self._updating = False
        self.count_label.setText(f"已选择: {len(self.selected_projects)}/{len(self.projects)} 个")
        self.start_btn.setText(f"开始下载 ({len(self.selected_projects)})")

    def deselect_all(self):
        self._updating = True
        self.selected_projects = []
        for cb in self.checkboxes.values():
            cb.setChecked(False)
        self._updating = False
        self.count_label.setText(f"已选择: 0/{len(self.projects)} 个")
        self.start_btn.setText("开始下载 (0)")

    def get_selected_projects(self):
        """返回选中的项目列表 [(name, url), ...]"""
        return [(name, url) for name, url in self.projects if name in self.selected_projects]


class BatchResultDialog(QDialog):
    """批量下载结果对话框 - 优化展示，支持点击打开目录"""

    def __init__(self, parent, success_list, fail_list, elapsed_time=0, on_retry=None, on_clean=None):
        """
        success_list: 成功列表 [(project_name, file_path), ...]
        fail_list: 失败列表 [(project_name, error_msg), ...]
        elapsed_time: 下载耗时（秒）
        """
        super().__init__(parent)
        self.success_list = success_list
        self.fail_list = fail_list
        self.elapsed_time = elapsed_time
        self.on_retry = on_retry
        self.on_clean = on_clean
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("批量下载完成")
        self.setFixedSize(550, 500)
        self.setStyleSheet("""
            QDialog { background-color: #f5f5f7; }
            QWidget { background-color: #ffffff; color: #1d1d1f; }
            QLabel { color: #1d1d1f; background-color: transparent; }
            QPushButton {
                background-color: #0071e3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #0077ed; }
            QPushButton:focus { outline: none; }
            QPushButton[secondary="true"] {
                background-color: #f0f0f5;
                color: #1d1d1f;
                border: 1px solid rgba(0,0,0,0.04);
            }
            QPushButton[secondary="true"]:hover { background-color: #e5e5ea; }
            QPushButton[warning="true"] {
                background-color: #ff9500;
                color: white;
            }
            QPushButton[warning="true"]:hover { background-color: #e68600; }
            QCheckBox {
                spacing: 8px;
                color: #1d1d1f;
            }
            QLabel[fileItem="true"] {
                padding: 4px 8px;
                border-radius: 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        # 标题
        title = QLabel("批量下载完成")
        title.setStyleSheet("font-size: 20px; font-weight: 600; color: #1d1d1f;")
        layout.addWidget(title)

        # 结果摘要
        total = len(self.success_list) + len(self.fail_list)
        summary_text = f"✅ 成功: {len(self.success_list)} 个  |  ❌ 失败: {len(self.fail_list)} 个"
        if self.elapsed_time > 0:
            summary_text += f"  |  ⏱️ 耗时: {self._format_time(self.elapsed_time)}"
        summary = QLabel(summary_text)
        summary.setStyleSheet("font-size: 14px; color: #1d1d1f;")
        layout.addWidget(summary)

        # 成功列表
        if self.success_list:
            success_label = QLabel(f"✅ 成功项目 ({len(self.success_list)})")
            success_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #34c759; padding-top: 8px;")
            layout.addWidget(success_label)

            success_scroll = QScrollArea()
            success_scroll.setWidgetResizable(True)
            success_scroll.setFixedHeight(min(120, 32 * len(self.success_list) + 16))
            success_scroll.setStyleSheet("""
                QScrollArea {
                    background-color: #f8fff8;
                    border: 1px solid #e5e5e7;
                    border-radius: 6px;
                }
            """)
            success_widget = QWidget()
            success_layout = QVBoxLayout(success_widget)
            success_layout.setContentsMargins(8, 8, 8, 8)
            success_layout.setSpacing(4)

            display_success = self.success_list[:8]
            for name, path in display_success:
                item_widget = QWidget()
                item_layout = QHBoxLayout(item_widget)
                item_layout.setContentsMargins(4, 2, 4, 2)
                item_layout.setSpacing(8)

                # 项目名
                name_label = QLabel(f"• {name}")
                name_label.setStyleSheet("font-size: 12px; color: #1d1d1f;")
                item_layout.addWidget(name_label, stretch=1)

                # 文件大小
                if path and os.path.exists(path):
                    size = os.path.getsize(path)
                    size_label = QLabel(self._format_size(size))
                    size_label.setStyleSheet("font-size: 11px; color: #86868b;")
                    item_layout.addWidget(size_label)

                # 打开目录按钮
                open_btn = QPushButton("📂")
                open_btn.setFixedSize(24, 24)
                open_btn.setStyleSheet("background-color: transparent; padding: 2px; font-size: 12px;")
                open_btn.setToolTip("打开文件所在目录")
                open_btn.clicked.connect(lambda checked, p=path: self._open_folder(p))
                item_layout.addWidget(open_btn)

                success_layout.addWidget(item_widget)

            if len(self.success_list) > 8:
                more = QLabel(f"  ... 等 {len(self.success_list) - 8} 个项目")
                more.setStyleSheet("font-size: 12px; color: #86868b;")
                success_layout.addWidget(more)

            success_scroll.setWidget(success_widget)
            layout.addWidget(success_scroll)

        # 失败列表
        if self.fail_list:
            fail_label = QLabel(f"❌ 失败项目 ({len(self.fail_list)})")
            fail_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #ff3b30; padding-top: 8px;")
            layout.addWidget(fail_label)

            fail_scroll = QScrollArea()
            fail_scroll.setWidgetResizable(True)
            fail_scroll.setFixedHeight(min(120, 32 * len(self.fail_list) + 16))
            fail_scroll.setStyleSheet("""
                QScrollArea {
                    background-color: #fff8f8;
                    border: 1px solid #e5e5e7;
                    border-radius: 6px;
                }
            """)
            fail_widget = QWidget()
            fail_layout = QVBoxLayout(fail_widget)
            fail_layout.setContentsMargins(8, 8, 8, 8)
            fail_layout.setSpacing(4)

            display_fail = self.fail_list[:8]
            for name, err in display_fail:
                item_widget = QWidget()
                item_layout = QHBoxLayout(item_widget)
                item_layout.setContentsMargins(4, 2, 4, 2)
                item_layout.setSpacing(8)

                name_label = QLabel(f"• {name}")
                name_label.setStyleSheet("font-size: 12px; color: #1d1d1f; font-weight: 500;")
                item_layout.addWidget(name_label, stretch=1)

                err_label = QLabel(err[:25] + "..." if len(err) > 25 else err)
                err_label.setStyleSheet("font-size: 11px; color: #ff3b30;")
                err_label.setToolTip(err)
                item_layout.addWidget(err_label)

                fail_layout.addWidget(item_widget)

            if len(self.fail_list) > 8:
                more = QLabel(f"  ... 等 {len(self.fail_list) - 8} 个项目")
                more.setStyleSheet("font-size: 12px; color: #86868b;")
                fail_layout.addWidget(more)

            fail_scroll.setWidget(fail_widget)
            layout.addWidget(fail_scroll)

        # 清理选项
        clean_widget = QWidget()
        clean_layout = QHBoxLayout(clean_widget)
        clean_layout.setContentsMargins(0, 0, 0, 0)

        self.clean_checkbox = QCheckBox("清除今日之前的已下载缓存（节省磁盘空间）")
        clean_layout.addWidget(self.clean_checkbox)
        clean_layout.addStretch()
        layout.addWidget(clean_widget)

        layout.addStretch()

        # 按钮行
        bottom = QWidget()
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        if self.fail_list:
            retry_btn = QPushButton("🔄 重试失败")
            retry_btn.setProperty("warning", True)
            retry_btn.clicked.connect(self.on_retry_click)
            bottom_layout.addWidget(retry_btn)

        bottom_layout.addStretch()

        self.cancel_btn = QPushButton("确定")
        self.cancel_btn.setProperty("secondary", True)
        self.cancel_btn.clicked.connect(self.on_confirm)
        bottom_layout.addWidget(self.cancel_btn)

        layout.addWidget(bottom)

        # 添加淡入动画
        self._setup_animation()

    def _setup_animation(self):
        """设置对话框淡入动画"""
        # 设置初始透明度为0
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)

        # 创建淡入动画
        self.fade_in_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in_animation.setDuration(300)  # 300毫秒
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        # 延迟启动动画
        QTimer.singleShot(50, self.fade_in_animation.start)

    def _format_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.1f}KB"
        else:
            return f"{size_bytes/1024/1024:.1f}MB"

    def _format_time(self, seconds):
        """格式化时间"""
        if seconds < 60:
            return f"{seconds:.0f}秒"
        elif seconds < 3600:
            return f"{seconds/60:.1f}分钟"
        else:
            return f"{seconds/3600:.1f}小时"

    def _open_folder(self, file_path):
        """打开文件所在目录"""
        import subprocess
        folder = os.path.dirname(file_path)
        if os.path.exists(folder):
            subprocess.Popen(f'explorer "{folder}"')

    def on_retry_click(self):
        if self.on_retry:
            self.on_retry()
        self.accept()

    def on_confirm(self):
        if self.clean_checkbox.isChecked() and self.on_clean:
            self.on_clean()
        self.accept()

    def get_fail_list(self):
        return self.fail_list


class BatchDownloadProgressDialog(QDialog):
    """批量下载进度对话框 - 双进度条，详细信息显示"""

    def __init__(self, parent, total_projects):
        super().__init__(parent)
        self.total_projects = total_projects
        self.current_project = 0
        self.start_time = time.time()
        self._cancelled = False
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("批量下载中")
        self.setFixedSize(500, 220)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog { background-color: #f5f5f7; }
            QWidget { background-color: #ffffff; color: #1d1d1f; }
            QLabel { color: #1d1d1f; background-color: transparent; }
            QPushButton {
                background-color: #f0f0f5;
                color: #1d1d1f;
                border: 1px solid rgba(0,0,0,0.04);
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #e5e5ea; }
            QPushButton:focus { outline: none; }
            QProgressBar {
                border: 1px solid #d2d2d7;
                border-radius: 12px;
                background-color: #e5e5ea;
                text-align: center;
                max-height: 16px;
            }
            QProgressBar::chunk {
                background-color: #0077ed;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # 标题
        self.title_label = QLabel("正在批量下载...")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #1d1d1f;")
        layout.addWidget(self.title_label)

        # 总体进度
        overall_layout = QHBoxLayout()
        overall_label = QLabel("总体进度:")
        overall_label.setStyleSheet("font-size: 12px; color: #6e6e73;")
        overall_layout.addWidget(overall_label)

        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, self.total_projects)
        self.overall_progress.setValue(0)
        self.overall_progress.setTextVisible(True)
        overall_layout.addWidget(self.overall_progress, stretch=1)
        layout.addLayout(overall_layout)

        # 当前项目进度
        current_layout = QHBoxLayout()
        current_label = QLabel("当前项目:")
        current_label.setStyleSheet("font-size: 12px; color: #6e6e73;")
        current_layout.addWidget(current_label)

        self.current_progress = QProgressBar()
        self.current_progress.setRange(0, 100)
        self.current_progress.setValue(0)
        self.current_progress.setTextVisible(True)
        current_layout.addWidget(self.current_progress, stretch=1)
        layout.addLayout(current_layout)

        # 状态信息
        self.status_label = QLabel("准备开始...")
        self.status_label.setStyleSheet("color: #6e6e73; font-size: 13px;")
        layout.addWidget(self.status_label)

        # 详细信息行
        info_layout = QHBoxLayout()

        self.project_label = QLabel("")
        self.project_label.setStyleSheet("color: #1d1d1f; font-size: 12px; font-weight: 500;")
        info_layout.addWidget(self.project_label, stretch=1)

        self.time_label = QLabel("")
        self.time_label.setStyleSheet("color: #86868b; font-size: 11px;")
        info_layout.addWidget(self.time_label)

        layout.addLayout(info_layout)

        # 取消按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.on_cancel)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

        # 更新时间显示的定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time_display)
        self.timer.start(1000)

        # 添加淡入动画
        self._setup_animation()

    def _setup_animation(self):
        """设置对话框淡入动画"""
        # 设置初始透明度为0
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)

        # 创建淡入动画
        self.fade_in_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in_animation.setDuration(200)  # 200毫秒
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        # 延迟启动动画
        QTimer.singleShot(50, self.fade_in_animation.start)

    def update_progress(self, current, total, project_name, project_progress=0, overall_progress=None):
        """更新进度"""
        self.current_project = current
        # 使用计算好的总体进度，如果没有则使用当前项目索引
        if overall_progress is not None:
            self.overall_progress.setValue(int(overall_progress))
        else:
            self.overall_progress.setValue(current)
        self.current_progress.setValue(project_progress)
        self.project_label.setText(f"📁 {project_name}")
        self.status_label.setText(f"正在下载 {current}/{total}: {project_name}")

    def update_time_display(self):
        """更新时间显示"""
        elapsed = time.time() - self.start_time
        if elapsed < 60:
            time_str = f"{elapsed:.0f}秒"
        elif elapsed < 3600:
            time_str = f"{elapsed/60:.1f}分钟"
        else:
            time_str = f"{elapsed/3600:.1f}小时"

        # 预估剩余时间
        if self.current_project > 0:
            avg_time = elapsed / self.current_project
            remaining = avg_time * (self.total_projects - self.current_project)
            if remaining < 60:
                remain_str = f"{remaining:.0f}秒"
            elif remaining < 3600:
                remain_str = f"{remaining/60:.1f}分钟"
            else:
                remain_str = f"{remaining/3600:.1f}小时"
            self.time_label.setText(f"⏱️ 已用 {time_str} | 预计剩余 {remain_str}")
        else:
            self.time_label.setText(f"⏱️ 已用 {time_str}")

    def download_finished(self, success_count, fail_count):
        """下载完成"""
        self.timer.stop()
        elapsed = time.time() - self.start_time
        self.title_label.setText("批量下载完成")
        self.status_label.setText(f"✅ 成功: {success_count} 个  |  ❌ 失败: {fail_count} 个  |  ⏱️ 耗时: {self._format_time(elapsed)}")
        self.project_label.setText("")
        self.time_label.setText("")
        self.cancel_btn.setText("关闭")
        self.cancel_btn.clicked.disconnect()
        self.cancel_btn.clicked.connect(self.accept)

    def _format_time(self, seconds):
        """格式化时间"""
        if seconds < 60:
            return f"{seconds:.0f}秒"
        elif seconds < 3600:
            return f"{seconds/60:.1f}分钟"
        else:
            return f"{seconds/3600:.1f}小时"

    def on_cancel(self):
        self._cancelled = True
        self.timer.stop()
        self.reject()

    def is_cancelled(self):
        return self._cancelled


class BatchCleanProgressDialog(QDialog):
    """清理进度对话框"""

    def __init__(self, parent, files_to_clean):
        super().__init__(parent)
        self.files_to_clean = files_to_clean  # [(filepath, size), ...]
        self._cancelled = False
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("清理缓存")
        self.setFixedSize(450, 180)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog { background-color: #f5f5f7; }
            QWidget { background-color: #ffffff; color: #1d1d1f; }
            QLabel { color: #1d1d1f; background-color: transparent; }
            QPushButton {
                background-color: #f0f0f5;
                color: #1d1d1f;
                border: 1px solid rgba(0,0,0,0.04);
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #e5e5ea; }
            QPushButton:focus { outline: none; }
            QProgressBar {
                border: 1px solid #d2d2d7;
                border-radius: 12px;
                background-color: #e5e5ea;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #0077ed;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 标题
        title = QLabel("正在清理缓存...")
        title.setStyleSheet("font-size: 16px; font-weight: 600; color: #1d1d1f;")
        layout.addWidget(title)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, len(self.files_to_clean))
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        # 状态
        self.status_label = QLabel("准备清理...")
        self.status_label.setStyleSheet("color: #6e6e73; font-size: 13px;")
        layout.addWidget(self.status_label)

        # 文件名
        self.file_label = QLabel("")
        self.file_label.setStyleSheet("color: #86868b; font-size: 11px;")
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)

        # 取消按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.on_cancel)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def update_progress(self, current, total, filename):
        self.progress_bar.setValue(current)
        self.status_label.setText(f"正在清理: {current}/{total}")
        self.file_label.setText(filename)

    def cleanup_finished(self, total_size):
        total_mb = total_size / 1024 / 1024
        self.status_label.setText(f"清理完成！已清理 {len(self.files_to_clean)} 个文件，释放 {total_mb:.1f} MB")
        self.file_label.setText("")
        self.cancel_btn.setText("关闭")
        self.cancel_btn.clicked.disconnect()
        self.cancel_btn.clicked.connect(self.accept)

    def on_cancel(self):
        self._cancelled = True
        self.reject()

    def is_cancelled(self):
        return self._cancelled


class DownloadHistoryManager:
    """下载历史统计管理器"""

    def __init__(self):
        self.history_file = os.path.join(CONFIG_DIR, "download_history.json")
        self.history = self._load()

    def _load(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except:
            pass

    def record(self, date, success_count, fail_count):
        """记录每日下载结果"""
        if date not in self.history:
            self.history[date] = {'success': 0, 'fail': 0, 'total': 0}

        self.history[date]['success'] += success_count
        self.history[date]['fail'] += fail_count
        self.history[date]['total'] += success_count + fail_count
        self._save()

    def get_stats(self, days=7):
        """获取最近N天的统计"""
        stats = []
        today = datetime.now()
        for i in range(days):
            d = (today - timedelta(days=i)).strftime('%Y%m%d')
            if d in self.history:
                stats.append({
                    'date': d,
                    'success': self.history[d].get('success', 0),
                    'fail': self.history[d].get('fail', 0),
                })
        return stats

    def get_fail_rate(self):
        """计算总体失败率"""
        total_success = sum(v['success'] for v in self.history.values())
        total_fail = sum(v['fail'] for v in self.history.values())
        total = total_success + total_fail
        if total == 0:
            return 0.0
        return (total_fail / total) * 100

    def get_always_fail_projects(self):
        """获取经常失败的项目"""
        project_fails = defaultdict(int)
        for entry in self.history.values():
            if 'fail_projects' in entry:
                for p in entry['fail_projects']:
                    project_fails[p] += 1
        return sorted(project_fails.items(), key=lambda x: x[1], reverse=True)


class SystemNotificationManager:
    """系统通知管理器（用于批量下载完成通知）"""

    def __init__(self):
        self.enabled = True
        self.load_settings()

    def load_settings(self):
        """从设置文件加载通知开关状态"""
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.enabled = settings.get('system_notification', True)
            except:
                pass

    def save_settings(self):
        """保存通知开关状态"""
        try:
            settings = {}
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            settings['system_notification'] = self.enabled
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except:
            pass

    def notify(self, title, message):
        """发送系统通知"""
        if not self.enabled:
            return

        try:
            from plyer import notification
            notification.notify(
                title=title,
                message=message,
                app_name="禅道BUG分析",
                timeout=10
            )
        except ImportError:
            print("[通知] plyer未安装，无法发送系统通知")
        except Exception as e:
            print(f"[通知] 发送通知失败: {e}")


class BrowserInstallThread(QThread):
    """后台线程安装浏览器驱动"""
    finished = pyqtSignal(bool, str)  # success, message
    progress = pyqtSignal(str, int)   # message, percent

    def run(self):
        import subprocess
        import shutil
        python_path = shutil.which('python')
        if not python_path:
            python_path = shutil.which('python3')
        if not python_path:
            self.finished.emit(False, "未找到Python，请安装Python后重试")
            return

        self.progress.emit("正在下载浏览器驱动（约150MB）...", 10)
        try:
            # 同样设置浏览器路径环境变量，确保安装到正确位置
            install_env = os.environ.copy()
            browsers_path = os.path.expanduser('~/AppData/Local/ms-playwright')
            if os.path.exists(browsers_path):
                install_env['PLAYWRIGHT_BROWSERS_PATH'] = browsers_path
            process = subprocess.Popen(
                [python_path, '-m', 'playwright', 'install', 'chromium'],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                env=install_env
            )
            # 读取输出并发送进度
            for line in iter(process.stdout.readline, ''):
                if line:
                    if 'downloading' in line.lower():
                        self.progress.emit("正在下载浏览器驱动...", 40)
                    elif 'installing' in line.lower():
                        self.progress.emit("正在安装浏览器驱动...", 80)
            process.wait()
            if process.returncode == 0:
                self.progress.emit("验证浏览器驱动...", 95)
                # 验证
                from playwright.sync_api import sync_playwright
                pw = sync_playwright().start()
                try:
                    browser = pw.chromium.launch(headless=True, timeout=15000,
                                                 args=['--no-sandbox', '--disable-gpu'])
                    browser.close()
                    pw.stop()
                    self.finished.emit(True, "浏览器驱动安装成功")
                except Exception as e:
                    pw.stop()
                    self.finished.emit(False, f"浏览器驱动验证失败: {e}")
            else:
                self.finished.emit(False, "浏览器驱动安装失败")
        except Exception as e:
            self.finished.emit(False, f"安装出错: {e}")


def _get_playwright_browsers_path():
    """获取系统 playwright 浏览器安装路径（PyInstaller打包后需要显式指定）"""
    # Windows 默认安装路径
    default_path = os.path.expanduser('~/AppData/Local/ms-playwright')
    if os.path.exists(default_path):
        return default_path
    env_path = os.environ.get('PLAYWRIGHT_BROWSERS_PATH')
    if env_path and os.path.exists(env_path):
        return env_path
    return None

def main():
    import sys
    import shutil

    # 设置 Playwright 浏览器路径（PyInstaller 打包后无法自动检测）
    browsers_path = _get_playwright_browsers_path()
    if browsers_path:
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = browsers_path
        print(f"[启动] 设置浏览器路径: {browsers_path}")

    # 先创建QApplication用于UI
    app = QApplication(sys.argv)
    app.setApplicationName("禅道BUG分析")

    browser_ok = False

    # 检查浏览器驱动
    try:
        from playwright.sync_api import sync_playwright
        print("[启动] 检查浏览器驱动...")
        pw = sync_playwright().start()
        try:
            browser = pw.chromium.launch(headless=True, timeout=15000,
                                         args=['--no-sandbox', '--disable-gpu'])
            browser.close()
            pw.stop()
            print("[启动] 浏览器驱动正常")
            browser_ok = True
        except Exception:
            pw.stop()
            print("[启动] 浏览器驱动缺失，显示安装对话框...")

            # 存储安装结果
            install_success = [False]  # 用列表以便在闭包中修改

            # 创建进度对话框
            progress_dialog = QProgressDialog(
                "正在安装浏览器驱动（约150MB）...",
                None,  # 无取消按钮
                0, 100
            )
            progress_dialog.setWindowTitle("首次启动设置")
            progress_dialog.setWindowFlags(
                progress_dialog.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint
            )
            progress_dialog.setMinimumDuration(0)
            progress_dialog.setValue(0)
            progress_dialog.setModal(True)

            install_thread = BrowserInstallThread()

            def on_progress(msg, val):
                progress_dialog.setLabelText(msg)
                progress_dialog.setValue(val)

            def on_finished(success, message):
                install_success[0] = success
                progress_dialog.close()
                if not success:
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.critical(None, "安装失败", message)
                    sys.exit(1)

            install_thread.progress.connect(on_progress)
            install_thread.finished.connect(on_finished)
            install_thread.start()

            # 显示进度对话框（模态）
            progress_dialog.exec()

            # 对话框关闭后，等待线程结束
            if install_thread.isRunning():
                install_thread.wait(600000)  # 最多等10分钟

            if install_success[0]:
                browser_ok = True

    except Exception as e:
        print(f"[启动] 浏览器检查失败: {e}")
        QMessageBox.critical(None, "启动失败", f"浏览器驱动检查失败：{e}\n\n请确保已安装Python和Playwright。")

    if not browser_ok:
        print("[启动] 浏览器驱动未就绪，无法启动程序")
        sys.exit(1)

    window = ZentaoBugTool()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
