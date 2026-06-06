# ============================================================
# #LexisLingo调试工具 - 单词的删改
# LexisLingo 单词数据库可视化调试器（tkinter）
# 方案A：读入内存 → 修改内存 → 手动保存写回
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
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from _Enviro import EndeCrypt
from Config  import KEY_LABEL, DIC_LABEL, _WOP

# ── 模板和反查表 ─────────────────────────────────────────────
WORD_TEMPLATE = DIC_LABEL["wordPorp"]
_WOP_REV      = {v: k for k, v in _WOP.items()}

FIELD_DESC = {
    "ET": "暴露次数",      "TT": "考试次数",
    "RT": "成功复习次数",  "WT": "总错误次数",
    "LW": "上次错误时间",  "TS": "翻译大表",
    "TL": "翻译抽取次数",  "PM": "补充信息/音标",
    "LR": "上次复习时间",  "SG": "掌握分数",
    "RC": "修正分数",      "IC": "出现课程",
    "FS": "首次出现时间",  "FC": "首次出现课程",
    "IM": "是否已掌握",    "WH": "错误历史",
    "II": "用户标记重要",
}
TS_FIELDS = ("LW", "LR", "FS")


# ══════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════
def _encode(val: dict, key: str) -> str:
    return EndeCrypt(json.dumps(val, ensure_ascii=False), key)

def _decode(blob: str, key: str) -> dict:
    return json.loads(EndeCrypt(blob, key, decode=True))

def _fmt_ts(ts) -> str:
    try:
        if ts and int(ts) > 100000:
            return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass
    return str(ts)

def _type_label(val) -> str:
    if isinstance(val, bool):  return "bool"
    if isinstance(val, int):   return "int"
    if isinstance(val, float): return "float"
    if isinstance(val, str):   return "str"
    if isinstance(val, list):  return "list"
    if isinstance(val, dict):  return "dict"
    return type(val).__name__

def _display_val(abbr: str, val) -> str:
    if abbr in TS_FIELDS:
        return _fmt_ts(val)
    if isinstance(val, (dict, list)):
        s = json.dumps(val, ensure_ascii=False)
        return (s[:80] + "…") if len(s) > 80 else s
    return str(val)

def _build_db_path(course: str, user: str) -> str:
    return f"Data/{course}/UserConfig/{user}_ld.db"

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
    """批量写回：BEGIN → DELETE ALL → INSERT ALL → COMMIT"""
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


