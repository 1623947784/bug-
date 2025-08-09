"""简易 Bug 追踪器 (Tkinter 版本)

功能:
1. 添加 Bug：描述、优先级 (Low/Medium/High)、状态 (Open/In Progress/Done)
2. 查看列表（Treeview）
3. 编辑选中条目
4. 标记完成（状态改为 Done）
5. 删除选中条目
6. 本地 JSON 自动持久化 (bugs.json)
7. 退出前自动保存；每次 CRUD 操作即时保存

文件结构: 仅此一个 main.py (标准库实现，无需额外依赖)

运行: python main.py
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


class BugTracker:
	def __init__(self, data_file: str = "bugs.json") -> None:
		self.data_file = data_file
		self.bugs: List[Bug] = []
		self._next_id = 1
		self.load()

	# ----------------- 持久化 ----------------- #
	def load(self) -> None:
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
		try:
			with open(self.data_file, "w", encoding="utf-8") as f:
				json.dump([b.to_dict() for b in self.bugs], f, ensure_ascii=False, indent=2)
		except OSError as e:
			messagebox.showerror("保存失败", f"无法保存数据: {e}")

	# ----------------- CRUD 操作 ----------------- #
	def add_bug(self, description: str, priority: str, status: str = "Open") -> Bug:
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
		return next((b for b in self.bugs if b.id == bug_id), None)

	def update_bug(self, bug_id: int, *, description: Optional[str] = None, priority: Optional[str] = None, status: Optional[str] = None) -> bool:
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
		before = len(self.bugs)
		self.bugs = [b for b in self.bugs if b.id != bug_id]
		if len(self.bugs) != before:
			self.save()
			return True
		return False

	def list_bugs(self) -> List[Bug]:
		return list(self.bugs)


# --------------------------- GUI 部分 --------------------------- #


class BugTrackerApp:
	PRIORITIES = ["Low", "Medium", "High"]
	STATUSES = ["Open", "In Progress", "Done"]

	def __init__(self, root: tk.Tk, tracker: BugTracker) -> None:
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

		self.refresh_btn = ttk.Button(actions, text="刷新", command=self._populate)
		self.refresh_btn.pack(side="left", padx=4)

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
		self.desc_var.set("")
		self.priority_var.set("Medium")
		self.status_var.set("Open")
		if clear_status:
			self.status_text.set("表单已重置")
		self.desc_entry.focus_set()

	def on_close(self) -> None:
		# 关闭前保存
		self.tracker.save()
		self.root.destroy()

	# ----------------- Treeview 操作 ----------------- #
	def _populate(self, *, select_id: Optional[int] = None) -> None:
		for child in self.tree.get_children():
			self.tree.delete(child)
		for bug in sorted(self.tracker.list_bugs(), key=lambda b: b.id):
			self._insert_tree_item(bug)
		if select_id is not None:
			for iid in self.tree.get_children():
				if int(self.tree.set(iid, "id")) == select_id:
					self.tree.selection_set(iid)
					self.tree.focus(iid)
					self.tree.see(iid)
					break

	def _insert_tree_item(self, bug: Bug) -> None:
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
		sel = self.tree.selection()
		if not sel:
			return None
		try:
			bug_id = int(self.tree.set(sel[0], "id"))
			return bug_id
		except Exception:
			return None


# --------------------------- 入口 --------------------------- #


def main() -> None:
	# 数据文件放在脚本同目录
	script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
	data_file = os.path.join(script_dir, "bugs.json")
	tracker = BugTracker(data_file=data_file)
	root = tk.Tk()
	# Windows 高 DPI 适配（可忽略失败）
	try:
		if sys.platform.startswith("win"):
			from ctypes import windll

			windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]
	except Exception:
		pass
	app = BugTrackerApp(root, tracker)
	root.mainloop()


if __name__ == "__main__":
	main()

