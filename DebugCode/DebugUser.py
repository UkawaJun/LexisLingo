# ============================================================
# debug_visual.py
# LexisLingo 用户数据可视化调试器（tkinter）
# 放在和主程序同级目录下直接运行
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
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

# ── 从主程序导入，保证模板与主程序永远同步 ──────────────────
from _Enviro import EndeCrypt
from Config  import (
    KEY_LABEL,
    DIC_LABEL,
    _WOP,
    DEFAULT_VOICE_ID,
    DEFAULT_SPEED_RATE,
    Setting as SETTING_TEMPLATE,
)

USERCONFIG_TEMPLATE = DIC_LABEL["UserConfig"]

# ══════════════════════════════════════════════════════════════
# 加解密封装
# ══════════════════════════════════════════════════════════════
def _read_encrypted(filepath: str, key: str) -> dict:
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()
    dec = EndeCrypt(raw, key, decode=True)
    try:
        from json_repair import loads
        return loads(dec)
    except ImportError:
        return json.loads(dec)

def _write_encrypted(filepath: str, data: dict, key: str):
    text = json.dumps(data, ensure_ascii=False)
    enc  = EndeCrypt(text, key)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(enc)

# ══════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════
FIELD_DESC = {
    "name"            : "用户名",
    "isVip"           : "是否 VIP",
    "LearnCourse"     : "已学课程列表",
    "DailyDate"       : "打卡记录",
    "SetupTime"       : "建立时间戳",
    "PeferVoice"      : "偏好音色 ID",
    "PeferSpeed"      : "偏好语速",
    "LastLoginAt"     : "上次登录时间戳",
    "RegisterTime"    : "初次登陆时间戳",
    "CurrentCourse"   : "上次学习课程",
    "Nickname"        : "昵称",
    "Avatar"          : "头像",
    "Setting"         : "设置项（子字典）",
    "_v"              : "版本号",
    "MaxWordSound"    : "本地最大单词音频数",
    "MaxSentSound"    : "本地最大句子音频数",
    "LongestStreak"   : "最长连续打卡天数",
    "DailyGoalWords"  : "每日目标单词数",
    "DailyGoalMinutes": "每日目标学习时长(分)",
    "FontScale"       : "字体缩放比例",
    "TargetLang"      : "学习语言(EN/CN)",
}

def _type_label(val) -> str:
    if isinstance(val, bool):  return "bool"
    if isinstance(val, int):   return "int"
    if isinstance(val, float): return "float"
    if isinstance(val, str):   return "str"
    if isinstance(val, list):  return "list"
    if isinstance(val, dict):  return "dict"
    return type(val).__name__

def _fmt_ts(ts) -> str:
    try:
        if ts and int(ts) > 100000:
            return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return str(ts)

def _build_file_label(course_name: str, user_name: str) -> dict:
    cp = f"Data/{course_name}"
    ip = f"LoadFile/{course_name}"
    return {
        "CoursePath"    : cp,
        "ImportPath"    : ip,
        "Data"          : f"{cp}/LessonCore.json",
        "Data2"         : f"{cp}/LessonCore2.json",
        "_TargetPath"   : f"{ip}/{course_name}_Data.csv",
        "_TargetPath2"  : f"{ip}/{course_name}_WordList.csv",
        "_CoursePath2"  : ip,
        "Sound"         : f"{cp}/Sound",
        "SoundSentence" : f"{cp}/UserSound",
        "SoundIndex"    : f"{cp}/Sound/WordSIndex.json",
        "SentenceIndex" : f"{cp}/UserSound/SentenceIndex.json",
        "Video"         : f"{cp}/Video",
        "UserConfig"    : f"{cp}/UserConfig/",
        "Tree"          : f"{cp}/Tree.db",
        "CourseText"    : f"{cp}/Course.db",
        "wordFrequent"  : f"{cp}/Frequent.db",
        "Use1"          : f"{cp}/UserConfig/{user_name}.json",
        "Use2"          : f"{cp}/UserConfig/{user_name}_ld.db",
    }

def _collect_extra_keys(cfg: dict, template: dict, prefix: str = "") -> list:
    """递归收集 cfg 里有、但 template 里没有的 key，返回完整路径列表"""
    extras = []
    for k in cfg:
        full = f"{prefix}.{k}" if prefix else k
        if k not in template:
            extras.append(full)
        else:
            if isinstance(template[k], dict) and isinstance(cfg[k], dict):
                extras.extend(_collect_extra_keys(cfg[k], template[k], full))
    return extras


