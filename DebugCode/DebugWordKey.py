
# ============================================================
# DebugWordKey.py
# LexisLingo 单词字段批量增删工具（tkinter）
# 方案A：内存操作 + 手动保存，保存前自动备份为 .db.copy
# ============================================================
import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import os
import json
import shutil
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

import sys
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
_qt_app = QApplication.instance() or QApplication(sys.argv)

from _Enviro import EndeCrypt
from Config  import KEY_LABEL
class WordViewDialog(tk.Toplevel):
    """双击单词查看全部字段，只读"""

    def __init__(self, parent, word: str, data: dict):
        super().__init__(parent)
        self.title(f"字段详情：{word}")
        self.geometry("580x500")
        self.resizable(True, True)
        self.grab_set()

        tk.Label(self, text=word,
                 font=("微软雅黑", 15, "bold"),
                 fg="#2c3e50").pack(pady=(14, 2))
        tk.Label(self, text=f"共 {len(data)} 个字段  （只读）",
                 fg="#95a5a6", font=("微软雅黑", 9)).pack()

        ttk.Separator(self).pack(fill="x", padx=10, pady=6)

        cols = ("Key", "类型", "值")
        tree = ttk.Treeview(self, columns=cols, show="headings",
                            selectmode="browse")
        tree.heading("Key",  text="Key")
        tree.heading("类型", text="类型")
        tree.heading("值",   text="值")
        tree.column("Key",  width=120, anchor="w")
        tree.column("类型", width=60,  anchor="center")
        tree.column("值",   width=340, anchor="w")

        tree.tag_configure("dict_key", background="#f0f4ff")
        tree.tag_configure("normal",   background="#ffffff")

        for k, v in data.items():
            if isinstance(v, dict):
                # 复杂类型：先插父行
                tree.insert("", "end", iid=f"__k__{k}",
                            values=(k, "dict", f"[{len(v)} 个字段]"),
                            tags=("dict_key",))
                # 展开子字段
                for sk, sv in v.items():
                    display = str(sv) if not isinstance(sv, (dict, list)) else json.dumps(sv, ensure_ascii=False)
                    tree.insert("", "end",
                                values=(f"  └ {sk}", type(sv).__name__, display),
                                tags=("normal",))
            elif isinstance(v, list):
                s = json.dumps(v, ensure_ascii=False)
                display = s[:80] + "…" if len(s) > 80 else s
                tree.insert("", "end",
                            values=(k, "list", display),
                            tags=("normal",))
            else:
                tree.insert("", "end",
                            values=(k, type(v).__name__, str(v)),
                            tags=("normal",))

        vsb = ttk.Scrollbar(self, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y", padx=(0, 6))
        tree.pack(fill="both", expand=True, padx=6)

        tk.Button(self, text="关闭", command=self.destroy,
                  bg="#dfe6e9", font=("微软雅黑", 10),
                  width=10).pack(pady=10)
# ══════════════════════════════════════════════════════════════
# 加解密 + 数据库读写
# ══════════════════════════════════════════════════════════════
def _encode(val: dict, key: str) -> str:
    return EndeCrypt(json.dumps(val, ensure_ascii=False), key)

def _decode(blob: str, key: str) -> dict:
    return json.loads(EndeCrypt(blob, key, decode=True))

def _load_all(db_path: str, key: str) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT word, data FROM UserWordF").fetchall()
    conn.close()
    result = {}
    for row in rows:
        try:
            result[row["word"]] = _decode(row["data"], key)
        except Exception:
            result[row["word"]] = {}
    return result

def _save_all(db_path: str, data: dict, key: str):
    # 保存前先备份原文件为 .db.copy
    copy_path = db_path + ".copy"
    if os.path.exists(db_path):
        shutil.copy2(db_path, copy_path)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("BEGIN")
        conn.execute("DELETE FROM UserWordF")
        rows = [(w, _encode(v, key)) for w, v in data.items()]
        conn.executemany(
            "INSERT INTO UserWordF(word, data) VALUES(?, ?)", rows)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        conn.close()
        raise
    conn.close()

def _build_db_path(course: str, user: str) -> str:
    return f"Data/{course}/UserConfig/{user}_ld.db"

def _cast_value(raw: str, type_str: str):
    if type_str == "bool":
        return raw.strip().lower() in ("true", "1", "yes")
    if type_str == "int":
        return int(raw.strip())
    if type_str == "float":
        return float(raw.strip())
    return raw  # str


# ══════════════════════════════════════════════════════════════
# 主窗口
# ══════════════════════════════════════════════════════════════
class DebugWordKey(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("LexisLingo · DebugWordKey 字段批量增删")
        self.geometry("860x640")
        self.configure(bg="#f5f6fa")
        self.resizable(True, True)

        self._scale = 1.5
        self.tk.call("tk", "scaling", self._scale)

        self._all_words = {}
        self._db_path   = ""
        self._dirty     = False

        self._build_selector()
        self._build_main()
        self._bind_scroll_recursive(self)

    # ── Ctrl+滚轮 ────────────────────────────────────────
    def _bind_scroll_recursive(self, widget):
        widget.bind("<Control-MouseWheel>", self._on_scroll)
        for child in widget.winfo_children():
            self._bind_scroll_recursive(child)
    def _on_dclick(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        word = self._tree.item(sel[0], "values")[0]
        data = self._all_words.get(word, {})
        WordViewDialog(self, word, data)

    def _on_scroll(self, event):
        step = 0.1 if event.delta > 0 else -0.1
        self._scale = round(max(0.8, min(3.0, self._scale + step)), 1)
        self.tk.call("tk", "scaling", self._scale)
        self._status_var.set(f"缩放：{self._scale:.1f}x")
        return "break"

    # ── 顶部选择栏 ───────────────────────────────────────
    def _build_selector(self):
        frm = tk.Frame(self, bg="#2c3e50", pady=8)
        frm.pack(fill="x")

        tk.Label(frm, text="🔧 DebugWordKey",
                 bg="#2c3e50", fg="white",
                 font=("微软雅黑", 13, "bold")).pack(side="left", padx=14)

        tk.Label(frm, text="课程：", bg="#2c3e50",
                 fg="#ecf0f1").pack(side="left", padx=(16, 4))
        self._course_var = tk.StringVar()
        self._course_cb  = ttk.Combobox(frm, textvariable=self._course_var,
                                        width=16, state="readonly")
        self._course_cb.pack(side="left")
        self._course_cb.bind("<<ComboboxSelected>>", self._on_course_change)

        tk.Label(frm, text="用户：", bg="#2c3e50",
                 fg="#ecf0f1").pack(side="left", padx=(12, 4))
        self._user_var = tk.StringVar()
        self._user_cb  = ttk.Combobox(frm, textvariable=self._user_var,
                                      width=14, state="readonly")
        self._user_cb.pack(side="left")

        tk.Button(frm, text="📂 加载", bg="#27ae60", fg="white",
                  font=("微软雅黑", 9, "bold"),
                  command=self._load_db).pack(side="left", padx=10)

        self._btn_save = tk.Button(frm, text="💾 保存（自动备份）",
                                   bg="#e67e22", fg="white",
                                   font=("微软雅黑", 9, "bold"),
                                   command=self._save_db, state="disabled")
        self._btn_save.pack(side="left", padx=4)

        self._status_var = tk.StringVar(value="请选择课程和用户后点击【加载】")
        tk.Label(frm, textvariable=self._status_var,
                 bg="#2c3e50", fg="#f39c12",
                 font=("微软雅黑", 9)).pack(side="right", padx=14)

        self._refresh_courses_only()

    # ── 主体 ─────────────────────────────────────────────
    def _build_main(self):
        # 左：操作面板
        left = tk.Frame(self, bg="#f0f3f7", bd=0)
        left.pack(side="left", fill="y", padx=0, pady=0)

        tk.Label(left, text="操作面板",
                 bg="#dfe6e9", font=("微软雅黑", 10, "bold"),
                 pady=6, width=28).pack(fill="x")

        # ── 增加字段 ──────────────────────────────
        add_frame = tk.LabelFrame(left, text="➕  增加字段",
                                  font=("微软雅黑", 9, "bold"),
                                  bg="#f0f3f7", padx=10, pady=10)
        add_frame.pack(fill="x", padx=10, pady=(14, 6))

        tk.Label(add_frame, text="Key 名：",
                 bg="#f0f3f7").grid(row=0, column=0, sticky="w", pady=3)
        self._add_key = tk.Entry(add_frame, width=18)
        self._add_key.grid(row=0, column=1, pady=3)

        tk.Label(add_frame, text="类型：",
                 bg="#f0f3f7").grid(row=1, column=0, sticky="w", pady=3)
        self._add_type = ttk.Combobox(add_frame, width=16, state="readonly",
                                      values=["str", "int", "float", "bool"])
        self._add_type.current(0)
        self._add_type.grid(row=1, column=1, pady=3)

        tk.Label(add_frame, text="默认值：",
                 bg="#f0f3f7").grid(row=2, column=0, sticky="w", pady=3)
        self._add_val = tk.Entry(add_frame, width=18)
        self._add_val.grid(row=2, column=1, pady=3)

        tk.Button(add_frame, text="预览并执行",
                  bg="#3498db", fg="white",
                  font=("微软雅黑", 9, "bold"),
                  command=self._do_add).grid(row=3, column=0, columnspan=2,
                                             pady=(8, 0), sticky="ew")

        # ── 删除字段 ──────────────────────────────
        del_frame = tk.LabelFrame(left, text="🗑️  删除字段",
                                  font=("微软雅黑", 9, "bold"),
                                  bg="#f0f3f7", padx=10, pady=10)
        del_frame.pack(fill="x", padx=10, pady=6)

        tk.Label(del_frame, text="Key 名：",
                 bg="#f0f3f7").grid(row=0, column=0, sticky="w", pady=3)
        self._del_key = tk.Entry(del_frame, width=18)
        self._del_key.grid(row=0, column=1, pady=3)

        tk.Button(del_frame, text="预览并执行",
                  bg="#e74c3c", fg="white",
                  font=("微软雅黑", 9, "bold"),
                  command=self._do_del).grid(row=1, column=0, columnspan=2,
                                             pady=(8, 0), sticky="ew")

        # ── 操作日志 ──────────────────────────────
        tk.Label(left, text="操作日志",
                 bg="#dfe6e9", font=("微软雅黑", 9, "bold"),
                 pady=4).pack(fill="x", pady=(14, 0))
        self._log = tk.Text(left, height=12, width=30,
                            font=("Consolas", 9),
                            state="disabled", bg="#1e272e", fg="#dfe6e9",
                            relief="flat")
        self._log.pack(fill="both", expand=True, padx=0, pady=0)

        # 右：单词预览表
        right = tk.Frame(self, bg="#f5f6fa")
        right.pack(side="left", fill="both", expand=True)

        tk.Label(right, text="单词列表（加载后显示，操作后实时更新）",
                 bg="#dfe6e9", font=("微软雅黑", 10, "bold"),
                 pady=4).pack(fill="x")

        cols = ("单词", "字段数", "字段列表（前5个key）")
        self._tree = ttk.Treeview(right, columns=cols,
                                  show="headings", selectmode="browse")
        self._tree.heading("单词",   text="单词")
        self._tree.heading("字段数", text="字段数")
        self._tree.heading("字段列表（前5个key）", text="字段列表（前5个key）")
        self._tree.column("单词",   width=140, anchor="w")
        self._tree.column("字段数", width=60,  anchor="center")
        self._tree.column("字段列表（前5个key）", width=420, anchor="w")

        vsb = ttk.Scrollbar(right, orient="vertical",
                            command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree.pack(fill="both", expand=True)
        self._tree.bind("<Double-1>", self._on_dclick)
        tk.Label(right,
                 text="💡 保存时自动备份原数据库为 .db.copy，恢复时去掉 .copy 后缀即可",
                 fg="#7f8c8d", font=("微软雅黑", 8),
                 bg="#f5f6fa").pack(anchor="w", padx=6, pady=2)

    # ── 扫描目录 ─────────────────────────────────────────
    def _refresh_courses_only(self):
        data_root = "Data"
        courses = ([d for d in os.listdir(data_root)
                    if os.path.isdir(os.path.join(data_root, d))]
                   if os.path.exists(data_root) else [])
        self._course_cb["values"] = courses
        if courses:
            self._course_cb.current(0)

    def _refresh_users(self):
        course = self._course_var.get()
        udir   = f"Data/{course}/UserConfig"
        users  = ([f[:-6] for f in os.listdir(udir)
                   if f.endswith("_ld.db")]
                  if os.path.exists(udir) else [])
        self._user_cb["values"] = users
        if users:
            self._user_cb.current(0)

    def _on_course_change(self, *_):
        self._refresh_users()

    # ── 加载 ─────────────────────────────────────────────
    def _load_db(self):
        course = self._course_var.get()
        user   = self._user_var.get()
        if not course or not user:
            messagebox.showwarning("提示", "请先选择课程和用户")
            return
        self._db_path = _build_db_path(course, user)
        if not os.path.exists(self._db_path):
            messagebox.showerror("错误", f"数据库不存在：\n{self._db_path}")
            return
        try:
            self._all_words = _load_all(self._db_path, KEY_LABEL["UserData"])
        except Exception as e:
            messagebox.showerror("读取失败", str(e))
            return

        self._dirty = False
        self._btn_save.config(state="disabled")
        self._status_var.set(f"已加载：{course}/{user}  共 {len(self._all_words)} 词")
        self._render_table()
        self._log_write(f"[加载] {course}/{user}，共 {len(self._all_words)} 词")
        self._bind_scroll_recursive(self)

    # ── 渲染表格 ─────────────────────────────────────────
    def _render_table(self):
        self._tree.delete(*self._tree.get_children())
        for word, data in self._all_words.items():
            keys_preview = "、".join(list(data.keys())[:5])
            if len(data) > 5:
                keys_preview += "…"
            self._tree.insert("", "end",
                              values=(word, len(data), keys_preview))

    # ── 增加字段 ─────────────────────────────────────────
    def _do_add(self):
        if not self._all_words:
            messagebox.showwarning("提示", "请先加载数据库")
            return

        key      = self._add_key.get().strip()
        type_str = self._add_type.get()
        raw_val  = self._add_val.get().strip()

        if not key:
            messagebox.showwarning("提示", "Key 名不能为空")
            return
        if not raw_val:
            messagebox.showwarning("提示", "默认值不能为空")
            return

        try:
            val = _cast_value(raw_val, type_str)
        except Exception as e:
            messagebox.showerror("类型错误", f"默认值无法转换为 {type_str}：{e}")
            return

        # 统计影响范围
        will_add    = sum(1 for d in self._all_words.values() if key not in d)
        will_skip   = len(self._all_words) - will_add

        ans = messagebox.askyesno(
            "预览确认",
            f"Key：{key}\n类型：{type_str}\n默认值：{val}\n\n"
            f"将新增：{will_add} 个词\n已有此Key（跳过）：{will_skip} 个词\n\n确认执行？"
        )
        if not ans:
            return

        for data in self._all_words.values():
            if key not in data:
                data[key] = val

        self._dirty = True
        self._btn_save.config(state="normal")
        self._render_table()
        self._log_write(f"[增加] key={key}  type={type_str}  val={val}  影响{will_add}词")
        self._status_var.set(f"✅ 已给 {will_add} 个词新增字段 [{key}]，记得保存")

    # ── 删除字段 ─────────────────────────────────────────
    def _do_del(self):
        if not self._all_words:
            messagebox.showwarning("提示", "请先加载数据库")
            return

        key = self._del_key.get().strip()
        if not key:
            messagebox.showwarning("提示", "Key 名不能为空")
            return

        will_del  = sum(1 for d in self._all_words.values() if key in d)
        will_skip = len(self._all_words) - will_del

        if will_del == 0:
            messagebox.showinfo("提示", f"没有任何词包含字段 [{key}]，无需操作")
            return

        ans = messagebox.askyesno(
            "预览确认",
            f"Key：{key}\n\n"
            f"将删除：{will_del} 个词的此字段\n不含此Key（跳过）：{will_skip} 个词\n\n"
            f"⚠️ 删除后无法通过此工具恢复，确认执行？",
            icon="warning"
        )
        if not ans:
            return

        for data in self._all_words.values():
            data.pop(key, None)

        self._dirty = True
        self._btn_save.config(state="normal")
        self._render_table()
        self._log_write(f"[删除] key={key}  影响{will_del}词")
        self._status_var.set(f"🗑️ 已从 {will_del} 个词中删除字段 [{key}]，记得保存")

    # ── 保存 ─────────────────────────────────────────────
    def _save_db(self):
        if not self._db_path:
            return
        ans = messagebox.askyesno(
            "确认保存",
            f"将把 {len(self._all_words)} 条记录写回数据库。\n"
            f"原数据库将备份为：\n{self._db_path}.copy\n\n确定？"
        )
        if not ans:
            return
        try:
            _save_all(self._db_path, self._all_words, KEY_LABEL["UserData"])
        except Exception as e:
            messagebox.showerror("保存失败", str(e))
            return

        self._dirty = False
        self._btn_save.config(state="disabled")
        self._log_write(f"[保存] 写回 {len(self._all_words)} 词，备份至 .db.copy")
        self._status_var.set("✅ 保存成功，原数据已备份为 .db.copy")

    # ── 日志 ─────────────────────────────────────────────
    def _log_write(self, msg: str):
        self._log.config(state="normal")
        self._log.insert("end", msg + "\n")
        self._log.see("end")
        self._log.config(state="disabled")

    # ── 关闭 ─────────────────────────────────────────────
    def _on_close(self):
        if self._dirty:
            if not messagebox.askyesno("未保存",
                    "有未保存的修改，确定退出吗？（修改将丢失）"):
                return
        self.destroy()


# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = DebugWordKey()
    app.protocol("WM_DELETE_WINDOW", app._on_close)
    app.mainloop()