# ══════════════════════════════════════════════════════════════
# 字段编辑弹窗（复用 debug_visual 风格）
# ══════════════════════════════════════════════════════════════
class FieldEditDialog(tk.Toplevel):

    def __init__(self, parent, abbr: str, current_val, tpl_val, on_save):
        super().__init__(parent)
        self.title(f"编辑字段：{abbr}  ({_WOP_REV.get(abbr, '')})")
        self.resizable(False, False)
        self.grab_set()
        self._abbr    = abbr
        self._tpl_type = _type_label(tpl_val)
        self._on_save  = on_save

        desc = FIELD_DESC.get(abbr, "")
        tk.Label(self, text=f"{abbr}  —  {_WOP_REV.get(abbr, '')}",
                 font=("微软雅黑", 12, "bold"), anchor="w"
                 ).pack(fill="x", padx=16, pady=(14, 2))
        tk.Label(self, text=f"说明：{desc}", fg="#555",
                 anchor="w").pack(fill="x", padx=16)
        tk.Label(self, text=f"模板类型：{self._tpl_type}",
                 fg="#0074D9", anchor="w").pack(fill="x", padx=16, pady=(0, 8))
        ttk.Separator(self).pack(fill="x", padx=8)

        if self._tpl_type == "bool":
            self._var = tk.BooleanVar(value=bool(current_val))
            frm = tk.Frame(self); frm.pack(padx=16, pady=10, fill="x")
            tk.Radiobutton(frm, text="True",  variable=self._var,
                           value=True).pack(side="left", padx=10)
            tk.Radiobutton(frm, text="False", variable=self._var,
                           value=False).pack(side="left", padx=10)
            self._get_val = lambda: self._var.get()

        elif self._tpl_type in ("list", "dict"):
            tk.Label(self, text="以 JSON 格式编辑：",
                     anchor="w", fg="#555").pack(fill="x", padx=16)
            self._text = tk.Text(self, height=10, width=52,
                                 font=("Consolas", 11))
            self._text.insert("1.0", json.dumps(
                current_val, ensure_ascii=False, indent=2))
            self._text.pack(padx=16, pady=6)
            self._get_val = self._parse_json

        else:
            tk.Label(self, text="新值：", anchor="w",
                     fg="#555").pack(fill="x", padx=16)
            self._entry = tk.Entry(self, font=("微软雅黑", 12), width=36)
            self._entry.insert(0, str(current_val))
            self._entry.pack(padx=16, pady=6)
            self._entry.focus_set()
            self._entry.bind("<Return>", lambda e: self._save())
            self._get_val = self._parse_scalar

        ttk.Separator(self).pack(fill="x", padx=8, pady=(4, 0))
        btn_frm = tk.Frame(self); btn_frm.pack(pady=10)
        tk.Button(btn_frm, text="✅ 保存", width=10,
                  bg="#2ecc71", fg="white",
                  font=("微软雅黑", 10, "bold"),
                  command=self._save).pack(side="left", padx=8)
        tk.Button(btn_frm, text="取消", width=10,
                  command=self.destroy).pack(side="left", padx=8)
        self._center()

    def _center(self):
        self.update_idletasks()
        pw = self.master.winfo_rootx() + self.master.winfo_width()  // 2
        ph = self.master.winfo_rooty() + self.master.winfo_height() // 2
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{pw - w//2}+{ph - h//2}")

    def _parse_json(self):
        raw = self._text.get("1.0", "end").strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            messagebox.showerror("JSON 格式错误", str(e), parent=self)
            return None

    def _parse_scalar(self):
        raw = self._entry.get().strip()
        try:
            if self._tpl_type == "int":   return int(raw)
            if self._tpl_type == "float": return float(raw)
            return raw
        except ValueError as e:
            messagebox.showerror("类型错误",
                f"期望 {self._tpl_type}，无法转换：{e}", parent=self)
            return None

    def _save(self):
        val = self._get_val()
        if val is None:
            return
        self._on_save(self._abbr, val)
        self.destroy()


# ══════════════════════════════════════════════════════════════
# 单词详情 / 编辑弹窗
# ══════════════════════════════════════════════════════════════
class WordDetailDialog(tk.Toplevel):
    """双击单词：查看全字段 + 双击字段可编辑（改内存，主窗口统一保存）"""

    def __init__(self, parent, word: str, data: dict, on_field_change=None):
        super().__init__(parent)
        self.title(f"单词详情：{word}")
        self.geometry("600x560")
        self.resizable(True, True)
        self.grab_set()
        self._word    = word
        self._data    = data          # 直接引用主窗口内存（修改即生效到内存）
        self._on_change = on_field_change  # 通知主窗口刷新

        tk.Label(self, text=word,
                 font=("微软雅黑", 16, "bold"), fg="#2c3e50"
                 ).pack(pady=(14, 2))
        tk.Label(self, text="双击字段可编辑（修改存内存，回主窗口点保存才写库）",
                 fg="#e17055", font=("微软雅黑", 8)).pack()

        ttk.Separator(self).pack(fill="x", padx=10, pady=6)

        cols = ("缩写", "全名", "说明", "类型", "值", "状态")
        self._tree = ttk.Treeview(self, columns=cols, show="headings",
                                  selectmode="browse")
        widths = (40, 120, 100, 45, 190, 50)
        for col, w in zip(cols, widths):
            self._tree.heading(col, text=col)
            self._tree.column(col, width=w, anchor="w")

        self._tree.tag_configure("missing",  background="#ffeaa7",
                                 foreground="#d35400")
        self._tree.tag_configure("normal",   background="#ffffff")
        self._tree.tag_configure("modified", background="#d5f5e3")

        vsb = ttk.Scrollbar(self, orient="vertical",
                            command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y", padx=(0, 6))
        self._tree.pack(fill="both", expand=True, padx=6)
        self._tree.bind("<Double-1>", self._on_dclick)

        tk.Label(self, text="💡 双击字段可编辑",
                 fg="#7f8c8d", font=("微软雅黑", 8)).pack(anchor="w", padx=8)

        tk.Button(self, text="关闭", command=self.destroy,
                  bg="#dfe6e9", font=("微软雅黑", 10),
                  width=10).pack(pady=8)

        self._render()

    def _render(self):
        self._tree.delete(*self._tree.get_children())
        for abbr, tpl_val in WORD_TEMPLATE.items():
            full = _WOP_REV.get(abbr, abbr)
            desc = FIELD_DESC.get(abbr, "")
            if abbr in self._data:
                val     = self._data[abbr]
                display = _display_val(abbr, val)
                tag     = "normal"
                status  = "正常"
            else:
                val     = tpl_val
                display = f"[缺失] 默认={tpl_val}"
                tag     = "missing"
                status  = "缺失"
            self._tree.insert("", "end", iid=abbr,
                              values=(abbr, full, desc,
                                      _type_label(val), display, status),
                              tags=(tag,))

    def _on_dclick(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        abbr     = sel[0]
        row_vals = self._tree.item(abbr, "values")
        status   = row_vals[5]

        if status == "缺失":
            ans = messagebox.askyesno(
                "字段缺失",
                f"字段 [{abbr}] 不存在，是否用模板默认值修复？")
            if not ans:
                return
            self._data[abbr] = WORD_TEMPLATE[abbr]
            self._notify_change()
            self._render()
            return

        tpl_val = WORD_TEMPLATE.get(abbr, self._data[abbr])
        cur_val = self._data[abbr]

        def on_save(key, new_val):
            self._data[key] = new_val
            self._notify_change()
            self._render()

        FieldEditDialog(self, abbr, cur_val, tpl_val, on_save)

    def _notify_change(self):
        if self._on_change:
            self._on_change(self._word)


# ══════════════════════════════════════════════════════════════
# 主窗口
# ══════════════════════════════════════════════════════════════
class WordDbVisual(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("LexisLingo 单词数据库调试器")
        self.geometry("1100x700")
        self.configure(bg="#f5f6fa")
        self.resizable(True, True)

        self._scale      = 1.5
        self.tk.call("tk", "scaling", self._scale)

        self._all_words   = {}    # word -> dict（内存副本）
        self._shown_words = []
        self._db_path     = ""
        self._dirty       = False  # 是否有未保存修改
        self._modified_words = set()  # 记录哪些词被改过

        self._build_selector()
        self._build_main()
        self._bind_scroll_recursive(self)

    # ── Ctrl+滚轮 ────────────────────────────────────────
    def _bind_scroll_recursive(self, widget):
        widget.bind("<Control-MouseWheel>", self._on_scroll)
        for child in widget.winfo_children():
            self._bind_scroll_recursive(child)

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

        tk.Label(frm, text="📖 LexisLingo 单词DB",
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
                  command=self._load_db).pack(side="left", padx=8)

        # 保存按钮
        self._btn_save = tk.Button(frm, text="💾 保存到数据库",
                                   bg="#e67e22", fg="white",
                                   font=("微软雅黑", 9, "bold"),
                                   command=self._save_db, state="disabled")
        self._btn_save.pack(side="left", padx=4)

        # 放弃修改
        self._btn_discard = tk.Button(frm, text="↩ 放弃修改",
                                      bg="#636e72", fg="white",
                                      font=("微软雅黑", 9, "bold"),
                                      command=self._discard_changes,
                                      state="disabled")
        self._btn_discard.pack(side="left", padx=4)

        # 搜索
        tk.Label(frm, text="搜索：", bg="#2c3e50",
                 fg="#ecf0f1").pack(side="left", padx=(12, 4))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search)
        tk.Entry(frm, textvariable=self._search_var,
                 width=16, font=("微软雅黑", 10)).pack(side="left")

        # 过滤
        self._filter_var = tk.StringVar(value="全部")
        for label in ("全部", "已掌握", "重要", "有错误", "已修改"):
            tk.Radiobutton(frm, text=label, variable=self._filter_var,
                           value=label, bg="#2c3e50", fg="white",
                           selectcolor="#34495e", activebackground="#2c3e50",
                           command=self._apply_filter
                           ).pack(side="left", padx=3)

        self._status_var = tk.StringVar(value="请选择课程和用户后点击【加载】")
        tk.Label(frm, textvariable=self._status_var,
                 bg="#2c3e50", fg="#f39c12",
                 font=("微软雅黑", 9)).pack(side="right", padx=14)

        self._refresh_courses_only()

    # ── 主体 ─────────────────────────────────────────────
    def _build_main(self):
        paned = tk.PanedWindow(self, orient="horizontal",
                               bg="#dfe6e9", sashwidth=5)
        paned.pack(fill="both", expand=True, padx=6, pady=6)

        left = tk.Frame(paned, bg="#f5f6fa")
        paned.add(left, minsize=700)

        tk.Label(left, text="单词列表（双击查看/编辑字段，绿色=已修改未保存）",
                 bg="#dfe6e9", font=("微软雅黑", 10, "bold"),
                 pady=4).pack(fill="x")

        cols = ("单词", "暴露ET", "分数SG", "掌握IM", "重要II",
                "复习RT", "错误WT", "首次课程FC", "上次复习LR")
        self._tree = ttk.Treeview(left, columns=cols,
                                  show="headings", selectmode="browse")
        col_widths = (140, 65, 65, 60, 60, 60, 60, 160, 130)
        for col, w in zip(cols, col_widths):
            self._tree.heading(col, text=col,
                               command=lambda c=col: self._sort_by(c))
            self._tree.column(col, width=w, anchor="w")

        self._tree.tag_configure("mastered",  background="#dff9fb")
        self._tree.tag_configure("important", background="#fff3cd")
        self._tree.tag_configure("wrong",     background="#ffeaa7")
        self._tree.tag_configure("modified",  background="#d5f5e3")
        self._tree.tag_configure("normal",    background="#ffffff")

        vsb = ttk.Scrollbar(left, orient="vertical",
                            command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree.pack(fill="both", expand=True)
        self._tree.bind("<Double-1>", self._on_dclick)
        self._tree.bind("<Button-3>", self._on_right_click)

        # 右键菜单
        self._ctx_menu = tk.Menu(self, tearoff=0)
        self._ctx_menu.add_command(label="🔍 查看/编辑字段",
                                   command=self._ctx_detail)
        self._ctx_menu.add_separator()
        self._ctx_menu.add_command(label="🗑️  删除此单词（内存）",
                                   foreground="red",
                                   command=self._ctx_delete)
        self._right_click_word = ""

        tk.Label(left,
                 text="💡 双击查看详情并编辑字段 | 右键删除 | 绿色=已修改 | 记得点保存",
                 fg="#7f8c8d", font=("微软雅黑", 8),
                 bg="#f5f6fa").pack(anchor="w", padx=6, pady=2)

        # 右：统计
        right = tk.Frame(paned, bg="#f5f6fa")
        paned.add(right, minsize=200)

        tk.Label(right, text="数据库统计",
                 bg="#dfe6e9", font=("微软雅黑", 10, "bold"),
                 pady=4).pack(fill="x")

        self._stat_text = tk.Text(right, font=("微软雅黑", 10),
                                  state="disabled", wrap="word",
                                  bg="#f9f9f9", relief="flat",
                                  padx=10, pady=10)
        self._stat_text.pack(fill="both", expand=True)

        self._sort_col = None
        self._sort_asc = True

    # ── 扫描 ─────────────────────────────────────────────
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
        if self._dirty:
            ans = messagebox.askyesno("未保存的修改",
                "有未保存的修改，重新加载会丢失，继续吗？")
            if not ans:
                return

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

        self._dirty          = False
        self._modified_words = set()
        self._btn_save.config(state="disabled")
        self._btn_discard.config(state="disabled")
        self._status_var.set(
            f"已加载：{course}/{user}  共 {len(self._all_words)} 词")
        self._apply_filter()
        self._render_stats()
        self._bind_scroll_recursive(self)

    # ── 保存 ─────────────────────────────────────────────
    def _save_db(self):
        if not self._db_path:
            return
        ans = messagebox.askyesno(
            "确认保存",
            f"将把内存中 {len(self._all_words)} 条记录全部写回数据库。\n"
            f"（共修改了 {len(self._modified_words)} 个单词）\n\n确定？")
        if not ans:
            return
        try:
            _save_all(self._db_path, self._all_words, KEY_LABEL["UserData"])
        except Exception as e:
            messagebox.showerror("保存失败", str(e))
            return

        self._dirty          = False
        self._modified_words = set()
        self._btn_save.config(state="disabled")
        self._btn_discard.config(state="disabled")
        self._apply_filter()
        self._status_var.set("✅ 保存成功")

    # ── 放弃修改 ─────────────────────────────────────────
    def _discard_changes(self):
        if not messagebox.askyesno("放弃修改",
                "放弃所有未保存的修改，重新从数据库加载？"):
            return
        self._load_db()

    # ── 某个词被改了（详情窗回调）────────────────────────
    def _on_word_modified(self, word: str):
        self._dirty = True
        self._modified_words.add(word)
        self._btn_save.config(state="normal")
        self._btn_discard.config(state="normal")
        self._status_var.set(
            f"✏️ 已修改 {len(self._modified_words)} 个单词，记得保存")
        # 刷新这一行的显示
        self._refresh_row(word)
        self._render_stats()

    def _refresh_row(self, word: str):
        if word not in self._tree.get_children() and \
           word not in self._shown_words:
            return
        data = self._all_words.get(word, {})
        et   = data.get(_WOP["exposeTimes"], 0)
        sg   = data.get(_WOP["Score"],       0)
        im   = "✅" if data.get(_WOP["IsMastered"], False) else ""
        ii   = "⭐" if data.get(_WOP["Important"],  False) else ""
        rt   = data.get(_WOP["ReviewTimes"], 0)
        wt   = data.get(_WOP["WrongTimes"],  0)
        fc   = data.get(_WOP["FirstCourseAt"], "")
        lr   = _fmt_ts(data.get(_WOP["LastReviewTime"], 0))
        tag  = "modified"  # 绿色标记已修改
        try:
            self._tree.item(word, values=(word, et, sg, im, ii, rt, wt, fc, lr),
                            tags=(tag,))
        except tk.TclError:
            pass

    # ── 过滤 ─────────────────────────────────────────────
    def _on_search(self, *_):
        self._apply_filter()

    def _apply_filter(self):
        keyword = self._search_var.get().strip().lower()
        flt     = self._filter_var.get()
        result  = []
        for word, data in self._all_words.items():
            if keyword and keyword not in word.lower():
                continue
            if flt == "已掌握" and not data.get(_WOP["IsMastered"], False):
                continue
            if flt == "重要"   and not data.get(_WOP["Important"],   False):
                continue
            if flt == "有错误" and data.get(_WOP["WrongTimes"], 0) == 0:
                continue
            if flt == "已修改" and word not in self._modified_words:
                continue
            result.append(word)
        self._shown_words = result
        self._render_table(result)

    # ── 渲染主表 ─────────────────────────────────────────
    def _render_table(self, words: list):
        self._tree.delete(*self._tree.get_children())
        for word in words:
            data = self._all_words.get(word, {})
            et   = data.get(_WOP["exposeTimes"], 0)
            sg   = data.get(_WOP["Score"],       0)
            im   = "✅" if data.get(_WOP["IsMastered"], False) else ""
            ii   = "⭐" if data.get(_WOP["Important"],  False) else ""
            rt   = data.get(_WOP["ReviewTimes"], 0)
            wt   = data.get(_WOP["WrongTimes"],  0)
            fc   = data.get(_WOP["FirstCourseAt"], "")
            lr   = _fmt_ts(data.get(_WOP["LastReviewTime"], 0))

            if word in self._modified_words:
                tag = "modified"
            elif im:
                tag = "mastered"
            elif ii:
                tag = "important"
            elif wt and int(wt) > 0:
                tag = "wrong"
            else:
                tag = "normal"

            self._tree.insert("", "end", iid=word,
                              values=(word, et, sg, im, ii, rt, wt, fc, lr),
                              tags=(tag,))

    # ── 排序 ─────────────────────────────────────────────
    _COL_KEY = {
        "暴露ET": _WOP["exposeTimes"],
        "分数SG": _WOP["Score"],
        "复习RT": _WOP["ReviewTimes"],
        "错误WT": _WOP["WrongTimes"],
    }

    def _sort_by(self, col: str):
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        key = self._COL_KEY.get(col)
        if key:
            self._shown_words.sort(
                key=lambda w: self._all_words.get(w, {}).get(key, 0),
                reverse=not self._sort_asc)
        else:
            self._shown_words.sort(reverse=not self._sort_asc)
        self._render_table(self._shown_words)

    # ── 统计 ─────────────────────────────────────────────
    def _render_stats(self):
        total = len(self._all_words)
        if not total:
            return
        mastered   = sum(1 for d in self._all_words.values()
                         if d.get(_WOP["IsMastered"], False))
        important  = sum(1 for d in self._all_words.values()
                         if d.get(_WOP["Important"], False))
        with_error = sum(1 for d in self._all_words.values()
                         if d.get(_WOP["WrongTimes"], 0) > 0)
        avg_score  = sum(d.get(_WOP["Score"], 0)
                         for d in self._all_words.values()) / total
        avg_expose = sum(d.get(_WOP["exposeTimes"], 0)
                         for d in self._all_words.values()) / total

        text = (
            f"总词数：{total}\n\n"
            f"已掌握：{mastered}\n"
            f"  占比：{mastered/total*100:.1f}%\n\n"
            f"标记重要：{important}\n\n"
            f"有错误：{with_error}\n\n"
            f"平均掌握分：{avg_score:.2f}\n\n"
            f"平均暴露度：{avg_expose:.2f}\n\n"
            f"待保存修改：{len(self._modified_words)} 词\n\n"
            f"路径：\n{self._db_path}"
        )
        self._stat_text.config(state="normal")
        self._stat_text.delete("1.0", "end")
        self._stat_text.insert("1.0", text)
        self._stat_text.config(state="disabled")

    # ── 双击 ─────────────────────────────────────────────
    def _on_dclick(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        word = sel[0]
        data = self._all_words.get(word, {})
        WordDetailDialog(self, word, data,
                         on_field_change=self._on_word_modified)

    # ── 右键 ─────────────────────────────────────────────
    def _on_right_click(self, event):
        row = self._tree.identify_row(event.y)
        if not row:
            return
        self._tree.selection_set(row)
        self._right_click_word = row
        self._ctx_menu.post(event.x_root, event.y_root)

    def _ctx_detail(self):
        word = self._right_click_word
        if word:
            WordDetailDialog(self, word, self._all_words.get(word, {}),
                             on_field_change=self._on_word_modified)

    def _ctx_delete(self):
        word = self._right_click_word
        if not word:
            return
        if not messagebox.askyesno("删除确认",
                f"从内存中删除单词：\n\n「{word}」\n\n"
                "（需要再点保存才真正写回数据库）"):
            return
        self._all_words.pop(word, None)
        self._modified_words.discard(word)
        if word in self._shown_words:
            self._shown_words.remove(word)
        try:
            self._tree.delete(word)
        except tk.TclError:
            pass
        self._dirty = True
        self._btn_save.config(state="normal")
        self._btn_discard.config(state="normal")
        self._render_stats()
        self._status_var.set(f"🗑️ 已从内存删除：{word}，记得保存")

    # ── 关闭 ─────────────────────────────────────────────
    def _on_close(self):
        if self._dirty:
            ans = messagebox.askyesno("未保存",
                "有未保存的修改，确定退出吗？（修改将丢失）")
            if not ans:
                return
        self.destroy()


# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = WordDbVisual()
    app.protocol("WM_DELETE_WINDOW", app._on_close)
    app.mainloop()