# ══════════════════════════════════════════════════════════════
# 编辑弹窗
# ══════════════════════════════════════════════════════════════
class EditDialog(tk.Toplevel):

    def __init__(self, parent, field_key: str, current_val, template_val, on_save):
        super().__init__(parent)
        self.title(f"编辑字段：{field_key}")
        self.resizable(False, False)
        self.grab_set()
        self.on_save   = on_save
        self.field_key = field_key
        self.tpl_type  = _type_label(template_val)

        desc = FIELD_DESC.get(field_key, "")
        tk.Label(self, text=f"字段：{field_key}",
                 font=("微软雅黑", 12, "bold"), anchor="w"
                 ).pack(fill="x", padx=16, pady=(14, 2))
        tk.Label(self, text=f"说明：{desc}", fg="#555",
                 anchor="w").pack(fill="x", padx=16)
        tk.Label(self, text=f"模板类型：{self.tpl_type}",
                 fg="#0074D9", anchor="w").pack(fill="x", padx=16, pady=(0, 8))
        ttk.Separator(self).pack(fill="x", padx=8)

        if self.tpl_type == "bool":
            self._var = tk.BooleanVar(value=bool(current_val))
            frm = tk.Frame(self); frm.pack(padx=16, pady=10, fill="x")
            tk.Radiobutton(frm, text="True",  variable=self._var,
                           value=True).pack(side="left", padx=10)
            tk.Radiobutton(frm, text="False", variable=self._var,
                           value=False).pack(side="left", padx=10)
            self._get_val = lambda: self._var.get()

        elif self.tpl_type in ("list", "dict"):
            tk.Label(self, text="以 JSON 格式编辑：",
                     anchor="w", fg="#555").pack(fill="x", padx=16)
            self._text = tk.Text(self, height=10, width=52,
                                 font=("Consolas", 11))
            self._text.insert("1.0", json.dumps(current_val,
                              ensure_ascii=False, indent=2))
            self._text.pack(padx=16, pady=6)
            self._get_val = self._parse_json

        else:
            tk.Label(self, text="新值：",
                     anchor="w", fg="#555").pack(fill="x", padx=16)
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
        tpl = self.tpl_type
        try:
            if tpl == "int":   return int(raw)
            if tpl == "float": return float(raw)
            return raw
        except ValueError as e:
            messagebox.showerror("类型错误",
                f"期望 {tpl}，无法转换：{e}", parent=self)
            return None

    def _save(self):
        val = self._get_val()
        if val is None:
            return
        self.on_save(self.field_key, val)
        self.destroy()


