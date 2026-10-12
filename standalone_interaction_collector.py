# -*- coding: utf-8 -*-
"""无需肌电手环的动作提示、协议执行与数据打标工具。

只依赖 PyQt5。运行后会按照 ``基态 -> 目标 -> 基态`` 的节奏展示提示，
并将协议事件与人工标记分别保存为 CSV；不会连接、读取或伪造 EMG 数据。
"""

import csv
import json
import os
import random
import sys
import time
from datetime import datetime

from PyQt5.QtCore import QRect, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QSpinBox, QStatusBar, QTextEdit, QVBoxLayout,
    QWidget, QProgressBar,
)


GESTURES = [
    ("R0", "静息态"), ("G1", "张手"), ("G2", "握拳"), ("G3", "八"),
    ("G4", "竖大拇指"), ("G5", "指向"), ("G6", "V 手势"),
    ("G7", "指尖捏"), ("G9", "四"), ("G10", "六"),
]
GESTURE_NAMES = dict(GESTURES)
GESTURE_INDEX = {gesture_id: index for index, (gesture_id, _) in enumerate(GESTURES)}
GROUPS = [
    ("B01", "1. 静息态为基态", "R0", ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G9", "G10"], True),
    ("B02", "2. 张手为基态", "G1", ["G2", "G3", "G4", "G5", "G6", "G7", "G9", "G10"], False),
    ("B03", "3. 握拳为基态", "G2", ["G3", "G4", "G5", "G6", "G10"], False),
    ("B04", "4. 八为基态", "G3", ["G4", "G5", "G7"], False),
]
PHASE_TITLES = {
    "prepare": "执行准备", "formation": "执行", "transition": "执行",
    "hold": "维持", "recovery": "恢复",
}
PHASE_COLORS = {
    "执行准备": "#ffe7a3", "执行": "#9ed5ff", "维持": "#a9dfbf",
    "恢复": "#cbb5ff", "静息准备": "#d9e0e5",
}
IMAGE_SHEET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gesture_assets", "hand_gesture_sheet.png")
EVENT_FIELDS = [
    "event_type", "timestamp_local", "elapsed_s", "session_id", "group_id",
    "phase", "gesture_from", "gesture_to", "base_gesture", "target_gesture",
    "cycle_index", "planned_duration_s", "note",
]


def gesture_text(gesture_id):
    return f"{gesture_id} {GESTURE_NAMES[gesture_id]}"


def step(duration_s, phase, gesture_from, gesture_to, text, base, target="", cycle_index=""):
    return {
        "duration_s": float(duration_s), "phase": phase, "gesture_from": gesture_from,
        "gesture_to": gesture_to, "text": text, "base": base, "target": target,
        "cycle_index": cycle_index,
    }


def build_steps(group, prepare_s, repetitions, randomize):
    """构建完全带标签的 B -> T -> B 协议，和上位机的动作时序保持一致。"""
    group_id, _, base, targets, _ = group
    del group_id
    cycles = [target for target in targets for _ in range(repetitions)]
    if randomize:
        random.shuffle(cycles)

    def prepare(current, upcoming, target="", cycle_index=""):
        return step(prepare_s, "prepare", current, current,
                    f"准备：保持 {gesture_text(current)}；{prepare_s:.1f} 秒后 {upcoming}",
                    base, target, cycle_index)

    result = [prepare("R0", "开始第一个动作"), step(2, "hold", "R0", "R0", "保持自然静息", base)]
    if base != "R0":
        result.extend([
            prepare("R0", f"形成 {gesture_text(base)}"),
            step(2, "formation", "R0", base, f"从静息形成 {gesture_text(base)}", base),
            step(3, "hold", base, base, f"维持基态：{gesture_text(base)}", base),
        ])
    for cycle_index, target in enumerate(cycles, start=1):
        if base == "R0":
            forward_phase, return_phase = "formation", "recovery"
            forward_text = f"从静息形成 {gesture_text(target)}"
            return_text = f"从 {gesture_text(target)} 放松至静息"
            base_text = "保持自然静息"
        else:
            forward_phase = return_phase = "transition"
            forward_text = f"从 {gesture_text(base)} 转为 {gesture_text(target)}"
            return_text = f"从 {gesture_text(target)} 回到 {gesture_text(base)}"
            base_text = f"维持基态：{gesture_text(base)}"
        result.extend([
            prepare(base, forward_text, target, cycle_index),
            step(2, forward_phase, base, target, forward_text, base, target, cycle_index),
            step(3, "hold", target, target, f"维持目标：{gesture_text(target)}", base, target, cycle_index),
            step(2, return_phase, target, base, return_text, base, target, cycle_index),
            step(2, "hold", base, base, base_text, base, target, cycle_index),
        ])
    if base != "R0":
        result.extend([
            prepare(base, "放松至静息"),
            step(2, "recovery", base, "R0", f"从 {gesture_text(base)} 放松至静息", base),
            step(3, "hold", "R0", "R0", "保持自然静息", base),
        ])
    return result


class GesturePhoto(QLabel):
    """从 4 x 3 图片表中裁切指定姿态。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.gesture_id = "R0"
        self.sheet = QPixmap(IMAGE_SHEET)
        self.setMinimumSize(160, 180)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background:#fafafa; border:1px solid #d7dce0;")

    def set_gesture(self, gesture_id):
        self.gesture_id = gesture_id
        self._render()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render()

    def _render(self):
        if self.sheet.isNull():
            self.setText("未找到手势图片")
            return
        index = GESTURE_INDEX[self.gesture_id]
        col, row = index % 4, index // 4
        width, height = self.sheet.width(), self.sheet.height()
        left, top = col * width // 4, row * height // 3
        right, bottom = (col + 1) * width // 4, (row + 1) * height // 3
        self.setText("")
        self.setPixmap(self.sheet.copy(QRect(left, top, right - left, bottom - top)).scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))


class ActionTimeline(QWidget):
    """在 B -> T -> B 时间轴的相位起点显示三张姿态图。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.base = self.target = "R0"
        self.stages, self.elapsed = [], 0.0
        self.photos = [GesturePhoto(self) for _ in range(3)]
        self.setMinimumHeight(285)

    def set_cycle(self, base, target, stages, elapsed):
        self.base, self.target = base, target
        self.stages, self.elapsed = list(stages), max(0.0, elapsed)
        for photo, gesture_id in zip(self.photos, (base, target, base)):
            photo.set_gesture(gesture_id)
        self._position_photos()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_photos()

    def _position_photos(self):
        total = max(1.0, sum(duration for _, duration in self.stages))
        starts, elapsed = {}, 0.0
        for label, duration in self.stages:
            starts.setdefault(label, elapsed / total)
            elapsed += duration
        for photo, fraction in zip(self.photos, (starts.get("执行准备", 0), starts.get("执行", 0.2), starts.get("恢复", 0.7))):
            photo.setGeometry(max(0, round(fraction * self.width()) - 84), 0, 168, 190)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        bar = QRect(14, 207, max(1, self.width() - 28), 30)
        total = max(1.0, sum(duration for _, duration in self.stages))
        consumed = 0.0
        for label, duration in self.stages:
            left = bar.left() + round(bar.width() * consumed / total)
            consumed += duration
            right = bar.left() + round(bar.width() * consumed / total)
            rect = QRect(left, bar.top(), max(1, right - left), bar.height())
            painter.fillRect(rect, QColor(PHASE_COLORS.get(label, "#d9e0e5")))
            painter.setPen(QPen(QColor("#ffffff")))
            painter.drawRect(rect)
            painter.setPen(QColor("#37474f"))
            painter.drawText(QRect(left, 243, max(1, right - left), 24), Qt.AlignHCenter | Qt.AlignTop, label)
        x = bar.left() + round(bar.width() * min(1.0, self.elapsed / total))
        painter.setPen(QPen(QColor("#263238"), 3))
        painter.drawLine(x, bar.top() - 4, x, bar.bottom() + 4)


class StandaloneInteractionCollector(QMainWindow):
    """无设备版本：提示受试者、记录自动协议标签与人工标签。"""

    def __init__(self):
        super().__init__()
        self.steps, self.step_index = [], -1
        self.active = self.paused = False
        self.started_at = self.step_started_at = None
        self.step_elapsed_before_pause = 0.0
        self.session_id = ""
        self.event_file = self.event_writer = None
        self.events, self.output_dir = [], ""
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._tick)
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("独立动作交互采集与打标工具（无肌电手环）")
        self.resize(1200, 900)
        self.setMinimumSize(1020, 760)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("动作交互采集与打标")
        title.setStyleSheet("font-size:25px;font-weight:700;color:#1f2937;")
        subtitle = QLabel("仅展示动作提示并保存时间标签；不连接、不读取或模拟肌电手环。")
        subtitle.setStyleSheet("font-size:13px;color:#607080;")
        title_box.addWidget(title); title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)
        self.session_label = QLabel("待开始")
        self.session_label.setAlignment(Qt.AlignCenter)
        self.session_label.setMinimumWidth(220)
        self.session_label.setStyleSheet(
            "padding:8px 12px;border-radius:8px;background:#eef2f6;color:#52616b;font-weight:600;"
        )
        header.addWidget(self.session_label)
        layout.addLayout(header)

        config = QGroupBox("1  协议设置")
        config.setStyleSheet("QGroupBox{font-weight:700;border:1px solid #d7dfe6;border-radius:8px;margin-top:10px;padding:10px;} QGroupBox::title{left:12px;padding:0 5px;}")
        grid = QGridLayout(config)
        grid.setHorizontalSpacing(12); grid.setVerticalSpacing(8)
        self.subject_edit = QLineEdit("S01")
        self.subject_edit.setPlaceholderText("例如 S01")
        self.group_combo = QComboBox()
        for group in GROUPS:
            self.group_combo.addItem(group[1], group)
        self.reps_spin = QSpinBox(); self.reps_spin.setRange(1, 20); self.reps_spin.setValue(1); self.reps_spin.setSuffix(" 次")
        self.prepare_spin = QDoubleSpinBox(); self.prepare_spin.setRange(0.5, 10); self.prepare_spin.setValue(2); self.prepare_spin.setSuffix(" 秒")
        self.randomize_check = QCheckBox("随机目标动作顺序")
        directory_row = QWidget(); directory_layout = QHBoxLayout(directory_row); directory_layout.setContentsMargins(0, 0, 0, 0); directory_layout.setSpacing(6)
        self.directory_edit = QLineEdit(os.path.join(os.path.dirname(os.path.abspath(__file__)), "interaction_labels"))
        self.choose_directory_button = QPushButton("选择目录")
        self.choose_directory_button.clicked.connect(self._choose_directory)
        directory_layout.addWidget(self.directory_edit); directory_layout.addWidget(self.choose_directory_button)
        grid.addWidget(QLabel("受试者编号"), 0, 0); grid.addWidget(self.subject_edit, 0, 1)
        grid.addWidget(QLabel("实验组"), 0, 2); grid.addWidget(self.group_combo, 0, 3)
        grid.addWidget(QLabel("每目标重复"), 1, 0); grid.addWidget(self.reps_spin, 1, 1)
        grid.addWidget(QLabel("执行准备"), 1, 2); grid.addWidget(self.prepare_spin, 1, 3)
        grid.addWidget(self.randomize_check, 2, 0, 1, 2)
        grid.addWidget(QLabel("保存位置"), 2, 2); grid.addWidget(directory_row, 2, 3)
        grid.setColumnStretch(1, 1); grid.setColumnStretch(3, 3)
        layout.addWidget(config)

        cue_card = QFrame()
        cue_card.setObjectName("cueCard")
        cue_card.setStyleSheet("QFrame#cueCard{background:#f7fafc;border:1px solid #dce5ec;border-radius:10px;}")
        cue_layout = QVBoxLayout(cue_card); cue_layout.setContentsMargins(22, 14, 22, 16); cue_layout.setSpacing(5)
        cue_top = QHBoxLayout()
        self.stage_label = QLabel("准备就绪")
        self.stage_label.setAlignment(Qt.AlignCenter)
        self.stage_label.setMinimumWidth(130)
        self.stage_label.setStyleSheet("font-size:20px;font-weight:700;color:#0f609b;background:#dceefa;border-radius:15px;padding:6px 14px;")
        self.step_label = QLabel("阶段 -- / --")
        self.step_label.setStyleSheet("font-size:14px;color:#637381;")
        cue_top.addWidget(self.stage_label); cue_top.addSpacing(10); cue_top.addWidget(self.step_label); cue_top.addStretch(1)
        self.countdown_label = QLabel("--.- 秒")
        self.countdown_label.setStyleSheet("font-size:30px;font-weight:700;color:#253746;")
        cue_top.addWidget(self.countdown_label)
        self.instruction_label = QLabel("设置参数后点击“开始协议”。")
        self.instruction_label.setAlignment(Qt.AlignCenter); self.instruction_label.setWordWrap(True)
        self.instruction_label.setStyleSheet("font-size:23px;font-weight:600;color:#253746;padding:3px;")
        self.cycle_label = QLabel("动作循环：--")
        self.cycle_label.setAlignment(Qt.AlignCenter); self.cycle_label.setStyleSheet("font-size:16px;font-weight:600;color:#536674;")
        cue_layout.addLayout(cue_top); cue_layout.addWidget(self.instruction_label); cue_layout.addWidget(self.cycle_label)
        layout.addWidget(cue_card)

        timing_box = QGroupBox("2  当前动作时序")
        timing_box.setStyleSheet("QGroupBox{font-weight:700;border:1px solid #d7dfe6;border-radius:8px;margin-top:10px;padding:8px;} QGroupBox::title{left:12px;padding:0 5px;}")
        timing_layout = QVBoxLayout(timing_box); timing_layout.setContentsMargins(10, 8, 10, 8)
        self.timeline = ActionTimeline(); timing_layout.addWidget(self.timeline, 1)
        layout.addWidget(timing_box, 1)

        progress_row = QHBoxLayout()
        progress_info = QVBoxLayout()
        self.protocol_progress_text = QLabel("协议总进度：等待开始")
        self.protocol_progress_text.setStyleSheet("font-size:13px;font-weight:600;color:#4e6270;")
        self.protocol_progress = QProgressBar(); self.protocol_progress.setRange(0, 1000); self.protocol_progress.setValue(0); self.protocol_progress.setTextVisible(False); self.protocol_progress.setFixedHeight(10)
        self.protocol_progress.setStyleSheet("QProgressBar{border:0;border-radius:5px;background:#e6edf2;} QProgressBar::chunk{border-radius:5px;background:#2b82bd;}")
        progress_info.addWidget(self.protocol_progress_text); progress_info.addWidget(self.protocol_progress)
        progress_row.addLayout(progress_info, 1)
        layout.addLayout(progress_row)

        bottom_row = QHBoxLayout()
        controls_box = QGroupBox("3  协议控制")
        controls_box.setStyleSheet("QGroupBox{font-weight:700;border:1px solid #d7dfe6;border-radius:8px;margin-top:10px;padding:10px;} QGroupBox::title{left:12px;padding:0 5px;}")
        controls = QHBoxLayout(controls_box)
        self.start_button = QPushButton("开始协议"); self.start_button.clicked.connect(self.start_protocol)
        self.pause_button = QPushButton("暂停"); self.pause_button.clicked.connect(self.toggle_pause); self.pause_button.setEnabled(False)
        self.stop_button = QPushButton("停止并保存"); self.stop_button.clicked.connect(self.stop_protocol); self.stop_button.setEnabled(False)
        for button in (self.start_button, self.pause_button, self.stop_button):
            button.setMinimumHeight(42)
        self.start_button.setStyleSheet("font-weight:700;background:#1976b5;color:white;border:0;border-radius:6px;padding:0 18px;")
        self.pause_button.setStyleSheet("font-weight:700;background:#f0a62f;color:#28323a;border:0;border-radius:6px;padding:0 18px;")
        self.stop_button.setStyleSheet("font-weight:700;background:#e6edf2;color:#334753;border:0;border-radius:6px;padding:0 18px;")
        controls.addWidget(self.start_button); controls.addWidget(self.pause_button); controls.addWidget(self.stop_button)
        bottom_row.addWidget(controls_box, 1)

        marker_box = QGroupBox("4  人工补充标记")
        marker_box.setStyleSheet("QGroupBox{font-weight:700;border:1px solid #d7dfe6;border-radius:8px;margin-top:10px;padding:10px;} QGroupBox::title{left:12px;padding:0 5px;}")
        marker_layout = QVBoxLayout(marker_box)
        self.marker_combo = QComboBox()
        for key, name in [("observer_note", "观察备注"), ("valid", "有效"), ("invalid", "无效/误动作"), ("repeat", "需重做"), ("custom", "自定义")]:
            self.marker_combo.addItem(name, key)
        marker_top = QHBoxLayout(); marker_top.addWidget(QLabel("类型")); marker_top.addWidget(self.marker_combo, 1)
        self.marker_note = QTextEdit(); self.marker_note.setPlaceholderText("可选：例如“第 3 次握拳提前开始”"); self.marker_note.setFixedHeight(48)
        self.marker_button = QPushButton("保存当前标记"); self.marker_button.clicked.connect(self.save_manual_marker); self.marker_button.setEnabled(False)
        self.marker_button.setMinimumHeight(34)
        marker_layout.addLayout(marker_top); marker_layout.addWidget(self.marker_note); marker_layout.addWidget(self.marker_button)
        bottom_row.addWidget(marker_box, 2)
        layout.addLayout(bottom_row)
        self.status = QStatusBar(); self.setStatusBar(self.status)

    def _choose_directory(self):
        chosen = QFileDialog.getExistingDirectory(self, "选择标签保存目录", self.directory_edit.text())
        if chosen:
            self.directory_edit.setText(chosen)

    @staticmethod
    def _safe_name(value):
        return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value.strip())[:32] or "subject"

    def _current_group(self):
        return self.group_combo.currentData()

    def _write_event(self, event_type, step_data=None, note=""):
        now = time.monotonic()
        current = step_data or (self.steps[self.step_index] if 0 <= self.step_index < len(self.steps) else None)
        row = {
            "event_type": event_type, "timestamp_local": datetime.now().isoformat(timespec="milliseconds"),
            "elapsed_s": round(now - self.started_at, 6) if self.started_at else "", "session_id": self.session_id,
            "group_id": self._current_group()[0], "phase": current["phase"] if current else "",
            "gesture_from": current["gesture_from"] if current else "", "gesture_to": current["gesture_to"] if current else "",
            "base_gesture": current["base"] if current else "", "target_gesture": current["target"] if current else "",
            "cycle_index": current["cycle_index"] if current else "", "planned_duration_s": current["duration_s"] if current else "", "note": note,
        }
        self.events.append(row)
        self.event_writer.writerow(row)
        self.event_file.flush()

    def _write_metadata(self, completed):
        _, title, base, targets, static_group = self._current_group()
        payload = {
            "schema_version": 1, "data_source": "manual_interaction_only", "completed": bool(completed),
            "session_id": self.session_id, "subject_id": self.subject_edit.text().strip(),
            "group": {"title": title, "base": base, "targets": targets, "static_group": static_group},
            "protocol_parameters": {"prepare_duration_s": self.prepare_spin.value(), "repetitions": self.reps_spin.value(), "randomize_targets": self.randomize_check.isChecked()},
            "gesture_definitions": dict(GESTURES), "event_count": len(self.events),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "note": "本工具不采集 EMG；events.csv 同时保存自动阶段标签和人工标记。",
        }
        with open(os.path.join(self.output_dir, f"{self.session_id}_metadata.json"), "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)

    def start_protocol(self):
        if self.active:
            return
        group = self._current_group()
        self.steps = build_steps(group, self.prepare_spin.value(), self.reps_spin.value(), self.randomize_check.isChecked())
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_id = f"{self._safe_name(self.subject_edit.text())}_{group[0]}_{stamp}"
        self.output_dir = self.directory_edit.text().strip()
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            path = os.path.join(self.output_dir, f"{self.session_id}_events.csv")
            self.event_file = open(path, "w", newline="", encoding="utf-8")
            self.event_writer = csv.DictWriter(self.event_file, fieldnames=EVENT_FIELDS)
            self.event_writer.writeheader()
        except OSError as exc:
            QMessageBox.critical(self, "无法创建输出文件", str(exc))
            return
        self.active, self.paused, self.events, self.step_index = True, False, [], -1
        self.started_at = time.monotonic()
        self._write_event("protocol_start", note=f"{group[1]}；共 {len(self.steps)} 个阶段")
        self._write_metadata(completed=False)
        self._set_config_enabled(False)
        self.pause_button.setEnabled(True); self.stop_button.setEnabled(True); self.marker_button.setEnabled(True)
        self.session_label.setText(f"运行中 · {self.session_id}")
        self.session_label.setStyleSheet(
            "padding:8px 12px;border-radius:8px;background:#e3f4ea;color:#1b6b43;font-weight:700;"
        )
        self._advance()

    def _advance(self):
        self.step_index += 1
        if self.step_index >= len(self.steps):
            self.stop_protocol(completed=True)
            return
        current = self.steps[self.step_index]
        self.step_started_at, self.step_elapsed_before_pause = time.monotonic(), 0.0
        self._write_event("step_start", current)
        self.timer.start()
        self._refresh(0.0)

    def _action_stages(self):
        current = self.steps[self.step_index]
        cycle = current["cycle_index"]
        if not cycle:
            return [("静息准备", current["duration_s"])]
        result = []
        for candidate in self.steps:
            if candidate["cycle_index"] == cycle:
                label = "执行准备" if candidate["phase"] == "prepare" else (
                    "维持" if candidate["phase"] == "hold" and candidate["gesture_from"] == candidate["target"] else
                    "静息准备" if candidate["phase"] == "hold" else
                    "执行" if candidate["gesture_from"] == candidate["base"] else "恢复")
                result.append((label, candidate["duration_s"]))
        return result

    def _refresh(self, elapsed):
        current = self.steps[self.step_index]
        remaining = max(0.0, current["duration_s"] - elapsed)
        title = PHASE_TITLES.get(current["phase"], "动作提示")
        self.stage_label.setText(title)
        phase_color = PHASE_COLORS.get(title, "#dceefa")
        self.stage_label.setStyleSheet(
            f"font-size:20px;font-weight:700;color:#253746;background:{phase_color};"
            "border-radius:15px;padding:6px 14px;"
        )
        self.step_label.setText(f"阶段 {self.step_index + 1} / {len(self.steps)}")
        self.instruction_label.setText(current["text"])
        if current["cycle_index"]:
            action_elapsed = sum(
                item["duration_s"] for index, item in enumerate(self.steps)
                if item["cycle_index"] == current["cycle_index"] and index < self.step_index
            ) + elapsed
            self.cycle_label.setText(f"动作 {current['cycle_index']}：{gesture_text(current['base'])} → {gesture_text(current['target'])} → {gesture_text(current['base'])}")
            self.timeline.set_cycle(current["base"], current["target"], self._action_stages(), action_elapsed)
        else:
            self.cycle_label.setText(f"协议准备：{gesture_text(current['gesture_from'])}")
            self.timeline.set_cycle(current["gesture_from"], current["gesture_from"], self._action_stages(), elapsed)
        self.countdown_label.setText(f"{remaining:.1f} 秒")
        elapsed_before = sum(item["duration_s"] for item in self.steps[:self.step_index])
        total = max(0.01, sum(item["duration_s"] for item in self.steps))
        fraction = min(1.0, (elapsed_before + min(elapsed, current["duration_s"])) / total)
        self.protocol_progress.setValue(round(fraction * 1000))
        self.protocol_progress_text.setText(
            f"协议总进度：{fraction * 100:.0f}%  ·  第 {self.step_index + 1} / {len(self.steps)} 阶段"
        )

    def _tick(self):
        if not self.active or self.paused:
            return
        elapsed = time.monotonic() - self.step_started_at
        self._refresh(elapsed)
        if elapsed >= self.steps[self.step_index]["duration_s"]:
            self.timer.stop()
            self._write_event("step_end", self.steps[self.step_index])
            self._advance()

    def toggle_pause(self):
        self.paused = not self.paused
        if self.paused:
            self.step_elapsed_before_pause = time.monotonic() - self.step_started_at
            self.timer.stop(); self._write_event("protocol_pause")
            self.pause_button.setText("继续")
            self.session_label.setText(f"已暂停 · {self.session_id}")
            self.session_label.setStyleSheet(
                "padding:8px 12px;border-radius:8px;background:#fff2d7;color:#92651a;font-weight:700;"
            )
            self.instruction_label.setText("协议已暂停：保持当前姿势；点击“继续”后再按提示运动。")
        else:
            self.step_started_at = time.monotonic() - self.step_elapsed_before_pause
            self.timer.start(); self._write_event("protocol_resume")
            self.pause_button.setText("暂停")
            self.session_label.setText(f"运行中 · {self.session_id}")
            self.session_label.setStyleSheet(
                "padding:8px 12px;border-radius:8px;background:#e3f4ea;color:#1b6b43;font-weight:700;"
            )

    def save_manual_marker(self):
        if not self.active:
            return
        kind = self.marker_combo.currentData()
        note = self.marker_note.toPlainText().strip()
        self._write_event("manual_marker", note=f"{kind}: {note}".rstrip())
        self.marker_note.clear()
        self.status.showMessage("人工标记已写入 events.csv", 3000)

    def _set_config_enabled(self, enabled):
        for widget in (self.subject_edit, self.group_combo, self.reps_spin, self.prepare_spin,
                       self.randomize_check, self.directory_edit, self.choose_directory_button):
            widget.setEnabled(enabled)
        self.start_button.setEnabled(enabled)

    def stop_protocol(self, completed=False):
        if not self.active:
            return
        self.timer.stop()
        self._write_event("protocol_complete" if completed else "protocol_stop")
        self.active = self.paused = False
        self._write_metadata(completed)
        path = self.event_file.name
        self.event_file.close(); self.event_file = self.event_writer = None
        self._set_config_enabled(True)
        self.pause_button.setEnabled(False); self.stop_button.setEnabled(False); self.marker_button.setEnabled(False)
        self.pause_button.setText("暂停")
        self.stage_label.setText("已完成" if completed else "已停止")
        self.instruction_label.setText(f"标签已保存：{path}")
        self.step_label.setText("阶段已结束")
        self.countdown_label.setText("--.- 秒")
        self.protocol_progress.setValue(1000 if completed else self.protocol_progress.value())
        self.protocol_progress_text.setText("协议总进度：100%" if completed else "协议已停止，标签已保存")
        self.session_label.setText("已完成" if completed else "已停止")
        self.session_label.setStyleSheet(
            "padding:8px 12px;border-radius:8px;background:#eef2f6;color:#52616b;font-weight:700;"
        )
        self.status.showMessage("协议完成，事件与人工标记已保存。", 8000)

    def closeEvent(self, event):
        if self.active:
            answer = QMessageBox.question(self, "结束协议", "当前协议尚未结束，是否停止并保存？", QMessageBox.Yes | QMessageBox.No)
            if answer == QMessageBox.No:
                event.ignore(); return
            self.stop_protocol()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = StandaloneInteractionCollector()
    window.show()
    sys.exit(app.exec_())
