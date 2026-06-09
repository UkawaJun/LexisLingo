# ============================================================
# Debug30Days.py  —  LexisLingo 学习数据可视化（PyQt5版）
# ============================================================
import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try: ctypes.windll.user32.SetProcessDPIAware()
    except Exception: pass

import os, sys, json, sqlite3
from datetime import datetime, timedelta
from urllib.parse import quote

from PyQt5.QtCore    import Qt, QUrl, QUrlQuery, QTimer
from PyQt5.QtGui     import QFont
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                              QHBoxLayout, QLabel, QComboBox, QPushButton,
                              QFrame, QSplitter, QSizePolicy)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings

QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
app = QApplication.instance() or QApplication(sys.argv)

from _Enviro import EndeCrypt
from Config  import KEY_LABEL, _WOP

HTML_PATH = os.path.abspath(os.path.join("HTML", "show30DaysDate.html"))

# ══ 工具函数 ══════════════════════════════════════════════════
def _read_enc(path, key):
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    dec = EndeCrypt(raw, key, decode=True)
    try:
        from json_repair import loads; return loads(dec)
    except ImportError:
        return json.loads(dec)

def _decode_word(blob, key):
    try: return json.loads(EndeCrypt(blob, key, decode=True))
    except: return {}

def _build_paths(course, user):
    cp = f"Data/{course}"
    return {
        "Use1": f"{cp}/UserConfig/{user}.json",
        "Use2": f"{cp}/UserConfig/{user}_ld.db",
    }

def _collect_30days(udict):
    today  = datetime.now().date()
    days   = [(today - timedelta(days=i)) for i in range(29, -1, -1)]
    daily  = udict.get("DailyDate", {})
    labels = []
    result = {}
    for d in days:
        label = d.strftime("%m/%d")
        y  = str(d.year)
        m  = str(d.month)
        dd = str(d.day)
        key = d.strftime("%Y-%m-%d")
        labels.append(label)
        row = {}
        try: row = daily[y][m][dd]
        except (KeyError, TypeError): pass
        result[key] = {
            "label": label,
            "t":  row.get("t",  0) if isinstance(row, dict) else 0,
            "x":  row.get("x",  0) if isinstance(row, dict) else 0,
            "n":  row.get("n",  0) if isinstance(row, dict) else 0,
            "ex": row.get("ex", 0) if isinstance(row, dict) else 0,
            "ee": row.get("ee", 0) if isinstance(row, dict) else 0,
            "re": row.get("re", 0) if isinstance(row, dict) else 0,
            "er": row.get("er", 0) if isinstance(row, dict) else 0,
            "new": 0,
        }
    return labels, result

def _count_new_words(db_path, key, day_data):
    if not os.path.exists(db_path): return
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT data FROM UserWordF").fetchall()
        conn.close()
        for row in rows:
            info = _decode_word(row[0], key)
            fs   = info.get(_WOP["FirstSeenAt"], 0)
            if fs:
                d = datetime.fromtimestamp(int(fs)).strftime("%Y-%m-%d")
                if d in day_data:
                    day_data[d]["new"] += 1
    except Exception: pass

def _count_stats(db_path, key):
    total = mastered = examed = 0
    if not os.path.exists(db_path): return total, mastered, examed
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT data FROM UserWordF").fetchall()
        conn.close()
        for row in rows:
            info = _decode_word(row[0], key)
            total += 1
            if info.get(_WOP["IsMastered"], False): mastered += 1
            if info.get(_WOP["IsExamed"],   0) > 0: examed   += 1
    except Exception: pass
    return total, mastered, examed