# ══════════════════════════════════════════════════════════════
# 主调试窗口
# ══════════════════════════════════════════════════════════════
class DebugVisual(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("LexisLingo 用户数据调试器")
        self.geometry("900x660")
        self.configure(bg="#f5f6fa")
        self.resizable(True, True)

        self._scale = 1.5
        self.tk.call("tk", "scaling", self._scale)

        self._cfg   = {}
        self._fl    = {}
        self._use1  = ""
        self._dirty = False

        self._build_selector()
        self._build_main_area()

        # 所有控件建好后统一绑定 Ctrl+滚轮
        self._bind_scroll_recursive(self)

    # ── Ctrl+滚轮缩放 ────────────────────────────────────
    def _bind_scroll_recursive(self, widget):
        widget.bind("<Control-MouseWheel>", self._on_ctrl_scroll)
        for child in widget.winfo_children():
            self._bind_scroll_recursive(child)

    def _on_ctrl_scroll(self, event):
        step = 0.1 if event.delta > 0 else -0.1
        self._scale = round(max(0.8, min(3.0, self._scale + step)), 1)
        self.tk.call("tk", "scaling", self._scale)
        self._status_var.set(f"缩放：{self._scale:.1f}x  （Ctrl+滚轮调整）")
        return "break"

    # ── 顶部选择栏 ───────────────────────────────────────
    def _build_selector(self):
        frm = tk.Frame(self, bg="#2c3e50", pady=8)
        frm.pack(fill="x")

        tk.Label(frm, text="🔍 LexisLingo 调试器",
                 bg="#2c3e50", fg="white",
                 font=("微软雅黑", 13, "bold")).pack(side="left", padx=14)

        tk.Label(frm, text="课程：",
                 bg="#2c3e50", fg="#ecf0f1").pack(side="left", padx=(20, 4))
        self._course_var = tk.StringVar()
        self._course_cb  = ttk.Combobox(frm, textvariable=self._course_var,
                                        width=16, state="readonly")
        self._course_cb.pack(side="left")
        self._course_cb.bind("<<ComboboxSelected>>", self._on_course_change)

        tk.Label(frm, text="用户：",
                 bg="#2c3e50", fg="#ecf0f1").pack(side="left", padx=(16, 4))
        self._user_var = tk.StringVar()
        self._user_cb  = ttk.Combobox(frm, textvariable=self._user_var,
                                      width=14, state="readonly")
        self._user_cb.pack(side="left")

        tk.Button(frm, text="📂 加载", bg="#27ae60", fg="white",
                  font=("微软雅黑", 9, "bold"),
                  command=self._load_data).pack(side="left", padx=12)

        self._btn_save = tk.Button(frm, text="💾 保存",
                                   bg="#e67e22", fg="white",
                                   font=("微软雅黑", 9, "bold"),
                                   command=self._save_data, state="disabled")
        self._btn_save.pack(side="left")

        self._status_var = tk.StringVar(value="请选择课程和用户后点击【加载】")
        tk.Label(frm, textvariable=self._status_var,
                 bg="#2c3e50", fg="#f39c12",
                 font=("微软雅黑", 9)).pack(side="right", padx=14)

        # _user_cb 已建好，现在可以安全刷新课程列表
        self._refresh_courses_only()

    # ── 主体区域 ─────────────────────────────────────────
    def _build_main_area(self):
        paned = tk.PanedWindow(self, orient="horizontal",
                               bg="#dfe6e9", sashwidth=5)
        paned.pack(fill="both", expand=True, padx=6, pady=6)

        # 左：字段列表
        left = tk.Frame(paned, bg="#f5f6fa")
        paned.add(left, minsize=520)

        tk.Label(left, text="UserConfig 字段",
                 bg="#dfe6e9", font=("微软雅黑", 10, "bold"),
                 pady=4).pack(fill="x")

        cols = ("字段", "说明", "类型", "当前值", "状态")
        self._tree = ttk.Treeview(left, columns=cols,
                                  show="headings", selectmode="browse")
        widths = (140, 150, 55, 220, 60)
        for col, w in zip(cols, widths):
            self._tree.heading(col, text=col)
            self._tree.column(col, width=w, anchor="w")

        self._tree.tag_configure("missing", background="#ffeaa7",
                                 foreground="#d35400")
        self._tree.tag_configure("normal",  background="#ffffff")
        self._tree.tag_configure("extra",   background="#dff9fb",
                                 foreground="#2d6a8a")

        vsb = ttk.Scrollbar(left, orient="vertical",
                            command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree.pack(fill="both", expand=True)
        self._tree.bind("<Double-1>", self._on_row_dclick)

        tk.Label(left,
                 text="💡 双击可编辑（黄=缺失可修复，蓝=模板已删除仅保留只读）",
                 fg="#7f8c8d", font=("微软雅黑", 8),
                 bg="#f5f6fa").pack(anchor="w", padx=6, pady=2)

        # 右：FILE_LABEL
        right = tk.Frame(paned, bg="#f5f6fa")
        paned.add(right, minsize=240)

        tk.Label(right, text="FILE_LABEL 路径",
                 bg="#dfe6e9", font=("微软雅黑", 10, "bold"),
                 pady=4).pack(fill="x")

        fl_cols = ("键", "存在", "路径")
        self._fl_tree = ttk.Treeview(right, columns=fl_cols,
                                     show="headings", selectmode="none")
        self._fl_tree.heading("键",   text="键")
        self._fl_tree.heading("存在", text="✅")
        self._fl_tree.heading("路径", text="路径")
        self._fl_tree.column("键",   width=110, anchor="w")
        self._fl_tree.column("存在", width=30,  anchor="center")
        self._fl_tree.column("路径", width=260, anchor="w")
        self._fl_tree.tag_configure("ok",  background="#dff9fb")
        self._fl_tree.tag_configure("bad", background="#ffeaa7")

        fl_vsb = ttk.Scrollbar(right, orient="vertical",
                               command=self._fl_tree.yview)
        self._fl_tree.configure(yscrollcommand=fl_vsb.set)
        fl_vsb.pack(side="right", fill="y")
        self._fl_tree.pack(fill="both", expand=True)

    # ── 课程 / 用户扫描 ──────────────────────────────────
    def _refresh_courses_only(self):
        data_root = "Data"
        if os.path.exists(data_root):
            courses = [d for d in os.listdir(data_root)
                       if os.path.isdir(os.path.join(data_root, d))]
        else:
            courses = []
        self._course_cb["values"] = courses
        if courses:
            self._course_cb.current(0)

    def _refresh_users(self):
        course = self._course_var.get()
        udir   = f"Data/{course}/UserConfig"
        if os.path.exists(udir):
            users = [f[:-5] for f in os.listdir(udir)
                     if f.endswith(".json") and not f.endswith("_ld.json")]
        else:
            users = []
        self._user_cb["values"] = users
        if users:
            self._user_cb.current(0)

    def _on_course_change(self, *_):
        self._refresh_users()

    # ── 加载 ─────────────────────────────────────────────
    def _load_data(self):
        course = self._course_var.get()
        user   = self._user_var.get()
        if not course or not user:
            messagebox.showwarning("提示", "请先选择课程和用户")
            return

        self._fl    = _build_file_label(course, user)
        self._use1  = self._fl["Use1"]
        self._dirty = False
        self._btn_save.config(state="disabled")

        if not os.path.exists(self._use1):
            messagebox.showerror("错误", f"用户文件不存在：\n{self._use1}")
            return
        try:
            self._cfg = _read_encrypted(self._use1, KEY_LABEL["UserData"])
        except Exception as e:
            messagebox.showerror("读取失败", str(e))
            return

        self._status_var.set(f"已加载：{course} / {user}")
        self._render_fields()
        self._render_fl()
        self._bind_scroll_recursive(self)

    # ── 渲染字段表 ───────────────────────────────────────
    def _render_fields(self):
        self._tree.delete(*self._tree.get_children())

        # ① 模板 key（正常 / 缺失）
        def _add_template_row(key, tpl_val, actual_dict,
                              parent_key=None, iid_prefix=""):
            full_key = f"{parent_key}.{key}" if parent_key else key
            iid      = iid_prefix + full_key
            desc     = FIELD_DESC.get(key, "")
            tpl_type = _type_label(tpl_val)

            if key in actual_dict:
                cur_val = actual_dict[key]
                if key in ("LastLoginAt", "SetupTime", "LastWrong",
                           "LastReviewTime", "FirstSeenAt", "RegisterTime") \
                        and isinstance(cur_val, (int, float)):
                    display = _fmt_ts(cur_val)
                elif isinstance(cur_val, (dict, list)):
                    s = str(cur_val)
                    display = (f"[{_type_label(cur_val)}] {s[:60]}…"
                               if len(s) > 60 else s)
                else:
                    display = str(cur_val)
                status = "正常"
                tag    = "normal"
            else:
                display = "—"
                status  = "缺失"
                tag     = "missing"

            self._tree.insert("", "end", iid=iid,
                              values=(full_key, desc, tpl_type, display, status),
                              tags=(tag,))

            if (isinstance(tpl_val, dict)
                    and key in actual_dict
                    and isinstance(actual_dict[key], dict)):
                for sub_key, sub_tpl in tpl_val.items():
                    _add_template_row(sub_key, sub_tpl,
                                      actual_dict[key],
                                      parent_key=key,
                                      iid_prefix=iid_prefix + full_key + ".")

        for key, tpl_val in USERCONFIG_TEMPLATE.items():
            _add_template_row(key, tpl_val, self._cfg)

        # ② 文件里有、模板里已没有的多余 key（淡蓝、只读）
        extra_keys = _collect_extra_keys(self._cfg, USERCONFIG_TEMPLATE)
        for full_key in extra_keys:
            parts    = full_key.split(".")
            cur_dict = self._cfg
            try:
                for p in parts[:-1]:
                    cur_dict = cur_dict[p]
                cur_val = cur_dict[parts[-1]]
            except (KeyError, TypeError):
                continue

            cur_type = _type_label(cur_val)
            s        = str(cur_val)
            display  = f"[{cur_type}] {s[:60]}…" if len(s) > 60 else s

            self._tree.insert("", "end",
                              iid="__extra__" + full_key,
                              values=(full_key, "（模板已无此字段）",
                                      cur_type, display, "多余"),
                              tags=("extra",))

    # ── 渲染 FILE_LABEL ──────────────────────────────────
    def _render_fl(self):
        self._fl_tree.delete(*self._fl_tree.get_children())
        for k, v in self._fl.items():
            if not isinstance(v, str):
                continue
            exists = "✅" if os.path.exists(v) else "❌"
            tag    = "ok" if os.path.exists(v) else "bad"
            dp     = v if len(v) < 45 else "…" + v[-42:]
            self._fl_tree.insert("", "end",
                                 values=(k, exists, dp), tags=(tag,))

    # ── 双击编辑 ─────────────────────────────────────────
    def _on_row_dclick(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        row_vals = self._tree.item(sel[0], "values")
        full_key = row_vals[0]
        status   = row_vals[4]

        # 多余 key：只读
        if status == "多余":
            messagebox.showinfo("只读字段",
                f"字段 [{full_key}] 在当前模板中已不存在。\n"
                "保存时会原封不动地保留此字段，无法在此修改。")
            return

        # 缺失 key：提示修复
        if status == "缺失":
            ans = messagebox.askyesno(
                "字段缺失",
                f"字段 [{full_key}] 在当前文件中不存在。\n\n"
                "是否用模板默认值修复？\n"
                "（修复后可再次双击修改具体值）"
            )
            if not ans:
                return

            parts    = full_key.split(".")
            tpl_dict = USERCONFIG_TEMPLATE
            try:
                for p in parts[:-1]:
                    tpl_dict = tpl_dict[p]
                tpl_val = tpl_dict[parts[-1]]
            except KeyError:
                messagebox.showerror("修复失败",
                    f"模板中也找不到字段 [{full_key}]，无法修复。")
                return

            cur_dict = self._cfg
            try:
                for p in parts[:-1]:
                    if p not in cur_dict:
                        cur_dict[p] = {}
                    cur_dict = cur_dict[p]
                cur_dict[parts[-1]] = tpl_val
            except Exception as e:
                messagebox.showerror("修复失败", str(e))
                return

            self._dirty = True
            self._btn_save.config(state="normal")
            self._render_fields()
            self._status_var.set(f"🔧 已修复 [{full_key}]，记得保存")
            messagebox.showinfo("修复成功",
                f"字段 [{full_key}] 已写入默认值：\n{tpl_val}\n\n"
                "可再次双击修改具体值。")
            return

        # 正常 key：弹编辑框
        parts    = full_key.split(".")
        cur_dict = self._cfg
        for p in parts[:-1]:
            cur_dict = cur_dict[p]
        leaf_key = parts[-1]
        cur_val  = cur_dict[leaf_key]

        tpl_dict = USERCONFIG_TEMPLATE
        for p in parts[:-1]:
            tpl_dict = tpl_dict[p]
        tpl_val = tpl_dict.get(leaf_key, cur_val)

        def on_save(key, new_val):
            cur_dict[leaf_key] = new_val
            self._dirty = True
            self._btn_save.config(state="normal")
            self._render_fields()
            self._status_var.set(f"✏️ 已修改 [{full_key}]，记得保存")

        EditDialog(self, leaf_key, cur_val, tpl_val, on_save)

    # ── 保存（多余 key 原封不动写回）────────────────────
    def _save_data(self):
        if not self._use1:
            return
        try:
            _write_encrypted(self._use1, self._cfg, KEY_LABEL["UserData"])
            self._dirty = False
            self._btn_save.config(state="disabled")
            self._status_var.set("✅ 保存成功")
            messagebox.showinfo("保存成功", f"已写回：\n{self._use1}")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def _on_close(self):
        if self._dirty:
            if not messagebox.askyesno("未保存",
                    "有未保存的修改，确定要退出吗？"):
                return
        self.destroy()


# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = DebugVisual()
    app.protocol("WM_DELETE_WINDOW", app._on_close)
    app.mainloop()
