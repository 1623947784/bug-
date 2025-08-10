"""简易 Bug 追踪器 (Tkinter 版本)

==================== 概览 ====================
这是一个使用 Tkinter 构建的桌面 GUI 示例程序，用于演示最基础的
Bug / 任务追踪功能 (Issue Tracking)。特点：轻量、单文件、无第三方依赖。

核心功能:
1. 添加 Bug：描述、优先级 (Low/Medium/High)、状态 (Open/In Progress/Done)
2. 查看列表（ttk.Treeview 表格展示）
3. 编辑选中条目（进入编辑模式后可保存修改）
4. 标记完成（快速把状态改为 Done）
5. 删除选中条目
6. 本地 JSON 自动持久化 (bugs.json) —— 每次增删改都会立即写入
7. 退出前再尝试保存一次，保证数据落盘

持久化策略:
- 使用 JSON 数组保存所有 Bug；每个 Bug 拥有自增整数 ID
- 在加载时扫描现有最大 ID 推断下一个 ID，避免重复

架构划分:
- 数据层: Bug 数据类 + BugTracker 管理列表与读写文件
- 表现层: BugTrackerApp 负责 Tkinter GUI、事件绑定、与数据层交互

线程 / 并发说明:
- 全部逻辑运行在主线程事件循环中，无并发访问问题
- 如果未来添加后台任务（如自动同步服务器），应引入线程/队列并在主线程中安全更新 UI

错误处理策略:
- 读取 JSON 出错 -> 弹出警告并回到空数据
- 保存出错 -> 弹出错误提示但不中断程序

扩展方向（可逐步演进）:
- 添加过滤 / 搜索 / 排序控制
- 增加更多状态（Duplicate / Invalid / Won't Fix）
- 支持批量操作、导出 CSV、导入导出备份
- 引入日志记录、Undo/Redo、标签系统、负责人字段
- 替换 UI 框架为 PySide6 / PyQt6 以获得更现代外观

运行: 直接执行 `python main.py`

设计目标: 代码清晰、注释充分、易于二次开发与教学演示。
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import filedialog  # 新增: 保存文件对话框
from tkinter import font as tkfont  # UI 字体缩放


# --------------------------- 数据模型与存储 --------------------------- #


@dataclass
class Bug:
    id: int
    description: str
    priority: str  # Low / Medium / High
    status: str  # Open / In Progress / Done
    created_at: str  # ISO 字符串
    updated_at: str  # ISO 字符串

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Bug":
        return Bug(**data)

    """Bug 数据对象.

    字段说明:
    - id:            自增主键（程序内部维护，不重复）
    - description:   Bug 描述（纯文本）
    - priority:      优先级 (Low / Medium / High) —— 可扩展为枚举
    - status:        状态 (Open / In Progress / Done) —— 可扩展
    - created_at:    创建时间 ISO8601 字符串（到秒）
    - updated_at:    最近一次更新（编辑 / 状态变化）时间

    为什么使用 dataclass:
    - 自动实现 __init__ / __repr__ / asdict 支持
    - 结构紧凑，利于序列化
    """


class BugTracker:
    def __init__(self, data_file: str = "bugs.json") -> None:
        self.data_file = data_file
        self.bugs: List[Bug] = []
        self._next_id = 1
        self.load()

    """数据管理器 (领域层 / Repository 角色).

    职责:
    - 负责内存中维护 Bug 列表
    - 提供 CRUD API
    - 负责与 JSON 文件的读写持久化

    为什么与 GUI 分离:
    - 便于未来替换为命令行 / Web / 其它界面
    - 便于后续编写单元测试（只需针对 BugTracker 测试业务逻辑）
    """

    # ----------------- 持久化 ----------------- #
    def load(self) -> None:
        """从 JSON 文件加载数据.

        容错:
        - 文件不存在: 忽略 (保持空列表)
        - JSON 格式损坏: 发出警告并清空数据
        """
        if not os.path.exists(self.data_file):
            return
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.bugs = [Bug.from_dict(item) for item in raw]
            if self.bugs:
                self._next_id = max(b.id for b in self.bugs) + 1
        except (json.JSONDecodeError, OSError) as e:
            messagebox.showwarning("读取失败", f"数据文件损坏或无法读取: {e}\n将从空数据开始。")
            self.bugs = []
            self._next_id = 1

    def save(self) -> None:
        """将内存中的 Bug 列表写入 JSON 文件.

        写入策略: 覆盖写 (简单直接)；数据量小可忽略性能问题。
        异常: 捕获 OSError 并用 messagebox 告知用户。
        """
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump([b.to_dict() for b in self.bugs], f, ensure_ascii=False, indent=2)
        except OSError as e:
            messagebox.showerror("保存失败", f"无法保存数据: {e}")

    # ----------------- CRUD 操作 ----------------- #
    def add_bug(self, description: str, priority: str, status: str = "Open") -> Bug:
        """创建一个新的 Bug 并立即持久化.

        参数:
        - description: 文本描述，会去除首尾空白
        - priority:    用户下拉选择的优先级
        - status:      初始状态 (默认 Open)

        返回: 新建的 Bug 对象 (已加入列表)
        """
        now = datetime.now().isoformat(timespec="seconds")
        bug = Bug(
            id=self._next_id,
            description=description.strip(),
            priority=priority,
            status=status,
            created_at=now,
            updated_at=now,
        )
        self.bugs.append(bug)
        self._next_id += 1
        self.save()
        return bug

    def get_bug(self, bug_id: int) -> Optional[Bug]:
        """按 ID 查找 Bug.

        找不到返回 None.
        """
        return next((b for b in self.bugs if b.id == bug_id), None)

    def update_bug(self, bug_id: int, *, description: Optional[str] = None, priority: Optional[str] = None, status: Optional[str] = None) -> bool:
        """更新指定 Bug 的部分字段.

        仅在字段发生真实变化时才刷新 updated_at 并保存，减少无谓写盘。

        返回: 是否有字段被修改。
        """
        bug = self.get_bug(bug_id)
        if not bug:
            return False
        changed = False
        if description is not None and description.strip() and description.strip() != bug.description:
            bug.description = description.strip()
            changed = True
        if priority is not None and priority != bug.priority:
            bug.priority = priority
            changed = True
        if status is not None and status != bug.status:
            bug.status = status
            changed = True
        if changed:
            bug.updated_at = datetime.now().isoformat(timespec="seconds")
            self.save()
        return changed

    def delete_bug(self, bug_id: int) -> bool:
        """删除指定 ID 的 Bug.

        返回: 是否删除成功 (存在并被移除)。
        """
        before = len(self.bugs)
        self.bugs = [b for b in self.bugs if b.id != bug_id]
        if len(self.bugs) != before:
            self.save()
            return True
        return False

    def list_bugs(self) -> List[Bug]:
        """返回当前所有 Bug 的浅拷贝列表 (避免外部直接修改内部列表)."""
        return list(self.bugs)

    def to_markdown(self) -> str:
        """生成当前 Bug 列表的 Markdown 表格字符串."""
        headers = ["ID", "描述", "优先级", "状态", "创建时间", "更新时间"]
        lines = []
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        def esc(text: str) -> str:
            # 转义表格分隔符
            return text.replace("|", "\\|")
        for b in sorted(self.bugs, key=lambda x: x.id):
            lines.append(
                f"| {b.id} | {esc(b.description)} | {b.priority} | {b.status} | {b.created_at} | {b.updated_at} |"
            )
        if not self.bugs:
            lines.append("| (空) | - | - | - | - | - |")
        return "\n".join(lines)


# --------------------------- GUI 部分 --------------------------- #


class BugTrackerApp:
    PRIORITIES = ["Low", "Medium", "High"]
    STATUSES = ["Open", "In Progress", "Done"]

    def __init__(self, root: tk.Tk, tracker: BugTracker) -> None:
        """初始化 GUI 应用.

        参数:
        - root: Tk 根窗口
        - tracker: 数据管理器实例

        初始化顺序:
        1. 设置窗口标题和尺寸
        2. 构建界面控件
        3. 填充现有数据
        4. 绑定窗口关闭事件
        """
        self.root = root
        self.tracker = tracker
        self.root.title("简易 Bug 追踪器")
        self.root.geometry("900x520")
        self._build_widgets()
        self._populate()
        self._editing_bug_id: Optional[int] = None
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ----------------- UI 构建 ----------------- #
    def _build_widgets(self) -> None:
        """创建并布局所有界面控件.

        布局说明:
        - 上部: 表单 (LabelFrame) 输入描述 / 优先级 / 状态 + 添加/重置按钮
        - 中部: 操作按钮行 (编辑 / 标记完成 / 删除 / 刷新)
        - 下部: Treeview 表格 + 状态栏

        无返回值，创建的控件绑定到 self.* 以便后续访问。
        """
        # 输入框区域
        form = ttk.LabelFrame(self.root, text="新增 / 编辑 Bug")
        form.pack(fill="x", padx=8, pady=6)

        ttk.Label(form, text="描述:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.desc_var = tk.StringVar()
        self.desc_entry = ttk.Entry(form, textvariable=self.desc_var, width=60)
        self.desc_entry.grid(row=0, column=1, columnspan=4, sticky="we", padx=4, pady=4)

        ttk.Label(form, text="优先级:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.priority_var = tk.StringVar(value="Medium")
        self.priority_cb = ttk.Combobox(form, textvariable=self.priority_var, values=self.PRIORITIES, width=10, state="readonly")
        self.priority_cb.grid(row=1, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(form, text="状态:").grid(row=1, column=2, sticky="w", padx=4, pady=4)
        self.status_var = tk.StringVar(value="Open")
        self.status_cb = ttk.Combobox(form, textvariable=self.status_var, values=self.STATUSES, width=12, state="readonly")
        self.status_cb.grid(row=1, column=3, sticky="w", padx=4, pady=4)

        self.add_btn = ttk.Button(form, text="添加", command=self.on_add)
        self.add_btn.grid(row=0, column=5, rowspan=2, sticky="nswe", padx=6, pady=4)

        self.reset_btn = ttk.Button(form, text="重置表单", command=self.reset_form)
        self.reset_btn.grid(row=0, column=6, rowspan=2, sticky="nswe", padx=6, pady=4)

        for i in range(0, 7):
            form.columnconfigure(i, weight=1)

        # 操作按钮区域
        actions = ttk.Frame(self.root)
        actions.pack(fill="x", padx=8, pady=4)

        self.edit_btn = ttk.Button(actions, text="编辑选中", command=self.on_edit)
        self.edit_btn.pack(side="left", padx=4)

        self.done_btn = ttk.Button(actions, text="标记完成", command=self.on_mark_done)
        self.done_btn.pack(side="left", padx=4)

        self.delete_btn = ttk.Button(actions, text="删除选中", command=self.on_delete)
        self.delete_btn.pack(side="left", padx=4)

        self.export_btn = ttk.Button(actions, text="导出 Markdown", command=self.on_export_markdown)  # 新增按钮
        self.export_btn.pack(side="left", padx=4)

        self.refresh_btn = ttk.Button(actions, text="刷新", command=self._populate)
        self.refresh_btn.pack(side="left", padx=4)

        # 搜索 / 过滤区域
        search_frame = ttk.Frame(self.root)
        search_frame.pack(fill="x", padx=8, pady=(0, 4))

        ttk.Label(search_frame, text="关键词:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=28)
        self.search_entry.pack(side="left", padx=(4, 8))
        self.search_entry.bind("<Return>", lambda e: self.on_search())

        ttk.Label(search_frame, text="优先级:").pack(side="left")
        self.priority_filter_var = tk.StringVar(value="全部")
        self.priority_filter_cb = ttk.Combobox(
            search_frame,
            textvariable=self.priority_filter_var,
            width=8,
            state="readonly",
            values=["全部"] + self.PRIORITIES,
        )
        self.priority_filter_cb.pack(side="left", padx=(4, 8))
        self.priority_filter_cb.bind("<<ComboboxSelected>>", lambda e: self.on_search(auto=True))

        ttk.Label(search_frame, text="状态:").pack(side="left")
        self.status_filter_var = tk.StringVar(value="全部")
        self.status_filter_cb = ttk.Combobox(
            search_frame,
            textvariable=self.status_filter_var,
            width=12,
            state="readonly",
            values=["全部"] + self.STATUSES,
        )
        self.status_filter_cb.pack(side="left", padx=(4, 8))
        self.status_filter_cb.bind("<<ComboboxSelected>>", lambda e: self.on_search(auto=True))

        self.search_btn = ttk.Button(search_frame, text="搜索", command=self.on_search)
        self.search_btn.pack(side="left")
        self.clear_search_btn = ttk.Button(search_frame, text="清除过滤", command=self.on_clear_search)
        self.clear_search_btn.pack(side="left", padx=(6, 0))

        # 列表区域
        columns = ("id", "description", "priority", "status", "created_at", "updated_at")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings", selectmode="browse")
        self.tree.pack(fill="both", expand=True, padx=8, pady=4)

        headers = {
            "id": "ID",
            "description": "描述",
            "priority": "优先级",
            "status": "状态",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        }
        widths = {
            "id": 40,
            "description": 320,
            "priority": 80,
            "status": 110,
            "created_at": 140,
            "updated_at": 140,
        }
        for col in columns:
            self.tree.heading(col, text=headers[col])
            self.tree.column(col, width=widths[col], anchor="center")

        self.tree.bind("<Double-1>", lambda e: self.on_edit())

        # 底部状态栏
        self.status_text = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_text, anchor="w")
        status_bar.pack(fill="x", padx=4, pady=(0, 2))

    # ----------------- 事件处理 ----------------- #
    def on_add(self) -> None:
        """添加或保存修改.

        行为依据 _editing_bug_id:
        - 为 None: 新增记录
        - 不为 None: 更新对应记录后退出编辑模式
        """
        desc = self.desc_var.get().strip()
        if not desc:
            messagebox.showinfo("提示", "描述不能为空")
            return
        if self._editing_bug_id is None:
            bug = self.tracker.add_bug(description=desc, priority=self.priority_var.get(), status=self.status_var.get())
            self._insert_tree_item(bug)
            self.status_text.set(f"添加 Bug #{bug.id}")
        else:
            changed = self.tracker.update_bug(
                self._editing_bug_id,
                description=desc,
                priority=self.priority_var.get(),
                status=self.status_var.get(),
            )
            if changed:
                self.status_text.set(f"更新 Bug #{self._editing_bug_id}")
            else:
                self.status_text.set("无变化")
            self._populate(select_id=self._editing_bug_id)
            self._editing_bug_id = None
            self.add_btn.config(text="添加")
        self.reset_form(clear_status=False)

    def on_edit(self) -> None:
        """进入编辑模式: 将选中行内容填充到表单并切换按钮文字."""
        bug_id = self._get_selected_bug_id()
        if bug_id is None:
            messagebox.showinfo("提示", "请选择一个条目")
            return
        bug = self.tracker.get_bug(bug_id)
        if not bug:
            return
        self.desc_var.set(bug.description)
        self.priority_var.set(bug.priority)
        self.status_var.set(bug.status)
        self._editing_bug_id = bug.id
        self.add_btn.config(text="保存修改")
        self.status_text.set(f"编辑模式: #{bug.id}")
        self.desc_entry.focus_set()

    def on_mark_done(self) -> None:
        """将选中 Bug 状态改为 Done (若尚未完成)."""
        bug_id = self._get_selected_bug_id()
        if bug_id is None:
            messagebox.showinfo("提示", "请选择一个条目")
            return
        bug = self.tracker.get_bug(bug_id)
        if not bug:
            return
        if bug.status == "Done":
            self.status_text.set("该条目已是 Done")
            return
        self.tracker.update_bug(bug_id, status="Done")
        self._populate(select_id=bug_id)
        self.status_text.set(f"Bug #{bug_id} 标记 Done")

    def on_delete(self) -> None:
        """删除当前选中 Bug（确认对话框防误操作）."""
        bug_id = self._get_selected_bug_id()
        if bug_id is None:
            messagebox.showinfo("提示", "请选择一个条目")
            return
        if messagebox.askyesno("确认删除", f"确定要删除 Bug #{bug_id} 吗？"):
            self.tracker.delete_bug(bug_id)
            self._populate()
            self.status_text.set(f"删除 Bug #{bug_id}")
            if self._editing_bug_id == bug_id:
                self._editing_bug_id = None
                self.add_btn.config(text="添加")
                self.reset_form(clear_status=False)

    def reset_form(self, clear_status: bool = True) -> None:
        """重置输入表单.

        参数 clear_status: 是否同时重置底部状态栏文本。
        """
        self.desc_var.set("")
        self.priority_var.set("Medium")
        self.status_var.set("Open")
        if clear_status:
            self.status_text.set("表单已重置")
        self.desc_entry.focus_set()

    def on_close(self) -> None:
        """窗口关闭回调: 先保存再销毁窗口."""
        # 关闭前保存，确保最新状态写入磁盘
        self.tracker.save()
        self.root.destroy()

    # ----------------- Treeview 操作 ----------------- #
    def _populate(self, *, select_id: Optional[int] = None) -> None:
        """刷新 Treeview 显示.

        参数 select_id: 刷新后尝试选中指定 ID 的行（用于编辑/更新反馈）。
        """
        for child in self.tree.get_children():
            self.tree.delete(child)
        # 遍历过滤结果并插入到表格
        for bug in self._get_filtered_bugs():
            self._insert_tree_item(bug)
        # 若传入 select_id，刷新后尝试重新选中该行
        if select_id is not None:
            for iid in self.tree.get_children():
                if int(self.tree.set(iid, "id")) == select_id:
                    self.tree.selection_set(iid)
                    self.tree.focus(iid)
                    self.tree.see(iid)
                    break

    def _insert_tree_item(self, bug: Bug) -> None:
        """向 Treeview 追加一行."""
        values = (
            bug.id,
            bug.description,
            bug.priority,
            bug.status,
            bug.created_at,
            bug.updated_at,
        )
        self.tree.insert("", "end", values=values)

    def _get_selected_bug_id(self) -> Optional[int]:
        """获取当前选中行的 Bug ID；若无选中或解析失败返回 None."""
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            bug_id = int(self.tree.set(sel[0], "id"))
            return bug_id
        except Exception:
            return None

    # ----------------- 搜索 / 过滤 ----------------- #
    def _get_filtered_bugs(self) -> List[Bug]:
        """根据当前搜索/过滤条件返回排序后的 bug 列表.

        过滤逻辑:
        - 关键词: 描述中大小写不敏感包含
        - 优先级: 匹配选中 (忽略 "全部")
        - 状态:   匹配选中 (忽略 "全部")
        """
        bugs = self.tracker.list_bugs()
        keyword = (self.search_var.get().strip().lower() if hasattr(self, "search_var") else "")
        pri_filter = getattr(self, "priority_filter_var", tk.StringVar(value="全部")).get()
        status_filter = getattr(self, "status_filter_var", tk.StringVar(value="全部")).get()

        def match(b: Bug) -> bool:
            if keyword and keyword not in b.description.lower():
                return False
            if pri_filter != "全部" and b.priority != pri_filter:
                return False
            if status_filter != "全部" and b.status != status_filter:
                return False
            return True

        return sorted([b for b in bugs if match(b)], key=lambda b: b.id)

    def on_search(self, auto: bool = False) -> None:
        """执行搜索过滤并刷新列表.

        参数 auto: 是否为自动触发 (下拉选择变化)，用于决定状态栏文案。
        """
        self._populate()
        if not auto:
            self.status_text.set("已应用搜索过滤")

    def on_clear_search(self) -> None:
        """清除所有搜索与过滤条件并刷新列表."""
        self.search_var.set("")
        self.priority_filter_var.set("全部")
        self.status_filter_var.set("全部")
        self._populate()
        self.status_text.set("过滤已清除")

    def on_export_markdown(self) -> None:
        """导出当前列表为 Markdown 文件."""
        if not self.tracker.list_bugs():
            if not messagebox.askyesno("确认", "当前没有任何条目，仍要导出一个空表格吗？"):
                return
        md_text = self.tracker.to_markdown()
        default_name = f"bugs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        path = filedialog.asksaveasfilename(
            title="选择保存位置",
            defaultextension=".md",
            initialfile=default_name,
            filetypes=[("Markdown 文件", "*.md"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("# Bug 列表导出\n\n")
                f.write(md_text)
                f.write("\n")
            self.status_text.set(f"已导出: {os.path.basename(path)}")
            messagebox.showinfo("导出成功", f"已保存到:\n{path}")
        except OSError as e:
            messagebox.showerror("导出失败", f"写入文件出错:\n{e}")


# --------------------------- 入口 --------------------------- #


def main() -> None:
    """程序入口.

    负责:
    1. 计算数据文件路径（与脚本同目录）
    2. 初始化数据层与 Tk 根窗口
    3. Windows 下尽力开启 DPI 感知减少模糊
    4. 启动事件循环

    无返回值，阻塞直到窗口关闭。
    """
    # 数据文件放在脚本同目录，避免工作目录变化导致找不到文件
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    data_file = os.path.join(script_dir, "bugs.json")
    tracker = BugTracker(data_file=data_file)
    root = tk.Tk()

    # ---------------- UI 放大设置 ---------------- #
    # 通过环境变量 BUG_TRACKER_SCALE 控制整体缩放 (1.0~2.0)
    try:
        scale_env = float(os.getenv("BUG_TRACKER_SCALE", "1.3"))
    except ValueError:
        scale_env = 1.0
    UI_SCALE = max(1.0, min(scale_env, 2.0))

    def apply_ui_scale(root: tk.Tk, scale: float) -> None:
        """统一调整字体、行高、padding 来放大界面.

        - 修改 Tk 命名字体: TkDefaultFont/TkTextFont/TkMenuFont/TkHeadingFont
        - 设置 ttk 控件样式 padding / rowheight
        - 调整 tk scaling (DPI 缩放)
        """
        base_pt = int(11 * scale)
        heading_pt = int(base_pt * 1.15)
        for name, size in [
            ("TkDefaultFont", base_pt),
            ("TkTextFont", base_pt),
            ("TkMenuFont", base_pt),
            ("TkHeadingFont", heading_pt),
        ]:
            try:
                tkfont.nametofont(name).configure(size=size)
            except Exception:
                pass
        # global scaling
        try:
            root.tk.call('tk', 'scaling', scale)
        except Exception:
            pass
        style = ttk.Style(root)
        # 控件 padding / 行高
        btn_pad_x = int(8 * scale)
        btn_pad_y = int(4 * scale)
        style.configure("TButton", padding=(btn_pad_x, btn_pad_y))
        style.configure("TCombobox", padding=(4 * scale, 2 * scale, 4 * scale, 2 * scale))
        style.configure("Treeview", rowheight=int(24 * scale))

    if UI_SCALE > 1.01:
        apply_ui_scale(root, UI_SCALE)

    # Windows 高 DPI 适配（可忽略失败）
    try:
        if sys.platform.startswith("win"):
            from ctypes import windll

            windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]
    except Exception:
        pass
    app = BugTrackerApp(root, tracker)
    # 初始窗口尺寸按缩放简单放大
    if UI_SCALE > 1.01:
        try:
            root.update_idletasks()
            w = int(root.winfo_width() * UI_SCALE)
            h = int(root.winfo_height() * UI_SCALE)
            root.geometry(f"{w}x{h}")
        except Exception:
            pass
    root.mainloop()


if __name__ == "__main__":
    main()

