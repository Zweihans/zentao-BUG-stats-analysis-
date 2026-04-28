#!/usr/bin/env python3
"""
禅道BUG分析工具 - 现代化扁平设计
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import os
import re
import json
from datetime import datetime
from collections import defaultdict
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET


class FocusPersonWindow:
    """关注人员选择窗口"""
    def __init__(self, parent, owner_stats, focus_list, on_confirm):
        self.window = tk.Toplevel(parent.root)
        self.window.title("关注人员选择")
        self.window.geometry("1100x650")
        self.window.resizable(True, True)  # 允许调整大小但有下限
        self.window.transient(parent.root)
        self.window.grab_set()

        # 窗口尺寸限制
        self.window.update_idletasks()
        self._min_width = 280  # 左侧面板最小宽度
        self._min_height = 400

        self.parent = parent
        self.owner_stats = owner_stats
        self.focus_list = set(focus_list)
        self.on_confirm = on_confirm
        self.selected_owner = None

        self.c = parent.c
        self.load_focus_list()
        self.setup_ui()

    def setup_ui(self):
        c = self.c
        self.window.configure(bg=c['bg'])

        # 顶部工具栏（紧凑布局）
        toolbar = tk.Frame(self.window, bg=c['card'], padx=10, pady=5)
        toolbar.pack(fill="x")

        # 左侧：搜索框
        tk.Label(toolbar, text="🔍", font=("Microsoft YaHei", 10), fg=c['text_sec'], bg=c['card']).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *_: self.update_person_list())
        tk.Entry(toolbar, textvariable=self.search_var, font=("Microsoft YaHei", 9),
            bg=c['bg'], fg=c['text'], insertbackground=c['text'], relief="flat", bd=0, width=15).pack(side="left", padx=(5, 15))

        # 中间：全选/取消按钮
        tk.Button(toolbar, text="全选", font=("Microsoft YaHei", 9), bg=c['card'], fg=c['text'],
            relief="flat", padx=8, cursor="hand2", command=self.select_all).pack(side="left", padx=2)
        tk.Button(toolbar, text="取消", font=("Microsoft YaHei", 9), bg=c['card'], fg=c['text'],
            relief="flat", padx=8, cursor="hand2", command=self.deselect_all).pack(side="left", padx=2)

        # 右侧：保存/加载按钮
        tk.Button(toolbar, text="💾 保存", font=("Microsoft YaHei", 9), bg=c['card'], fg=c['text'],
            relief="flat", padx=8, cursor="hand2", command=self.save_focus_list).pack(side="right", padx=2)
        tk.Button(toolbar, text="📂 加载", font=("Microsoft YaHei", 9), bg=c['card'], fg=c['text'],
            relief="flat", padx=8, cursor="hand2", command=self.load_focus_list_dialog).pack(side="right", padx=2)

        # 主内容区 - 左右布局
        content = tk.Frame(self.window, bg=c['bg'])
        content.pack(fill="both", expand=True, padx=10, pady=(5, 5))

        # 左侧人员列表（固定宽度260）
        left_card = tk.Frame(content, bg=c['card'], width=260)
        left_card.pack(side="left", fill="y")
        left_card.pack_propagate(False)

        tk.Label(left_card, text="人员列表", font=("Microsoft YaHei", 9, "bold"),
            fg=c['text'], bg=c['card']).pack(anchor="w", padx=8, pady=(5, 2))

        # 人员列表容器
        list_frame = tk.Frame(left_card, bg=c['bg'])
        list_frame.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        # Canvas + Scrollbar 滚动实现
        self.person_canvas = tk.Canvas(list_frame, bg=c['card'], highlightthickness=0)
        self.person_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.person_canvas.yview)
        self.person_canvas.configure(yscrollcommand=self.person_scrollbar.set)
        self.person_canvas.pack(side="left", fill="both", expand=True)
        self.person_scrollbar.pack(side="right", fill="y")

        self.person_container = tk.Frame(self.person_canvas, bg=c['card'])
        self.person_canvas_window = self.person_canvas.create_window((0, 0), window=self.person_container, anchor="nw", width=240)

        def update_scrollregion(e):
            self.person_canvas.configure(scrollregion=(0, 0, 240, self.person_container.winfo_reqheight()))
        self.person_container.bind("<Configure>", update_scrollregion)

        def on_mousewheel(e):
            self.person_canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        self.person_canvas.bind("<MouseWheel>", on_mousewheel)
        self.person_container.bind("<MouseWheel>", on_mousewheel)

        self.person_vars = {}

        # 右侧BUG详情（自适应填充剩余空间）
        right_card = tk.Frame(content, bg=c['card'])
        right_card.pack(side="left", fill="both", expand=True, padx=(8, 0))

        header_frame = tk.Frame(right_card, bg=c['card'])
        header_frame.pack(fill="x", padx=8, pady=(5, 0))
        tk.Label(header_frame, text="BUG详情", font=("Microsoft YaHei", 9, "bold"),
            fg=c['text'], bg=c['card']).pack(side="left")
        self.detail_title = tk.Label(header_frame, text="(点击左侧人员查看)",
            font=("Microsoft YaHei", 8), fg=c['text_sec'], bg=c['card'])
        self.detail_title.pack(side="left", padx=5)

        detail_frame = tk.Frame(right_card, bg=c['card'], padx=5, pady=5)
        detail_frame.pack(fill="both", expand=True)

        sy2 = ttk.Scrollbar(detail_frame, orient="vertical")
        sy2.pack(side="right", fill="y")
        sx2 = ttk.Scrollbar(detail_frame, orient="horizontal")
        sx2.pack(side="bottom", fill="x")

        self.detail_tree = ttk.Treeview(detail_frame, columns=("id", "severity", "status", "title"),
            show="headings", yscrollcommand=sy2.set, xscrollcommand=sx2.set)
        self.detail_tree.pack(side="left", fill="both", expand=True)
        sy2.config(command=self.detail_tree.yview)
        sx2.config(command=self.detail_tree.xview)

        self.detail_sort_col = None
        self.detail_sort_reverse = False
        self.current_bugs = []

        # 列宽设置：最小宽度限制
        self.detail_tree.column("id", width=70, minwidth=70, anchor="center")
        self.detail_tree.column("severity", width=50, minwidth=50, anchor="center")
        self.detail_tree.column("status", width=70, minwidth=70, anchor="center")
        self.detail_tree.column("title", width=300, minwidth=150, anchor="w")

        # 列标题中文名称映射
        self.col_names = {"id": "Bug ID", "severity": "严重", "status": "状态", "title": "标题"}

        self.detail_tree.heading("id", text="Bug ID", command=lambda: self.sort_detail("id"))
        self.detail_tree.heading("severity", text="严重", command=lambda: self.sort_detail("severity"))
        self.detail_tree.heading("status", text="状态", command=lambda: self.sort_detail("status"))
        self.detail_tree.heading("title", text="标题", command=lambda: self.sort_detail("title"))

        self.detail_tree.tag_configure("severe", foreground=c['danger'], font=("Microsoft YaHei", 9, "bold"))
        self.detail_tree.tag_configure("warning", foreground=c['warning'])
        self.detail_tree.tag_configure("normal", foreground=c['text'])

        # 列宽限制：防止列被挤压过窄或过宽
        def enforce_column_widths(event):
            min_widths = {"id": 70, "severity": 50, "status": 70, "title": 150}
            max_widths = {"id": 100, "severity": 70, "status": 120, "title": 500}
            for col in ("id", "severity", "status", "title"):
                col_width = self.detail_tree.column(col, width=None)
                if col_width < min_widths[col]:
                    self.detail_tree.column(col, width=min_widths[col])
                elif col_width > max_widths[col]:
                    self.detail_tree.column(col, width=max_widths[col])
        self.detail_tree.bind("<ButtonRelease-1>", enforce_column_widths, add=True)

        # 底部按钮
        bottom = tk.Frame(self.window, bg=c['card'], pady=5)
        bottom.pack(fill="x")

        self.focus_count_label = tk.Label(bottom, text="已关注: 0人",
            font=("Microsoft YaHei", 9), fg=c['primary'], bg=c['card'])
        self.focus_count_label.pack(side="left", padx=10)

        tk.Button(bottom, text="关闭", font=("Microsoft YaHei", 9), bg=c['card'], fg=c['text'],
            relief="flat", padx=15, cursor="hand2", command=self.window.destroy).pack(side="right", padx=3)
        tk.Button(bottom, text="确定", font=("Microsoft YaHei", 9, "bold"), bg=c['primary'], fg="white",
            relief="flat", padx=15, cursor="hand2", command=self.confirm).pack(side="right", padx=3)

        self.update_person_list()
        # 强制更新窗口布局
        self.window.update_idletasks()
        self.window.geometry()  # 触发窗口尺寸计算

    def update_person_list(self):
        # 清空
        for widget in self.person_container.winfo_children():
            widget.destroy()
        self.person_vars.clear()

        search = self.search_var.get().lower()
        sorted_owners = sorted(self.owner_stats.items(),
            key=lambda x: x[1]['total'], reverse=True)

        for owner_key, data in sorted_owners:
            dn = owner_key.split('(')[0].strip() if '(' in owner_key else owner_key
            if search and search not in dn.lower():
                continue

            row = tk.Frame(self.person_container, bg=self.c['card'], height=30)
            row.pack(fill="x", pady=0)
            row.pack_propagate(False)

            var = tk.BooleanVar(value=(owner_key in self.focus_list))

            def make_cb(opt, v):
                return lambda: self.on_checkbox_changed(opt, v)

            cb = tk.Checkbutton(row, variable=var, font=("Microsoft YaHei", 10),
                bg=self.c['card'], fg=self.c['text'], selectcolor=self.c['selected'],
                command=make_cb(owner_key, var))
            cb.pack(side="left", padx=(8, 0))

            # 点击姓名选中并显示详情
            name_label = tk.Label(row, text=dn, font=("Microsoft YaHei", 10),
                fg=self.c['text'], bg=self.c['card'], cursor="hand2")
            name_label.pack(side="left", fill="x", expand=True, padx=5)

            def make_click(opt):
                return lambda e: self.on_person_clicked(opt)

            name_label.bind("<Button-1>", make_click(owner_key))

            count_label = tk.Label(row, text=f"{data['total']}BUG", font=("Microsoft YaHei", 9),
                fg=self.c['text_sec'], bg=self.c['card'], width=6)
            count_label.pack(side="right", padx=8)

            self.person_vars[owner_key] = var

        # 强制更新scrollregion
        self.person_container.update_idletasks()
        self.person_canvas.update_idletasks()
        bbox = self.person_canvas.bbox("all")
        if bbox:
            self.person_canvas.configure(scrollregion=bbox)
        self.update_focus_count()

    def on_checkbox_changed(self, owner_key, var):
        if var.get():
            self.focus_list.add(owner_key)
            # 勾选时显示该人员的BUG详情
            self.selected_owner = owner_key
            bugs = self.owner_stats.get(owner_key, {}).get('bugs', [])
            self.detail_title.config(text=f"({owner_key}，共{len(bugs)}条BUG)")
            self.update_detail_tree(bugs)
        else:
            self.focus_list.discard(owner_key)
            # 取消勾选时，显示下一个已勾选人员的BUG，如果没有则清空
            if self.focus_list:
                next_owner = next(iter(self.focus_list))
                self.selected_owner = next_owner
                bugs = self.owner_stats.get(next_owner, {}).get('bugs', [])
                self.detail_title.config(text=f"({next_owner}，共{len(bugs)}条BUG)")
                self.update_detail_tree(bugs)
            else:
                self.selected_owner = None
                self.detail_title.config(text="(无选中人员)")
                self.update_detail_tree([])
        self.update_focus_count()

    def on_person_clicked(self, owner_key):
        self.selected_owner = owner_key
        bugs = self.owner_stats.get(owner_key, {}).get('bugs', [])
        self.detail_title.config(text=f"({owner_key}，共{len(bugs)}条BUG)")
        self.update_detail_tree(bugs)

    def update_detail_tree(self, bugs):
        self.current_bugs = bugs
        self._render_detail_tree()

    def _render_detail_tree(self):
        for item in self.detail_tree.get_children():
            self.detail_tree.delete(item)

        bugs = self.current_bugs

        # 排序
        if self.detail_sort_col:
            if self.detail_sort_col == "severity":
                bugs = sorted(bugs, key=lambda x: x.get('severity', 3), reverse=self.detail_sort_reverse)
            elif self.detail_sort_col == "id":
                bugs = sorted(bugs, key=lambda x: x.get('id', ''), reverse=self.detail_sort_reverse)
            elif self.detail_sort_col == "status":
                bugs = sorted(bugs, key=lambda x: x.get('status', '').lower(), reverse=self.detail_sort_reverse)
            elif self.detail_sort_col == "title":
                bugs = sorted(bugs, key=lambda x: x.get('title', '').lower(), reverse=self.detail_sort_reverse)
        else:
            bugs = sorted(bugs, key=lambda x: x.get('severity', 3))

        for b in bugs:
            s = b.get('severity', 3)
            sl = 'A' if s == 1 else 'B' if s == 2 else 'C' if s == 3 else 'D'
            st = b.get('status', '')
            tag = "severe" if sl == 'A' else "warning" if sl == 'B' else "normal"
            self.detail_tree.insert("", "end", values=(b['id'], sl, st, b.get('title', '')[:50]), tags=(tag,))

    def sort_detail(self, col):
        if self.detail_sort_col == col:
            self.detail_sort_reverse = not self.detail_sort_reverse
        else:
            self.detail_sort_col = col
            self.detail_sort_reverse = False
        # 更新列头显示（使用中文列名）
        for c in ["id", "severity", "status", "title"]:
            arrow = " ▲" if self.detail_sort_col == c and not self.detail_sort_reverse else " ▼" if self.detail_sort_col == c else ""
            self.detail_tree.heading(c, text=f"{self.col_names[c]}{arrow}")
        self._render_detail_tree()

    def update_focus_count(self):
        self.focus_count_label.config(text=f"已关注: {len(self.focus_list)}人")

    def select_all(self):
        self.focus_list = set(self.owner_stats.keys())
        self.update_person_list()

    def deselect_all(self):
        self.focus_list.clear()
        self.update_person_list()

    def save_focus_list(self):
        path = filedialog.asksaveasfilename(title="保存关注名单",
            defaultextension=".json",
            filetypes=[("JSON文件", "*.json")])
        if path:
            try:
                names = list(self.focus_list)
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(names, f, ensure_ascii=False, indent=2)
                messagebox.showinfo("成功", f"已保存 {len(names)} 人到:\n{path}")
            except Exception as e:
                messagebox.showerror("失败", str(e))

    def load_focus_list_dialog(self):
        path = filedialog.askopenfilename(title="加载关注名单",
            filetypes=[("JSON文件", "*.json")])
        if path:
            self.load_focus_list(path)

    def load_focus_list(self, path=None):
        default_path = Path(__file__).parent / "focus_list.json"
        if path is None:
            path = default_path
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    names = json.load(f)
                self.focus_list = set()
                for n in names:
                    for o in self.owner_stats:
                        dn = o.split('(')[0].strip() if '(' in o else o
                        if dn == n:
                            self.focus_list.add(o)
                            break
                self.update_person_list()
            except:
                pass

    def confirm(self):
        self.on_confirm(list(self.focus_list))
        self.window.destroy()


class ZentaoBugTool:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("禅道BUG分析")
        self.root.geometry("1200x700")
        self.root.minsize(900, 550)

        self.style = ttk.Style()
        self.style.theme_use('clam')

        self.c = {
            'bg': '#F5F7FA',
            'card': '#FFFFFF',
            'primary': '#4A90D9',
            'primary_dark': '#3A7BC8',
            'success': '#52C41A',
            'warning': '#FAAD14',
            'danger': '#FF4D4F',
            'text': '#262626',
            'text_sec': '#8C8C8C',
            'border': '#E8E8E8',
            'hover': '#F0F0F0',
            'selected': '#E6F7FF',
        }
        self.colors = self.c

        self._setup_styles()

        self.downloaded_file = None
        self.current_stats = None
        self.focus_list = []  # 关注人员列表

        self.setup_ui()

    def _setup_styles(self):
        c = self.c
        self.style.configure(".", background=c['bg'])
        self.style.configure("Treeview", background=c['card'], foreground=c['text'],
            fieldbackground=c['card'], rowheight=40, font=("Microsoft YaHei", 10), borderwidth=0)
        self.style.configure("Treeview.Heading", font=("Microsoft YaHei", 10, "bold"),
            foreground=c['text'], background=c['bg'], padding=10, borderwidth=0)

    def setup_ui(self):
        c = self.c
        self.root.configure(bg=c['bg'])

        # 标题栏
        header = tk.Frame(self.root, bg=c['primary'], height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="禅道BUG分析", font=("Microsoft YaHei", 16, "bold"),
            fg="white", bg=c['primary']).pack(side="left", padx=20, pady=10)

        # 工具栏
        toolbar = tk.Frame(self.root, bg=c['card'], height=56)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)

        btn_frame = tk.Frame(toolbar, bg=c['card'])
        btn_frame.pack(side="left", padx=15, pady=10)

        tk.Button(btn_frame, text="📂 打开文件", font=("Microsoft YaHei", 10), bg=c['card'], fg=c['text'],
            relief="flat", padx=16, pady=6, cursor="hand2", command=self.open_file,
            highlightbackground=c['border']).pack(side="left", padx=3)

        tk.Button(btn_frame, text="⚡ 开始分析", font=("Microsoft YaHei", 10, "bold"), bg=c['primary'], fg="white",
            relief="flat", padx=16, pady=6, cursor="hand2", command=self.analyze_and_report).pack(side="left", padx=3)

        tk.Button(btn_frame, text="📤 导出报告", font=("Microsoft YaHei", 10), bg=c['card'], fg=c['text'],
            relief="flat", padx=16, pady=6, cursor="hand2", command=self.export_report, state="disabled",
            highlightbackground=c['border']).pack(side="left", padx=3)

        # 搜索框
        search_frame = tk.Frame(toolbar, bg=c['card'])
        search_frame.pack(side="right", padx=15, pady=10)

        tk.Label(search_frame, text="🔍", font=("Microsoft YaHei", 12), fg=c['text_sec'], bg=c['card']).pack(side="left", padx=(0, 6))
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *_: self.update_list())
        tk.Entry(search_frame, textvariable=self.search_var, font=("Microsoft YaHei", 10),
            bg=c['bg'], fg=c['text'], insertbackground=c['text'], relief="flat", bd=0, width=15).pack(side="right", padx=6)

        # 文件信息栏
        self.file_bar = tk.Frame(self.root, bg=c['card'], height=36)
        self.file_bar.pack(fill="x")
        self.file_bar.pack_propagate(False)
        self.file_label = tk.Label(self.file_bar, text="未选择文件",
            font=("Microsoft YaHei", 10), fg=c['text_sec'], bg=c['card'])
        self.file_label.pack(side="left", padx=20, pady=6)

        # 统计卡片
        stats_container = tk.Frame(self.root, bg=c['bg'], padx=20, pady=12)
        stats_container.pack(fill="x")
        self.stats_cards = {}
        stats_data = [
            {"key": "total", "label": "总BUG", "color": c['primary']},
            {"key": "active", "label": "激活", "color": c['warning']},
            {"key": "A", "label": "A级", "color": c['danger']},
            {"key": "B", "label": "B级", "color": c['warning']},
            {"key": "C", "label": "C级", "color": c['success']},
        ]
        for sd in stats_data:
            card = tk.Frame(stats_container, bg=c['card'], relief="flat", bd=0)
            card.pack(side="left", padx=6)
            inner = tk.Frame(card, bg=sd['color'], width=4)
            inner.pack(side="left", fill="y")
            tk.Label(card, text="0", font=("Microsoft YaHei", 22, "bold"),
                fg=c['text'], bg=c['card']).pack(anchor="w", padx=(12, 6), pady=(12, 0))
            tk.Label(card, text=sd['label'], font=("Microsoft YaHei", 10),
                fg=c['text_sec'], bg=c['card']).pack(anchor="w", padx=12, pady=(0, 8))
            self.stats_cards[sd['key']] = card.winfo_children()[1]

        # 筛选栏
        filter_bar = tk.Frame(self.root, bg=c['card'], padx=20, pady=10)
        filter_bar.pack(fill="x")

        tk.Label(filter_bar, text="筛选:", font=("Microsoft YaHei", 10), fg=c['text'], bg=c['card']).pack(side="left", padx=(0, 8))
        self.filter_severity = tk.StringVar(value="all")
        self.filter_severity.trace_add('write', lambda *_: self.update_list())
        for txt, val in [("全部", "all"), ("A级", "a"), ("B级", "b"), ("C级", "c")]:
            ttk.Radiobutton(filter_bar, text=txt, variable=self.filter_severity, value=val).pack(side="left", padx=(0, 4))

        tk.Label(filter_bar, text="状态:", font=("Microsoft YaHei", 10), fg=c['text'], bg=c['card']).pack(side="left", padx=(20, 8))
        self.filter_status = tk.StringVar(value="all")
        self.filter_status.trace_add('write', lambda *_: self.update_list())
        for txt, val in [("全部", "all"), ("激活", "active"), ("关闭", "closed")]:
            ttk.Radiobutton(filter_bar, text=txt, variable=self.filter_status, value=val).pack(side="left", padx=(0, 4))

        # 关注人员按钮
        focus_btn = tk.Frame(filter_bar, bg=c['card'])
        focus_btn.pack(side="right")
        self.focus_btn = tk.Button(focus_btn, text="👥 关注人员 (0)",
            font=("Microsoft YaHei", 10), bg=c['card'], fg=c['primary'],
            relief="flat", padx=12, cursor="hand2", command=self.open_focus_window,
            highlightbackground=c['primary'])
        self.focus_btn.pack(side="left")

        # 主表格区
        table_container = tk.Frame(self.root, bg=c['bg'])
        table_container.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        table_card = tk.Frame(table_container, bg=c['card'])
        table_card.pack(fill="both", expand=True)

        tc = tk.Frame(table_card, bg=c['card'], padx=10, pady=10)
        tc.pack(fill="both", expand=True)

        sy = ttk.Scrollbar(tc, orient="vertical")
        sy.pack(side="right", fill="y")
        sx = ttk.Scrollbar(tc, orient="horizontal")
        sx.pack(side="bottom", fill="x")

        columns = ("total", "active", "A", "B", "C", "D")
        self.result_tree = ttk.Treeview(tc, columns=columns, show="tree headings",
            yscrollcommand=sy.set, xscrollcommand=sx.set, selectmode="extended")
        self.result_tree.pack(side="left", fill="both", expand=True)
        sy.config(command=self.result_tree.yview)
        sx.config(command=self.result_tree.xview)

        self.result_tree.column("#0", width=180, minwidth=120)
        for col in columns:
            self.result_tree.column(col, width=100, minwidth=80, anchor="center")

        self.result_tree.heading("#0", text="人员")
        self.result_tree.heading("total", text="总BUG")
        self.result_tree.heading("active", text="激活")
        self.result_tree.heading("A", text="A级")
        self.result_tree.heading("B", text="B级")
        self.result_tree.heading("C", text="C级")
        self.result_tree.heading("D", text="D级")

        self.result_tree.tag_configure("severe", background="#FFF1F0")
        self.result_tree.tag_configure("warning", background="#FFFBE6")
        self.result_tree.tag_configure("normal", background=c['card'])

        self.sort_column = None
        self.sort_reverse = False
        for col in columns + ("#0",):
            self.result_tree.heading(col, command=lambda c=col: self.on_column_click(c))

        self.result_tree.bind("<<TreeviewSelect>>", self.on_selection_change)
        self.result_tree.bind("<Double-Button-1>", self.on_person_select)

        # 底部提示栏
        hint_bar = tk.Frame(self.root, bg=c['card'], height=36)
        hint_bar.pack(fill="x")
        hint_bar.pack_propagate(False)
        self.selected_label = tk.Label(hint_bar, text="",
            font=("Microsoft YaHei", 10), fg=c['primary'], bg=c['card'])
        self.selected_label.pack(side="left", padx=20, pady=6)
        tk.Label(hint_bar, text="双击行查看详情",
            font=("Microsoft YaHei", 9), fg=c['text_sec'], bg=c['card']).pack(side="right", padx=20, pady=6)

        # 状态栏
        status_bar = tk.Frame(self.root, bg=c['primary'], height=28)
        status_bar.pack(fill="x")
        status_bar.pack_propagate(False)
        self.status_label = tk.Label(status_bar, text="就绪",
            font=("Microsoft YaHei", 9), fg="white", bg=c['primary'])
        self.status_label.pack(side="left", padx=15)

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.status_label.config(text=f"[{ts}] {msg}")

    def on_column_click(self, col):
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False
        self.update_list()

    def open_file(self):
        path = filedialog.askopenfilename(title="选择BUG导出文件",
            initialdir=str(Path.home() / "Desktop"),
            filetypes=[("Excel文件", "*.xlsx"), ("CSV文件", "*.csv"), ("所有文件", "*.*")])
        if path:
            self.downloaded_file = path
            self.file_label.config(text=f"📄 {os.path.basename(path)}", fg=self.c['text'])
            self.log(f"已选择: {os.path.basename(path)}")

    def read_excel_file(self, filepath):
        if filepath.endswith('.xlsx'): return self.read_xlsx_simple(filepath)
        with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
            return list(csv.reader(f)), 0

    def read_xlsx_simple(self, filepath):
        with zipfile.ZipFile(filepath, 'r') as z:
            strings = []
            if 'xl/sharedStrings.xml' in z.namelist():
                root = ET.fromstring(z.read('xl/sharedStrings.xml'))
                ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
                for si in root.findall(f'{{{ns}}}si'):
                    t = si.find(f'{{{ns}}}t')
                    if t is not None: strings.append(t.text or '')
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
            if ne > mne: mne, hi = ne, i
        return rows, hi

    def parse_priority(self, s):
        if not s: return 3
        s = str(s).strip()
        m = re.search(r'#(\d+)', s)
        if m: return int(m.group(1))
        try: return int(s)
        except: return 3

    def analyze_and_report(self):
        if not self.downloaded_file or not os.path.exists(self.downloaded_file):
            messagebox.showwarning("提示", "请先打开文件")
            return
        self.log("正在分析...")
        try:
            rows, hi = self.read_excel_file(self.downloaded_file)
            headers = rows[hi]
            hi_map = {}
            for i, h in enumerate(headers):
                hc = str(h).strip()
                if not hc: continue
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
            idx = {k: hi_map.get(k, -1) for k in ['id', 'title', 'priority', 'severity', 'assignedto', 'status']}
            bugs = []
            for row in rows[hi + 1:]:
                if not row or not any(v and v.strip() for v in row if v): continue
                bug_id = row[idx['id']].strip() if idx['id'] >= 0 and idx['id'] < len(row) else ''
                if not bug_id: continue
                bugs.append({
                    'id': bug_id,
                    'title': row[idx['title']].strip() if idx['title'] >= 0 and idx['title'] < len(row) else '',
                    'priority': self.parse_priority(row[idx['priority']].strip() if idx['priority'] >= 0 and idx['priority'] < len(row) else '3'),
                    'severity': self.parse_priority(row[idx['severity']].strip() if idx['severity'] >= 0 and idx['severity'] < len(row) else ''),
                    'assignedTo': row[idx['assignedto']].strip() if idx['assignedto'] >= 0 and idx['assignedto'] < len(row) else '未分配',
                    'status': row[idx['status']].strip() if idx['status'] >= 0 and idx['status'] < len(row) else ''
                })
            if not bugs:
                messagebox.showwarning("警告", "未解析到有效BUG数据")
                return

            owner_stats = defaultdict(lambda: {"total": 0, "bugs": [], "severity_A": 0, "severity_B": 0, "severity_C": 0, "severity_D": 0, "active": 0})
            for b in bugs:
                o = b['assignedTo']
                s = b.get('severity', 3)
                st = b.get('status', '').lower()
                is_act = 'active' in st or st == '' or 'closed' not in st
                owner_stats[o]["total"] += 1
                owner_stats[o]["bugs"].append(b)
                if s == 1: owner_stats[o]["severity_A"] += 1
                elif s == 2: owner_stats[o]["severity_B"] += 1
                elif s == 3: owner_stats[o]["severity_C"] += 1
                else: owner_stats[o]["severity_D"] += 1
                if is_act: owner_stats[o]["active"] += 1

            self.current_stats = {'bugs': bugs, 'owner_stats': dict(owner_stats), 'filename': os.path.basename(self.downloaded_file)}

            # 加载已保存的关注列表
            self.load_focus_list()
            # 过滤掉不在当前数据中的人员
            self.focus_list = [f for f in self.focus_list if f in owner_stats]

            self.update_stats_cards()
            self.update_list()
            self.update_focus_btn()
            self.log(f"分析完成: {len(bugs)}个BUG")
        except Exception as e:
            import traceback
            messagebox.showerror("分析失败", str(e))
            self.log("分析失败")

    def update_stats_cards(self):
        if not self.current_stats: return
        owner_stats = self.current_stats['owner_stats']

        # 只统计关注人员
        if self.focus_list:
            filtered = {k: v for k, v in owner_stats.items() if k in self.focus_list}
        else:
            filtered = owner_stats

        total = sum(d['total'] for d in filtered.values())
        active = sum(d['active'] for d in filtered.values())
        a_count = sum(d['severity_A'] for d in filtered.values())
        b_count = sum(d['severity_B'] for d in filtered.values())
        c_count = sum(d['severity_C'] for d in filtered.values())

        counts = {"total": total, "active": active, "A": a_count, "B": b_count, "C": c_count}
        for key, label in self.stats_cards.items():
            label.config(text=str(counts.get(key, 0)))

    def update_focus_btn(self):
        self.focus_btn.config(text=f"👥 关注人员 ({len(self.focus_list)})")

    def load_focus_list(self):
        default_path = Path(__file__).parent / "focus_list.json"
        if os.path.exists(default_path):
            try:
                with open(default_path, 'r', encoding='utf-8') as f:
                    self.focus_list = json.load(f)
            except:
                self.focus_list = []

    def open_focus_window(self):
        if not self.current_stats:
            messagebox.showwarning("提示", "请先分析数据")
            return
        FocusPersonWindow(self, self.current_stats['owner_stats'], self.focus_list, self.on_focus_confirm)

    def on_focus_confirm(self, focus_list):
        self.focus_list = focus_list
        self.update_stats_cards()
        self.update_list()
        self.update_focus_btn()
        self.log(f"已更新关注人员: {len(focus_list)}人")

    def update_list(self):
        if not self.current_stats: return
        for item in self.result_tree.get_children(): self.result_tree.delete(item)

        f_sev = self.filter_severity.get()
        f_stat = self.filter_status.get()
        search = self.search_var.get().lower()
        owner_stats = self.current_stats['owner_stats']

        # 如果有关注列表，只显示关注人员
        display_stats = {k: v for k, v in owner_stats.items() if k in self.focus_list} if self.focus_list else owner_stats

        owner_data = {}
        for o, data in display_stats.items():
            bugs = data['bugs']
            sev = {'A': data['severity_A'], 'B': data['severity_B'], 'C': data['severity_C'], 'D': data['severity_D']}
            act_total = data['active']
            owner_data[o] = {'total': len(bugs), 'active': act_total, 'severity': sev, 'bugs': bugs}

        col_map = {'#0': 0, 'total': 1, 'active': 2, 'A': 3, 'B': 4, 'C': 5, 'D': 6}
        if self.sort_column and self.sort_column in col_map:
            ci = col_map[self.sort_column]
            def sk(x):
                if ci == 0: return x[0].lower()
                elif ci == 1: return x[1]['total']
                elif ci == 2: return x[1]['active']
                elif ci == 3: return x[1]['severity'].get('A', 0)
                elif ci == 4: return x[1]['severity'].get('B', 0)
                elif ci == 5: return x[1]['severity'].get('C', 0)
                elif ci == 6: return x[1]['severity'].get('D', 0)
                return 0
            sorted_owners = sorted(owner_data.items(), key=sk, reverse=self.sort_reverse)
        else:
            sorted_owners = sorted(owner_data.items(),
                key=lambda x: (x[1]['severity'].get('A', 0) * 10 + x[1]['severity'].get('B', 0) * 3, x[1]['active']), reverse=True)

        for o, data in sorted_owners:
            dn = o.split('(')[0].strip() if '(' in o else o
            if search and search not in dn.lower(): continue

            sev = data['severity']
            if f_sev != "all":
                fs = f_sev.upper()
                if sev.get(fs, 0) == 0: continue
            if f_stat == "active" and data['active'] == 0: continue

            tag = "severe" if sev['A'] > 0 else "warning" if sev['B'] > 3 else "normal"
            self.result_tree.insert("", "end", text=dn,
                values=(data['total'], data['active'], sev['A'], sev['B'], sev['C'], sev['D']),
                tags=(tag,))

    def on_selection_change(self, event=None):
        if not self.current_stats: return
        sel = self.result_tree.selection()
        if not sel:
            self.selected_label.config(text="")
            return
        names = [self.result_tree.item(s, 'text') for s in sel]
        names_str = ", ".join(names[:5])
        if len(names) > 5: names_str += f"... (+{len(names)-5})"
        self.selected_label.config(text=f"已选: {names_str} ({len(names)}人)")

    def on_person_select(self, event):
        if not self.current_stats: return
        sel = self.result_tree.selection()
        if len(sel) == 1:
            name = self.result_tree.item(sel[0], 'text')
            owner_stats = self.current_stats['owner_stats']
            for o, data in owner_stats.items():
                dn = o.split('(')[0].strip() if '(' in o else o
                if dn == name:
                    self.show_detail_window(o, data['bugs'])
                    break

    def show_detail_window(self, title, bugs):
        win = tk.Toplevel(self.root)
        win.title(f"BUG详情 - {title}")
        win.geometry("900x500")
        win.transient(self.root)

        sev = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
        act_total = 0
        for b in bugs:
            s = b.get('severity', 3)
            sl = 'A' if s == 1 else 'B' if s == 2 else 'C' if s == 3 else 'D'
            sev[sl] += 1
            st = b.get('status', '').lower()
            if 'active' in st or st == '' or 'closed' not in st:
                act_total += 1

        header = tk.Frame(win, bg=self.c['primary'], padx=15, pady=12)
        header.pack(fill="x")
        tk.Label(header, text=f"{title}", font=("Microsoft YaHei", 14, "bold"), fg="white", bg=self.c['primary']).pack(side="left")
        tk.Label(header, text=f"总BUG: {len(bugs)} | 激活: {act_total} | A:{sev['A']} B:{sev['B']} C:{sev['C']} D:{sev['D']}",
            font=("Microsoft YaHei", 10), fg="white", bg=self.c['primary']).pack(side="right")

        tc = tk.Frame(win, padx=10, pady=10)
        tc.pack(fill="both", expand=True)
        sy = ttk.Scrollbar(tc, orient="vertical")
        sy.pack(side="right", fill="y")
        sx = ttk.Scrollbar(tc, orient="horizontal")
        sx.pack(side="bottom", fill="x")

        tree = ttk.Treeview(tc, columns=("id", "severity", "status", "title"), show="tree headings",
                           yscrollcommand=sy.set, xscrollcommand=sx.set)
        tree.pack(side="left", fill="both", expand=True)
        sy.config(command=tree.yview)
        sx.config(command=tree.xview)

        tree.column("id", width=80, anchor="center")
        tree.column("severity", width=60, anchor="center")
        tree.column("status", width=100, anchor="center")
        tree.column("title", width=600)
        tree.heading("id", text="Bug ID")
        tree.heading("severity", text="严重")
        tree.heading("status", text="状态")
        tree.heading("title", text="标题")

        tree.tag_configure("severe", foreground=self.c['danger'], font=("Microsoft YaHei", 10, "bold"))
        tree.tag_configure("warning", foreground=self.c['warning'])
        tree.tag_configure("normal", foreground=self.c['success'])

        for b in sorted(bugs, key=lambda x: x.get('severity', 3)):
            s = b.get('severity', 3)
            sl = 'A' if s == 1 else 'B' if s == 2 else 'C' if s == 3 else 'D'
            st = b.get('status', '')
            tag = "severe" if sl == 'A' else "warning" if sl == 'B' else "normal"
            tree.insert("", "end", values=(b['id'], sl, st, b['title']), tags=(tag,))

        btn_frame = tk.Frame(win, bg=self.c['card'], pady=10)
        btn_frame.pack(fill="x")
        tk.Button(btn_frame, text="关闭", font=("Microsoft YaHei", 10), command=win.destroy).pack(side="right", padx=15)

    def export_report(self):
        if not self.current_stats:
            messagebox.showwarning("提示", "请先分析数据")
            return
        path = filedialog.asksaveasfilename(title="导出报告",
            defaultextension=".txt", filetypes=[("文本文件", "*.txt"), ("CSV文件", "*.csv"), ("所有文件", "*.*")])
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write("禅道BUG统计分析报告\n")
                    f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"文件名: {self.current_stats['filename']}\n")
                    f.write(f"BUG总数: {len(self.current_stats['bugs'])}\n\n")
                    owner_stats = self.current_stats['owner_stats']
                    display_stats = {k: v for k, v in owner_stats.items() if k in self.focus_list} if self.focus_list else owner_stats
                    sorted_owners = sorted(display_stats.items(),
                        key=lambda x: x[1]['severity_A'] * 10 + x[1]['severity_B'] * 3, reverse=True)
                    for o, data in sorted_owners[:20]:
                        f.write(f"{o}: {data['total']}个BUG [A:{data['severity_A']} B:{data['severity_B']} C:{data['severity_C']} D:{data['severity_D']}]\n")
                messagebox.showinfo("成功", f"报告已导出到:\n{path}")
                self.log(f"报告已导出: {path}")
            except Exception as e:
                messagebox.showerror("导出失败", str(e))


if __name__ == "__main__":
    app = ZentaoBugTool()
    app.root.mainloop()
