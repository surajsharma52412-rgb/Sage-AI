"""
Human-in-the-Loop Permission Dialog for Sage AI.
Ensures zero unapproved external actions (sending emails, modifying critical files, executing commands).
"""
from typing import Dict, Any, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTextEdit, QWidget
)
from PySide6.QtCore import Qt


class PermissionDialog(QDialog):
    """
    Mandatory interactive authorization modal before performing sensitive external actions.
    Displays action details, recipient, subject, and editable preview.
    """

    def __init__(
        self,
        action_type: str,
        target: str,
        subject: str,
        body: str,
        details: Optional[Dict[str, Any]] = None,
        parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Sage AI - Action Authorization Required")
        self.resize(560, 480)
        self.setModal(True)

        self.action_type = action_type
        self.target = target
        self.subject = subject
        self.body = body
        self.details = details or {}
        self.approved = False
        self.final_body = body

        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("QDialog { background-color: #0A0F14; }")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(22, 20, 22, 20)
        main_layout.setSpacing(14)

        # 1. Header
        header = QHBoxLayout()
        warn_icon = QLabel("🛡️")
        warn_icon.setStyleSheet("font-size: 24px;")
        header.addWidget(warn_icon)

        title_col = QVBoxLayout()
        title_lbl = QLabel("Review & Authorize Action")
        title_lbl.setStyleSheet("color: #F8FAFC; font-size: 15px; font-weight: 700;")
        title_col.addWidget(title_lbl)

        sub_lbl = QLabel("Sage AI prepared this action for you. Please review and approve before it proceeds.")
        sub_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
        title_col.addWidget(sub_lbl)

        header.addLayout(title_col, 1)
        main_layout.addLayout(header)

        # 2. Action Overview Card
        card = QFrame()
        card.setObjectName("permOverviewCard")
        card.setStyleSheet("""
            #permOverviewCard {
                background-color: #162033;
                border: 1px solid rgba(255, 184, 77, 0.35);
                border-radius: 10px;
            }
            #permOverviewCard QLabel {
                border: none;
                background: transparent;
                padding: 0px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(6)

        row1 = QHBoxLayout()
        act_lbl = QLabel("Action:")
        act_lbl.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 600; min-width: 65px;")
        act_val = QLabel(self.action_type)
        act_val.setStyleSheet("color: #ffb84d; font-size: 13px; font-weight: 700;")
        row1.addWidget(act_lbl)
        row1.addWidget(act_val, 1)
        card_layout.addLayout(row1)

        row2 = QHBoxLayout()
        tgt_lbl = QLabel("Target:")
        tgt_lbl.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 600; min-width: 65px;")
        tgt_val = QLabel(self.target)
        tgt_val.setStyleSheet("color: #00D1FF; font-size: 13px; font-weight: 600;")
        row2.addWidget(tgt_lbl)
        row2.addWidget(tgt_val, 1)
        card_layout.addLayout(row2)

        if self.subject:
            row3 = QHBoxLayout()
            sub_title_lbl = QLabel("Subject:")
            sub_title_lbl.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 600; min-width: 65px;")
            sub_val = QLabel(self.subject)
            sub_val.setStyleSheet("color: #F8FAFC; font-size: 13px; font-weight: 600;")
            row3.addWidget(sub_title_lbl)
            row3.addWidget(sub_val, 1)
            card_layout.addLayout(row3)

        main_layout.addWidget(card)

        # 3. Payload / Body Preview (Editable)
        preview_lbl = QLabel("Proposed Message / Action Content (Review & edit if needed):")
        preview_lbl.setStyleSheet("color: #a0aec0; font-size: 11px; font-weight: 600;")
        main_layout.addWidget(preview_lbl)

        self.body_edit = QTextEdit()
        self.body_edit.setPlainText(self.body)
        self.body_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0A0F14;
                color: #e2e8f0;
                border: 1px solid rgba(0, 209, 255, 0.25);
                border-radius: 8px;
                padding: 10px;
                font-family: sans-serif;
                font-size: 12px;
                line-height: 1.4;
            }
            QTextEdit:focus {
                border: 1px solid #00D1FF;
            }
        """)
        main_layout.addWidget(self.body_edit, 1)

        # 4. Button Bar: Deny vs Authorize
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(12)

        deny_btn = QPushButton("❌ Deny / Discard")
        deny_btn.setCursor(Qt.PointingHandCursor)
        deny_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(244, 63, 94, 0.12);
                color: #f43f5e;
                border: 1px solid rgba(244, 63, 94, 0.35);
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(244, 63, 94, 0.25);
            }
        """)
        deny_btn.clicked.connect(self._on_deny)
        btn_bar.addWidget(deny_btn)

        btn_bar.addStretch()

        auth_btn = QPushButton("✅ Authorize & Send")
        auth_btn.setCursor(Qt.PointingHandCursor)
        auth_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
                color: #04120c;
                border: none;
                border-radius: 8px;
                padding: 8px 22px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #25fbd1, stop:1 #10b981);
            }
        """)
        auth_btn.clicked.connect(self._on_authorize)
        btn_bar.addWidget(auth_btn)

        main_layout.addLayout(btn_bar)

    def _on_authorize(self):
        self.approved = True
        self.final_body = self.body_edit.toPlainText().strip()
        self.accept()

    def _on_deny(self):
        self.approved = False
        self.reject()