# ══ 统计卡片 ══════════════════════════════════════════════════
class StatCard(QFrame):
    def __init__(self, eng_label, chn_label, color, parent=None):
        super().__init__(parent)
        self.setFixedHeight(100)
        self.setStyleSheet(f"""
            QFrame {{
                background: #ffffff;
                border-left: 4px solid {color};
                border-top: none; border-right: none; border-bottom: none;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 8, 16, 8)
        lay.setSpacing(1)

        lbl_eng = QLabel(eng_label)
        lbl_eng.setFont(QFont("Consolas", 9, QFont.Bold))
        lbl_eng.setStyleSheet(f"color:{color}; letter-spacing:2px; background:transparent;")

        self.lbl_val = QLabel("—")
        self.lbl_val.setFont(QFont("Microsoft YaHei", 20, QFont.Bold))
        self.lbl_val.setStyleSheet("color:#1a1a2e; background:transparent;")

        lbl_chn = QLabel(chn_label)
        lbl_chn.setFont(QFont("Microsoft YaHei", 10))
        lbl_chn.setStyleSheet("color:#aaaaaa; background:transparent;")

        lay.addWidget(lbl_eng)
        lay.addWidget(self.lbl_val)
        lay.addWidget(lbl_chn)

    def set_value(self, val):
        self.lbl_val.setText(str(val))

# ══ 信息行 ════════════════════════════════════════════════════
class InfoRow(QWidget):
    def __init__(self, label, value, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 3, 16, 3)
        lay.setSpacing(8)

        dot = QLabel("·")
        dot.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        dot.setStyleSheet("color:#e63946; background:transparent;")
        dot.setFixedWidth(14)

        lbl = QLabel(label)
        lbl.setFont(QFont("Microsoft YaHei", 11))
        lbl.setStyleSheet("color:#888888; background:transparent;")
        lbl.setFixedWidth(50)

        val = QLabel(value)
        val.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        val.setStyleSheet("color:#1a1a2e; background:transparent;")

        lay.addWidget(dot)
        lay.addWidget(lbl)
        lay.addWidget(val)
        lay.addStretch()

# ══ 主窗口 ════════════════════════════════════════════════════
class Debug30Days(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LexisLingo · 学习数据可视化")
        self.resize(1200, 760)
        self._udict          = {}
        self._paths          = {}
        self._course_collapsed = False
        self._flame_frames   = ["🔥", "🔆", "🔥", "✨"]
        self._flame_idx      = 0
        self._streak         = 0
        self._build_ui()

        # 实时时钟定时器
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start()
        self._update_clock()

        # 火焰动画定时器
        self._flame_timer = QTimer(self)
        self._flame_timer.setInterval(400)
        self._flame_timer.timeout.connect(self._update_flame)
        self._flame_timer.start()

    # ── 时钟 ─────────────────────────────────────────────
    def _update_clock(self):
        now = datetime.now()
        self._lbl_clock.setText(now.strftime("%H:%M:%S"))
        self._lbl_date.setText(now.strftime("%Y年%m月%d日"))

    def _update_flame(self):
        if self._streak > 0:
            self._flame_idx = (self._flame_idx + 1) % len(self._flame_frames)
            flame = self._flame_frames[self._flame_idx]
            self._lbl_streak.setText(f"{flame}  {self._streak} 天")

    # ── UI ───────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        central.setStyleSheet("background:#f0f2f5;")
        root_lay = QVBoxLayout(central)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # 顶栏
        top = QWidget()
        top.setFixedHeight(56)
        top.setStyleSheet("background:#1a1a2e;")
        top_lay = QHBoxLayout(top)
        top_lay.setContentsMargins(20, 0, 20, 0)
        top_lay.setSpacing(12)

        def _lbl(text, color="#ffffff", size=12, bold=False):
            l = QLabel(text)
            l.setFont(QFont("Microsoft YaHei", size,
                            QFont.Bold if bold else QFont.Normal))
            l.setStyleSheet(f"color:{color}; background:transparent;")
            return l

        top_lay.addWidget(_lbl("LexisLingo", "#ffffff", 13, True))
        top_lay.addWidget(_lbl("/", "#444466", 13))
        top_lay.addWidget(_lbl("学习数据可视化", "#aaaacc", 12))
        top_lay.addStretch()

        top_lay.addWidget(_lbl("课程", "#8899aa"))
        self._course_cb = QComboBox()
        self._course_cb.setFixedWidth(160)
        self._course_cb.setFont(QFont("Microsoft YaHei", 11))
        self._course_cb.setStyleSheet("""
            QComboBox { background:#2c2c4a; color:#ffffff; border:none;
                        border-radius:4px; padding:5px 10px; }
            QComboBox::drop-down { border:none; }
            QComboBox QAbstractItemView { background:#2c2c4a; color:#ffffff;
                        selection-background-color:#e63946; }
        """)
        self._course_cb.currentIndexChanged.connect(self._on_course_change)
        top_lay.addWidget(self._course_cb)

        top_lay.addWidget(_lbl("用户", "#8899aa"))
        self._user_cb = QComboBox()
        self._user_cb.setFixedWidth(130)
        self._user_cb.setFont(QFont("Microsoft YaHei", 11))
        self._user_cb.setStyleSheet(self._course_cb.styleSheet())
        top_lay.addWidget(self._user_cb)

        btn = QPushButton("载入")
        btn.setFixedSize(80, 34)
        btn.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        btn.setStyleSheet("""
            QPushButton { background:#e63946; color:#fff; border:none;
                          border-radius:4px; }
            QPushButton:hover { background:#c1121f; }
        """)
        btn.clicked.connect(self._load)
        top_lay.addWidget(btn)

        self._status = QLabel("选择课程和用户后点击【载入】")
        self._status.setFont(QFont("Microsoft YaHei", 10))
        self._status.setStyleSheet("color:#f4a261; background:transparent;")
        top_lay.addWidget(self._status)

        root_lay.addWidget(top)

        # 主体分割
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background:#e0e0e0; width:1px; }")

        # ── 左侧面板 ──────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(240)
        left.setStyleSheet("background:#f0f2f5;")
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(0)

        # 左侧小标题
        left_title = QWidget()
        left_title.setFixedHeight(44)
        left_title.setStyleSheet("background:#16213e;")
        lt_lay = QHBoxLayout(left_title)
        lt_lay.setContentsMargins(16, 0, 16, 0)
        lbl_lt = QLabel("学习概览")
        lbl_lt.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        lbl_lt.setStyleSheet("color:#ffffff; background:transparent;")
        lt_lay.addWidget(lbl_lt)
        left_lay.addWidget(left_title)
        left_lay.addSpacing(12)

        # 统计卡片
        self._card_total    = StatCard("WORDS",    "总学习词数", "#e63946")
        self._card_mastered = StatCard("MASTERED", "已掌握",    "#2a9d8f")
        self._card_examed   = StatCard("EXAMED",   "已考核",    "#6c63ff")

        for card in [self._card_total, self._card_mastered, self._card_examed]:
            wrap = QWidget()
            wrap.setStyleSheet("background:#f0f2f5;")
            wl = QVBoxLayout(wrap)
            wl.setContentsMargins(16, 0, 16, 10)
            wl.addWidget(card)
            left_lay.addWidget(wrap)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:#dddddd;")
        left_lay.addWidget(sep)
        left_lay.addSpacing(8)

        # 用户基本信息区
        self._info_area = QWidget()
        self._info_area.setStyleSheet("background:transparent;")
        self._info_lay = QVBoxLayout(self._info_area)
        self._info_lay.setContentsMargins(0, 0, 0, 0)
        self._info_lay.setSpacing(2)
        left_lay.addWidget(self._info_area)

        left_lay.addSpacing(4)

        # 课程折叠按钮
        self._course_toggle_btn = QPushButton("▼  课程进度")
        self._course_toggle_btn.setFont(QFont("Microsoft YaHei", 10))
        self._course_toggle_btn.setFixedHeight(28)
        self._course_toggle_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #888888;
                border: none; text-align: left;
                padding-left: 16px;
            }
            QPushButton:hover { color: #333333; }
        """)
        self._course_toggle_btn.clicked.connect(self._toggle_course_rows)
        left_lay.addWidget(self._course_toggle_btn)

        # 课程信息区（可折叠）
        self._course_rows_area = QWidget()
        self._course_rows_area.setStyleSheet("background:transparent;")
        self._course_rows_lay = QVBoxLayout(self._course_rows_area)
        self._course_rows_lay.setContentsMargins(0, 0, 0, 0)
        self._course_rows_lay.setSpacing(2)
        left_lay.addWidget(self._course_rows_area)

        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet("background:#dddddd;")
        left_lay.addWidget(sep2)
        left_lay.addSpacing(10)

        # 连续天数（火焰动态）
        self._lbl_streak = QLabel("")
        self._lbl_streak.setVisible(False)

        self._lbl_streak.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        self._lbl_streak.setStyleSheet("color:#e63946; background:transparent;")
        self._lbl_streak.setAlignment(Qt.AlignCenter)
        left_lay.addWidget(self._lbl_streak)

        self._lbl_streak_sub = QLabel("连续学习天数")
        self._lbl_streak_sub.setFont(QFont("Microsoft YaHei", 10))
        self._lbl_streak_sub.setStyleSheet("color:#aaaaaa; background:transparent;")
        self._lbl_streak_sub.setAlignment(Qt.AlignCenter)
        self._lbl_streak_sub.setVisible(False)
        left_lay.addWidget(self._lbl_streak_sub)

        left_lay.addSpacing(12)

        sep3 = QFrame()
        sep3.setFixedHeight(1)
        sep3.setStyleSheet("background:#dddddd;")
        left_lay.addWidget(sep3)
        left_lay.addSpacing(10)

        # 实时时钟
        self._lbl_clock = QLabel("00:00:00")
        self._lbl_clock.setFont(QFont("Consolas", 22, QFont.Bold))
        self._lbl_clock.setStyleSheet("color:#1a1a2e; background:transparent;")
        self._lbl_clock.setAlignment(Qt.AlignCenter)
        left_lay.addWidget(self._lbl_clock)

        self._lbl_date = QLabel("")
        self._lbl_date.setFont(QFont("Microsoft YaHei", 10))
        self._lbl_date.setStyleSheet("color:#aaaaaa; background:transparent;")
        self._lbl_date.setAlignment(Qt.AlignCenter)
        left_lay.addWidget(self._lbl_date)

        
        left_lay.addStretch()
        # 截图按钮
        btn_shot = QPushButton("📷  保存截图")
        btn_shot.setFont(QFont("Microsoft YaHei", 10))
        btn_shot.setFixedHeight(36)
        btn_shot.setStyleSheet("""
            QPushButton {
                background: #1a1a2e; color: #ffffff;
                border: none; border-radius: 4px;
                margin: 0 16px;
            }
            QPushButton:hover { background: #2c2c4a; }
        """)
        btn_shot.clicked.connect(self._save_screenshot)

        
        left_lay.addWidget(btn_shot)
        left_lay.addSpacing(12)

        splitter.addWidget(left)

        # ── 右侧图表区 ────────────────────────────────────
        right = QWidget()
        right.setStyleSheet("background:#f0f2f5;")
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(20, 16, 20, 20)
        right_lay.setSpacing(10)

        hdr = QHBoxLayout()
        t1 = QLabel("30 DAYS OVERVIEW")
        t1.setFont(QFont("Consolas", 14, QFont.Bold))
        t1.setStyleSheet("color:#1a1a2e; background:transparent;")
        t2 = QLabel("最近 30 天学习活动曲线")
        t2.setFont(QFont("Microsoft YaHei", 10))
        t2.setStyleSheet("color:#999999; background:transparent;")
        hdr.addWidget(t1)
        hdr.addSpacing(12)
        hdr.addWidget(t2)
        hdr.addStretch()
        right_lay.addLayout(hdr)

        self._web = QWebEngineView()
        self._web.setStyleSheet("border:none;")
        self._web.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        QWebEngineSettings.globalSettings().setAttribute(
            QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        QWebEngineSettings.globalSettings().setAttribute(
            QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        self._web.setHtml("""
            <html><body style="margin:0;background:#ffffff;
            display:flex;align-items:center;justify-content:center;
            height:100vh;font-family:'Microsoft YaHei';
            color:#cccccc;font-size:16px;">
            载入数据后自动渲染曲线</body></html>
        """)
        right_lay.addWidget(self._web)

        splitter.addWidget(right)
        splitter.setSizes([240, 960])
        root_lay.addWidget(splitter)

        self.setCentralWidget(central)
        self._refresh_courses()

    # ── 课程折叠 ──────────────────────────────────────────
    def _toggle_course_rows(self):
        self._course_collapsed = not self._course_collapsed
        self._course_rows_area.setVisible(not self._course_collapsed)
        self._course_toggle_btn.setText(
            "▶  课程进度" if self._course_collapsed else "▼  课程进度")

    # ── 目录扫描 ──────────────────────────────────────────
    def _refresh_courses(self):
        data_root = "Data"
        if os.path.exists(data_root):
            courses = [d for d in os.listdir(data_root)
                       if os.path.isdir(os.path.join(data_root, d))]
            self._course_cb.addItems(courses)

    def _on_course_change(self):
        course = self._course_cb.currentText()
        udir   = f"Data/{course}/UserConfig"
        self._user_cb.clear()
        if os.path.exists(udir):
            users = [f[:-5] for f in os.listdir(udir)
                     if f.endswith(".json") and "_ld" not in f]
            self._user_cb.addItems(users)

    # ── 信息行 ────────────────────────────────────────────
    def _set_info_rows(self, rows):
        for i in reversed(range(self._info_lay.count())):
            w = self._info_lay.itemAt(i).widget()
            if w: w.deleteLater()
        for i in reversed(range(self._course_rows_lay.count())):
            w = self._course_rows_lay.itemAt(i).widget()
            if w: w.deleteLater()

        course_keys = ("课程", "当前")
        for label, value in rows:
            row = InfoRow(label, value)
            if label in course_keys:
                self._course_rows_lay.addWidget(row)
            else:
                self._info_lay.addWidget(row)

    # ── 连续天数 ──────────────────────────────────────────
    def _calc_streak(self, day_data):
        sorted_keys = sorted(day_data.keys(), reverse=True)
        streak = 0
        for k in sorted_keys:
            if day_data[k].get("t", 0) > 1:
                streak += 1
            else:
                break
        return streak

    # ── 截图 ──────────────────────────────────────────────
    def _save_screenshot(self):
        report_dir = os.path.abspath("Report")
        os.makedirs(report_dir, exist_ok=True)
        now      = datetime.now().strftime("%Y%m%d_%H%M%S")
        user     = self._user_cb.currentText() or "unknown"
        filename = f"{user}_{now}_学习数据.png"
        path     = os.path.join(report_dir, filename)
        screen   = self.grab()
        screen.save(path)
        self._status.setText(f"📷 截图已保存：{filename}")

    # ── 加载 ──────────────────────────────────────────────
    def _load(self):
        course = self._course_cb.currentText()
        user   = self._user_cb.currentText()
        if not course or not user: return

        self._paths = _build_paths(course, user)
        if not os.path.exists(self._paths["Use1"]):
            self._status.setText("❌ 用户文件不存在")
            return

        try:
            self._udict = _read_enc(
                self._paths["Use1"], KEY_LABEL["UserData"])
        except Exception as e:
            self._status.setText(f"读取失败：{e}")
            return

        total, mastered, examed = _count_stats(
            self._paths["Use2"], KEY_LABEL["UserData"])
        self._card_total.set_value(total)
        self._card_mastered.set_value(mastered)
        self._card_examed.set_value(examed)

        nick    = self._udict.get("Nickname", user)
        reg     = self._udict.get("RegisterTime", 0)
        reg_str = datetime.fromtimestamp(int(reg)).strftime(
            "%Y-%m-%d") if reg else "—"
        cur     = self._udict.get("CurrentCourse", "—")
        self._set_info_rows([
            ("昵称", nick),
            ("用户", user),
            ("注册", reg_str),
            ("课程", course),
            ("当前", cur),
        ])

        labels, day_data = _collect_30days(self._udict)
        _count_new_words(self._paths["Use2"], KEY_LABEL["UserData"], day_data)

        self._streak = self._calc_streak(day_data)
        self._lbl_streak.setText(f"🔥  {self._streak} 天")
        self._lbl_streak.setVisible(True)
        self._lbl_streak_sub.setVisible(True)
        self._status.setText(
            f"✅ {course} / {user}  词库 {total} 词  🔥 连续 {self._streak} 天")

        self._render_chart(labels, day_data)

    # ── 渲染图表 ──────────────────────────────────────────
    def _render_chart(self, labels, day_data):
        if not os.path.exists(HTML_PATH):
            self._status.setText("❌ 找不到 show30DaysDate.html")
            return

        # 裁掉左侧连续为零的天
        fields      = ("t","x","n","ex","ee","re","er","new")
        sorted_keys = sorted(day_data.keys())
        first_nz    = 0
        for i, k in enumerate(sorted_keys):
            if any(day_data[k].get(f, 0) > 0 for f in fields):
                first_nz = i
                break
        sorted_keys = sorted_keys[first_nz:]

        labels_out = [day_data[k]["label"] for k in sorted_keys]
        data_out   = {day_data[k]["label"]: {
            f: day_data[k][f] for f in fields
        } for k in sorted_keys}

        days_json = quote(json.dumps(labels_out, ensure_ascii=False))
        data_json = quote(json.dumps(data_out,   ensure_ascii=False))

        url   = QUrl.fromLocalFile(HTML_PATH)
        query = QUrlQuery()
        query.addQueryItem("days", days_json)
        query.addQueryItem("data", data_json)
        url.setQuery(query)
        self._web.load(url)

# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    win = Debug30Days()
    win.show()
    sys.exit(app.exec_())
