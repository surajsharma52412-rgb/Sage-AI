"""
Message Input Bar Component for Sage AI (Lunar Engine).
Matches the reference design:
- Floating neon emerald capsule bar
- Sparkle icon '✦' with 'Ask anything or describe what you want to build...'
- Toolbar: Attachment '📎', '🌐 Web Search ⌄', '+' button, model dropdown, voice '🎤', and circular '↑' send button
- Footer disclaimer: 'Sage can make mistakes. Check important info. ⓘ'
"""
from pathlib import Path
import base64
from typing import List, Dict, Any, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QComboBox, QLabel, QFrame, QFileDialog, QMenu
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor


class AttachmentChip(QFrame):
    """Pill chip displaying an attached code or image file with a delete button."""

    removed = Signal(str)

    def __init__(self, file_path: str, file_name: str, file_size: int, is_image: bool = False, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setStyleSheet("""
            QFrame {
                background-color: #162033;
                border: 1px solid rgba(0, 209, 255, 0.35);
                border-radius: 12px;
                padding: 2px 8px;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(6)

        icon_str = "🖼" if is_image else "📄"
        icon_lbl = QLabel(icon_str)
        icon_lbl.setStyleSheet("font-size: 12px;")
        layout.addWidget(icon_lbl)

        size_str = f"{file_size} B" if file_size < 1024 else f"{file_size // 1024} KB"
        name_lbl = QLabel(f"{file_name} ({size_str})")
        name_lbl.setStyleSheet("color: #f4f5fb; font-size: 11px; font-weight: 600;")
        layout.addWidget(name_lbl)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(16, 16)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #8fa0b5;
                border: none;
                font-size: 10px;
                font-weight: 700;
            }
            QPushButton:hover {
                color: #ff5c77;
            }
        """)
        del_btn.clicked.connect(lambda: self.removed.emit(self.file_path))
        layout.addWidget(del_btn)


class CustomTextEdit(QTextEdit):
    """QTextEdit capturing Enter for submission, Shift+Enter for newlines, and Drag & Drop files."""

    submit_pressed = Signal()
    files_dropped = Signal(list)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                event.accept()
                self.submit_pressed.emit()
                return
        else:
            super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
            if paths:
                self.files_dropped.emit(paths)
                event.acceptProposedAction()
                return
        super().dropEvent(event)


class MessageInputBar(QWidget):
    """Floating neon capsule input container with file attachments."""

    submitted = Signal(str, bool, str, list)  # (prompt, force_web, selected_model, attachments)
    cancelled = Signal()
    manage_models_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_busy = False
        self.attached_files: List[Dict[str, Any]] = []

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 6, 40, 14)
        main_layout.setSpacing(6)
        main_layout.setAlignment(Qt.AlignCenter)

        # 1. Floating Capsule Frame
        capsule = QFrame()
        capsule.setObjectName("floatingInputCapsule")
        capsule.setMaximumWidth(960)
        capsule.setStyleSheet("""
            QFrame#floatingInputCapsule {
                background-color: #111827;
                border: 1.5px solid rgba(0, 209, 255, 0.35);
                border-radius: 22px;
            }
            QFrame#floatingInputCapsule:hover, QFrame#floatingInputCapsule:focus-within {
                border: 1.5px solid #00D1FF;
            }
        """)
        capsule_layout = QVBoxLayout(capsule)
        capsule_layout.setContentsMargins(16, 12, 16, 12)
        capsule_layout.setSpacing(8)

        # Top row: Sparkle icon + Text Edit
        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        input_row.setAlignment(Qt.AlignTop)

        sparkle = QLabel("✦")
        sparkle.setStyleSheet("color: #00D1FF; font-size: 17px; font-weight: bold; padding-top: 4px;")
        input_row.addWidget(sparkle)

        self.text_input = CustomTextEdit()
        self.text_input.setObjectName("capsuleTextEdit")
        self.text_input.setStyleSheet("""
            QTextEdit#capsuleTextEdit {
                background: transparent;
                border: none;
                color: #F8FAFC;
                font-size: 13px;
                line-height: 1.4;
                selection-background-color: #00D1FF;
                selection-color: #0A0F14;
            }
        """)
        self.text_input.setPlaceholderText("Ask anything, attach code/files, or describe what you want to build...")
        self.text_input.setFixedHeight(50)
        self.text_input.submit_pressed.connect(self._handle_submit)
        self.text_input.files_dropped.connect(self._handle_dropped_files)
        input_row.addWidget(self.text_input, 1)

        capsule_layout.addLayout(input_row)

        # Attachment Chips Row
        self.attachments_widget = QWidget()
        self.attachments_layout = QHBoxLayout(self.attachments_widget)
        self.attachments_layout.setContentsMargins(0, 0, 0, 0)
        self.attachments_layout.setSpacing(6)
        self.attachments_layout.setAlignment(Qt.AlignLeft)
        self.attachments_widget.setVisible(False)
        capsule_layout.addWidget(self.attachments_widget)

        # Bottom row: Tools & Controls
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        pill_style = """
            QPushButton#capsulePillBtn {
                background-color: #162033;
                color: #94A3B8;
                border: 1px solid #273449;
                border-radius: 14px;
                font-size: 12px;
                font-weight: 600;
                padding: 4px 10px;
            }
            QPushButton#capsulePillBtn:hover {
                color: #F8FAFC;
                border-color: rgba(0, 209, 255, 0.4);
            }
            QPushButton#capsulePillBtn:checked {
                background-color: rgba(0, 209, 255, 0.15);
                color: #00D1FF;
                border-color: #00D1FF;
            }
        """

        # 📎 Attachment Button
        self.attach_btn = QPushButton("📎")
        self.attach_btn.setObjectName("capsulePillBtn")
        self.attach_btn.setStyleSheet(pill_style)
        self.attach_btn.setToolTip("Attach files, code, or screenshots")
        self.attach_btn.setFixedSize(34, 32)
        self.attach_btn.setCursor(Qt.PointingHandCursor)
        self.attach_btn.clicked.connect(self._open_file_dialog)
        toolbar.addWidget(self.attach_btn)

        # 🌐 Web Search Dropdown Toggle
        self.web_btn = QPushButton("🌐 Web Search ⌄")
        self.web_btn.setObjectName("capsulePillBtn")
        self.web_btn.setStyleSheet(pill_style)
        self.web_btn.setCheckable(True)
        self.web_btn.setCursor(Qt.PointingHandCursor)
        self.web_btn.setToolTip("Toggle live web evidence extraction")
        toolbar.addWidget(self.web_btn)

        # 🎨 Image Generation Toggle (in-chat FLUX.1 generation)
        self.image_btn = QPushButton("🎨 Image Gen")
        self.image_btn.setObjectName("capsulePillBtn")
        self.image_btn.setStyleSheet(pill_style)
        self.image_btn.setCheckable(True)
        self.image_btn.setCursor(Qt.PointingHandCursor)
        self.image_btn.setToolTip("Generate images & artwork directly in chat with FLUX.1")
        self.image_btn.toggled.connect(self._on_image_mode_toggled)
        toolbar.addWidget(self.image_btn)

        # '+' Tool Button
        self.plus_tool_btn = QPushButton("＋")
        self.plus_tool_btn.setObjectName("capsulePillBtn")
        self.plus_tool_btn.setStyleSheet(pill_style)
        self.plus_tool_btn.setToolTip("Add AI models, files, or tools")
        self.plus_tool_btn.setFixedSize(34, 32)
        self.plus_tool_btn.setCursor(Qt.PointingHandCursor)
        self.plus_tool_btn.clicked.connect(self._open_plus_menu)
        toolbar.addWidget(self.plus_tool_btn)

        toolbar.addStretch()

        # Model Selector Button (triggers Searchable ModelSelectorPopup)
        self.current_model = "Auto Router"
        self.model_btn = QPushButton("⚡ Auto Router ▾")
        self.model_btn.setObjectName("capsulePillBtn")
        self.model_btn.setStyleSheet(pill_style + """
            QPushButton#capsulePillBtn {
                padding: 4px 12px;
                color: #00D1FF;
            }
        """)
        self.model_btn.setCursor(Qt.PointingHandCursor)
        self.model_btn.setToolTip("Select or search AI models")
        self.model_btn.clicked.connect(self._open_model_selector)
        toolbar.addWidget(self.model_btn)

        # 🎤 Voice Input Icon
        voice_btn = QPushButton("🎤")
        voice_btn.setObjectName("capsulePillBtn")
        voice_btn.setStyleSheet(pill_style)
        voice_btn.setFixedSize(34, 32)
        voice_btn.setToolTip("Voice dictation")
        voice_btn.setCursor(Qt.PointingHandCursor)
        toolbar.addWidget(voice_btn)

        # Circular Neon Cyan Send Button '↑'
        self.send_btn = QPushButton("↑")
        self.send_btn.setObjectName("capsuleSendBtn")
        self.send_btn.setStyleSheet("""
            QPushButton#capsuleSendBtn {
                background-color: #00D1FF;
                color: #0A0F14;
                border: none;
                border-radius: 18px;
                font-size: 17px;
                font-weight: 900;
            }
            QPushButton#capsuleSendBtn:hover {
                background-color: #00BBE6;
            }
        """)
        self.send_btn.setFixedSize(36, 36)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.clicked.connect(self._on_action_button_clicked)
        toolbar.addWidget(self.send_btn)

        capsule_layout.addLayout(toolbar)
        main_layout.addWidget(capsule)

        # 2. Footer Disclaimer
        footer_row = QHBoxLayout()
        footer_row.setAlignment(Qt.AlignCenter)
        footer_lbl = QLabel("Sage can make mistakes. Check important info. ⓘ")
        footer_lbl.setObjectName("footerDisclaimer")
        footer_row.addWidget(footer_lbl)

        main_layout.addLayout(footer_row)

    def _open_file_dialog(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Attach Files or Code",
            "",
            "Supported Files (*.py *.js *.ts *.html *.css *.json *.md *.txt *.csv *.sql *.png *.jpg *.jpeg *.webp);;Code Files (*.py *.js *.ts *.html *.css *.json *.md *.txt);;Images (*.png *.jpg *.jpeg *.webp);;All Files (*.*)"
        )
        for p in file_paths:
            self.add_attachment(p)

    def _handle_dropped_files(self, file_paths: list):
        for p in file_paths:
            self.add_attachment(p)

    def add_attachment(self, file_path: str):
        path = Path(file_path)
        if not path.is_file():
            return

        if any(a["path"] == str(path.resolve()) for a in self.attached_files):
            return

        size = path.stat().st_size
        suffix = path.suffix.lower()
        is_image = suffix in (".png", ".jpg", ".jpeg", ".webp")

        content = ""
        try:
            if is_image:
                with open(path, "rb") as f:
                    content = base64.b64encode(f.read()).decode("utf-8")
            else:
                if size <= 250000:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                else:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read(250000) + "\n... [Truncated due to size]"
        except Exception as e:
            content = f"Error reading file: {e}"

        item = {
            "path": str(path.resolve()),
            "name": path.name,
            "size": size,
            "is_image": is_image,
            "content": content
        }
        self.attached_files.append(item)

        chip = AttachmentChip(item["path"], item["name"], item["size"], item["is_image"], parent=self.attachments_widget)
        chip.removed.connect(self.remove_attachment)
        self.attachments_layout.addWidget(chip)
        self.attachments_widget.setVisible(True)

    def remove_attachment(self, file_path: str):
        self.attached_files = [a for a in self.attached_files if a["path"] != file_path]
        for i in reversed(range(self.attachments_layout.count())):
            item = self.attachments_layout.itemAt(i)
            w = item.widget()
            if w:
                w.setParent(None)

        for item in self.attached_files:
            chip = AttachmentChip(item["path"], item["name"], item["size"], item["is_image"], parent=self.attachments_widget)
            chip.removed.connect(self.remove_attachment)
            self.attachments_layout.addWidget(chip)

        self.attachments_widget.setVisible(len(self.attached_files) > 0)

    def clear_attachments(self):
        self.attached_files.clear()
        for i in reversed(range(self.attachments_layout.count())):
            item = self.attachments_layout.itemAt(i)
            w = item.widget()
            if w:
                w.setParent(None)
        self.attachments_widget.setVisible(False)

    def _on_image_mode_toggled(self, checked: bool):
        if checked:
            self._on_model_selected("image: Black Forest FLUX.1")
            self.text_input.setPlaceholderText("Describe the image or art you want to create (FLUX.1)...")
            cur_txt = self.text_input.toPlainText().strip()
            if not cur_txt:
                self.text_input.setPlainText("Generate an image of ")
                cursor = self.text_input.textCursor()
                cursor.movePosition(QTextCursor.End)
                self.text_input.setTextCursor(cursor)
            self.text_input.setFocus()
        else:
            self._on_model_selected("Auto Router")
            self.text_input.setPlaceholderText("Ask anything, attach code/files, or describe what you want to build...")

    def _handle_submit(self):
        if self._is_busy:
            return

        text = self.text_input.toPlainText().strip()
        if not text and not self.attached_files:
            return

        force_web = self.web_btn.isChecked()
        selected_model = self.current_model
        attachments = list(self.attached_files)

        if hasattr(self, "image_btn") and self.image_btn.isChecked():
            if not text.lower().startswith(("generate an image", "create a picture", "generate a photo", "generate image", "create image", "generate a picture")):
                text = f"Generate an image of {text}"
            self.image_btn.setChecked(False)

        self.text_input.clear()
        self.clear_attachments()
        self.submitted.emit(text, force_web, selected_model, attachments)

    def _on_action_button_clicked(self):
        if self._is_busy:
            self.cancelled.emit()
        else:
            self._handle_submit()

    def set_busy(self, is_busy: bool):
        self._is_busy = is_busy
        if is_busy:
            self.send_btn.setText("⏹")
            self.send_btn.setStyleSheet("background: #ff5c77; color: white; border-radius: 16px;")
        else:
            self.send_btn.setText("↑")
            self.send_btn.setStyleSheet("")
            self.text_input.setFocus()

    def set_input_text(self, text: str):
        self.text_input.setPlainText(text)
        self.text_input.setFocus()

    def _open_model_selector(self):
        from ui.components.model_selector_popup import ModelSelectorPopup
        popup = ModelSelectorPopup(current_model=self.current_model, parent=self)
        popup.model_selected.connect(self._on_model_selected)
        popup.manage_models_requested.connect(self.manage_models_requested.emit)
        popup.show_anchored(self.model_btn)

    def _on_model_selected(self, model_identifier: str):
        self.current_model = model_identifier
        self.model_btn.setText(self._format_model_btn_label(model_identifier))

    def _open_plus_menu(self):
        """Displays friendly quick-actions menu to add models, attach files, or toggle web search."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #111827;
                color: #F8FAFC;
                border: 1px solid #273449;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 7px 18px 7px 12px;
                border-radius: 5px;
                font-size: 12px;
                font-weight: 500;
            }
            QMenu::item:selected {
                background-color: rgba(0, 209, 255, 0.15);
                color: #00D1FF;
            }
        """)

        add_ai_act = menu.addAction("✨  Add / Connect AI Models...")
        add_ai_act.setToolTip("Open dialog to add free AI models, API keys, or offline Ollama")
        add_ai_act.triggered.connect(self.manage_models_requested.emit)

        pic_act = menu.addAction("🎨  Create Picture / Image (Black Forest FLUX.1)...")
        pic_act.setToolTip("Generate an image or artwork using Black Forest Labs FLUX.1")
        pic_act.triggered.connect(self._start_create_picture)

        attach_act = menu.addAction("📎  Attach Files or Images...")
        attach_act.triggered.connect(self._open_file_dialog)

        web_act = menu.addAction("🌐  Toggle Live Web Search Evidence")
        web_act.triggered.connect(lambda: self.web_btn.setChecked(not self.web_btn.isChecked()))

        menu.exec(self.plus_tool_btn.mapToGlobal(self.plus_tool_btn.rect().topLeft()))

    def _start_create_picture(self):
        """Switches active model to Create Picture and focuses prompt input."""
        if hasattr(self, "image_btn"):
            self.image_btn.setChecked(True)
        else:
            self._on_model_selected("image: Black Forest FLUX.1")
            self.text_input.setPlainText("Generate an image of ")
            cursor = self.text_input.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.text_input.setTextCursor(cursor)
            self.text_input.setFocus()

    def _format_model_btn_label(self, model_identifier: str) -> str:
        if not model_identifier or "auto" in model_identifier.lower():
            return "⚡ Auto Router ▾"
        if any(k in model_identifier.lower() for k in ("picture", "flux", "diffusion", "image")):
            return "🎨 Create Picture ▾"
        clean = model_identifier.split(":")[-1].strip()
        if "/" in clean:
            clean = clean.split("/")[-1]
        if len(clean) > 20:
            clean = clean[:18] + "..."
        return f"{clean} ▾"

    def refresh_models(self):
        """Refreshes button label with current model selection."""
        if hasattr(self, "model_btn"):
            self.model_btn.setText(self._format_model_btn_label(self.current_model))

    @property
    def model_combo(self):
        """Backwards compatibility helper."""
        class _MockCombo:
            def __init__(self, parent):
                self.parent = parent
            def currentText(self):
                return self.parent.current_model
        return _MockCombo(self)
