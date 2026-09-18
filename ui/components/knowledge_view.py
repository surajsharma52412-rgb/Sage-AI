"""
Knowledge & Memory View for Sage Multi-Agentic AI Architecture.
Provides an interactive center where users can:
- Teach the model persistent rules, preferences, bio, and architectural guidelines
- Tell the model what to remember across all chats and specialized agents
- Search and manage vector memory and knowledge base entries
"""
from datetime import datetime
from typing import List, Dict, Any, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QComboBox, QScrollArea, QFrame,
    QSizePolicy, QApplication
)
from PySide6.QtCore import Qt, Signal

from engine.orchestrator.memory_manager import MemoryManager
from engine.shared_resources.vector_db import get_vector_db
from engine.shared_resources.knowledge_base import get_knowledge_base


class MemoryCard(QFrame):
    """Card representing a single learned memory or knowledge entry."""

    deleted = Signal(str)   # mem_id
    copied = Signal(str)    # content

    CATEGORY_COLORS = {
        "directive": ("#a855f7", "rgba(168, 85, 247, 0.15)"),   # Purple
        "rule": ("#a855f7", "rgba(168, 85, 247, 0.15)"),
        "preference": ("#00D1FF", "rgba(0, 209, 255, 0.15)"), # Emerald
        "architecture": ("#00d2ff", "rgba(0, 210, 255, 0.15)"), # Cyan
        "fact": ("#eab308", "rgba(234, 179, 8, 0.15)"),        # Gold
        "general": ("#94A3B8", "rgba(139, 149, 173, 0.15)"),   # Slate
    }

    def __init__(self, item: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.item = item
        self.mem_id = item.get("id", item.get("key", ""))
        self.setObjectName("memoryCard")
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QFrame#memoryCard {
                background-color: #162033;
                border: 1px solid rgba(0, 209, 255, 0.15);
                border-radius: 12px;
            }
            QFrame#memoryCard:hover {
                border-color: rgba(0, 209, 255, 0.35);
                background-color: #162033;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Header row: category badge, title, and action buttons
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        # Category Pill
        tags = self.item.get("tags", "")
        cat = "general"
        if isinstance(tags, str):
            for potential in ["directive", "rule", "preference", "architecture", "fact"]:
                if potential in tags.lower():
                    cat = potential
                    break
        elif isinstance(tags, list):
            for potential in ["directive", "rule", "preference", "architecture", "fact"]:
                if potential in [str(t).lower() for t in tags]:
                    cat = potential
                    break

        cat_col, cat_bg = self.CATEGORY_COLORS.get(cat, self.CATEGORY_COLORS["general"])
        cat_badge = QLabel(cat.upper())
        cat_badge.setStyleSheet(f"""
            color: {cat_col};
            background-color: {cat_bg};
            border: 1px solid {cat_col}44;
            border-radius: 6px;
            font-size: 9px;
            font-weight: 800;
            padding: 2px 8px;
            letter-spacing: 0.5px;
        """)
        header_row.addWidget(cat_badge)

        # Title
        raw_title = self.item.get("title", "Learned Memory")
        title_lbl = QLabel(raw_title)
        title_lbl.setStyleSheet("color: #F8FAFC; font-size: 13px; font-weight: 700;")
        header_row.addWidget(title_lbl, 1)

        # Copy Button
        copy_btn = QPushButton("📋 Copy")
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setToolTip("Copy memory content to clipboard")
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.05);
                color: #94A3B8;
                border: 1px solid #273449;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
                padding: 3px 8px;
            }
            QPushButton:hover {
                color: #00D1FF;
                border-color: rgba(0, 209, 255, 0.3);
            }
        """)
        copy_btn.clicked.connect(self._copy_content)
        header_row.addWidget(copy_btn)

        # Delete Button
        del_btn = QPushButton("🗑 Forget")
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setToolTip("Remove this memory from model's knowledge")
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(244, 63, 94, 0.08);
                color: #f43f5e;
                border: 1px solid rgba(244, 63, 94, 0.2);
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
                padding: 3px 8px;
            }
            QPushButton:hover {
                background-color: rgba(244, 63, 94, 0.22);
            }
        """)
        del_btn.clicked.connect(lambda: self.deleted.emit(self.mem_id))
        header_row.addWidget(del_btn)

        layout.addLayout(header_row)

        # Content
        content_text = self.item.get("content", "")
        content_lbl = QLabel(content_text)
        content_lbl.setWordWrap(True)
        content_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        content_lbl.setStyleSheet("color: #94A3B8; font-size: 12px; line-height: 1.45;")
        layout.addWidget(content_lbl)

        # Footer tags
        if tags:
            tag_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
            footer_lbl = QLabel(f"🏷 Tags: {tag_str}")
            footer_lbl.setStyleSheet("color: #626c85; font-size: 10px; font-weight: 500;")
            layout.addWidget(footer_lbl)

    def _copy_content(self):
        text = self.item.get("content", "")
        cb = QApplication.clipboard()
        if cb:
            cb.setText(text)
        self.copied.emit(text)


class KnowledgeView(QWidget):
    """Full-featured interactive Knowledge & Memory Center for Sage AI."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("knowledgeView")
        self.memory_manager = MemoryManager()
        self.vector_db = get_vector_db()
        self.knowledge_base = get_knowledge_base()

        self._current_filter = "all"
        self._init_ui()
        self.refresh_memories()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 20, 28, 20)
        main_layout.setSpacing(16)

        # 1. Header Section
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        header_col = QVBoxLayout()
        header_col.setSpacing(4)
        title_lbl = QLabel("📖  Knowledge & Memory Center")
        title_lbl.setStyleSheet("color: #F8FAFC; font-size: 22px; font-weight: 800; letter-spacing: -0.3px;")
        header_col.addWidget(title_lbl)

        subtitle_lbl = QLabel("Teach the model what to remember, specify custom rules, and manage persistent agent intelligence.")
        subtitle_lbl.setStyleSheet("color: #94A3B8; font-size: 13px;")
        header_col.addWidget(subtitle_lbl)
        header_row.addLayout(header_col, 1)

        # Stat Badges
        self.stat_memories = QLabel("🧠 0 Memories")
        self.stat_memories.setObjectName("statMemories")
        header_row.addWidget(self.stat_memories)

        self.stat_vectors = QLabel("⚡ 0 Vector Embeddings")
        self.stat_vectors.setObjectName("statVectors")
        header_row.addWidget(self.stat_vectors)

        main_layout.addLayout(header_row)

        # 2. Main Scroll Area for Teach Form and Memory List
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: transparent;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(0, 209, 255, 0.2);
                border-radius: 3px;
                min-height: 25px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #00D1FF;
            }
        """)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 16)
        c_layout.setSpacing(18)

        # --- SECTION A: "Teach Model / Tell Model to Remember" Form ---
        self.teach_frame = QFrame()
        self.teach_frame.setObjectName("teachFrame")
        self.teach_frame.setMinimumHeight(260)
        t_layout = QVBoxLayout(self.teach_frame)
        t_layout.setContentsMargins(18, 16, 18, 16)
        t_layout.setSpacing(10)

        # Section Header
        t_header = QHBoxLayout()
        self.t_title = QLabel("✨  Teach Model / Tell Model to Remember")
        self.t_title.setObjectName("teachTitle")
        t_header.addWidget(self.t_title)
        t_header.addStretch()

        preset_lbl = QLabel("Presets:")
        preset_lbl.setStyleSheet("color: #626c85; font-size: 11px; font-weight: 700;")
        t_header.addWidget(preset_lbl)

        # Quick Preset Buttons
        presets = [
            ("📐 Coding", "Coding Standards", "directive", "Always write clean Python code with complete type hints and docstrings. Prefer modular functions and clear variable names.", "code,python,typing"),
            ("👤 Persona", "User Identity & Role", "preference", "User is Suraj Sharma, Lead AI Systems Architect. Prefers concise, direct, and technical explanations.", "user,profile,bio"),
            ("🚀 Architecture", "Sage Architecture Guidelines", "architecture", "Sage AI uses a 5-component Core Brain Orchestrator with 7 Specialized Agents (Research, Coding, Media, Data, Content, Execution, Planning).", "sage,architecture,agents"),
            ("⚡ Tone", "Preferred Response Style", "directive", "Format outputs cleanly using GitHub markdown, bullet points, and code blocks. Avoid unnecessary conversational filler.", "tone,formatting,style"),
        ]

        for p_label, p_title, p_cat, p_content, p_tags in presets:
            btn = QPushButton(p_label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.05);
                    color: #94A3B8;
                    border: 1px solid #273449;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 3px 8px;
                }
                QPushButton:hover {
                    color: #00D1FF;
                    border-color: rgba(0, 209, 255, 0.3);
                }
            """)
            btn.clicked.connect(lambda checked=False, t=p_title, c=p_cat, cnt=p_content, tg=p_tags: self._apply_preset(t, c, cnt, tg))
            t_header.addWidget(btn)

        t_layout.addLayout(t_header)

        # Row 1: Title input & Category combo
        input_row1 = QHBoxLayout()
        input_row1.setSpacing(12)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Topic / Subject (e.g., Python Code Guidelines, Project Database Schema...)")
        self.title_input.setStyleSheet("""
            QLineEdit {
                background-color: #162033;
                color: #F8FAFC;
                border: 1px solid #273449;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #00D1FF;
            }
        """)
        input_row1.addWidget(self.title_input, 2)

        self.category_combo = QComboBox()
        self.category_combo.addItem("Directive / Rule", "directive")
        self.category_combo.addItem("Personal Fact / Preference", "preference")
        self.category_combo.addItem("Project Architecture", "architecture")
        self.category_combo.addItem("Reference / Cheatsheet", "fact")
        self.category_combo.setStyleSheet("""
            QComboBox {
                background-color: #162033;
                color: #F8FAFC;
                border: 1px solid #273449;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                font-weight: 600;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #0A0F14;
                color: #F8FAFC;
                selection-background-color: #00D1FF;
                selection-color: #0A0F14;
                border: 1px solid rgba(0, 209, 255, 0.2);
            }
        """)
        input_row1.addWidget(self.category_combo, 1)

        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("Tags (comma separated, e.g., python, styling, bio)")
        self.tags_input.setStyleSheet("""
            QLineEdit {
                background-color: #162033;
                color: #F8FAFC;
                border: 1px solid #273449;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #00D1FF;
            }
        """)
        input_row1.addWidget(self.tags_input, 1)

        t_layout.addLayout(input_row1)

        # Content Textarea
        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText("Enter the exact rules, instructions, or knowledge you want Sage AI to permanently remember across all agents...")
        self.content_edit.setFixedHeight(75)
        self.content_edit.setStyleSheet("""
            QTextEdit {
                background-color: #162033;
                color: #F8FAFC;
                border: 1px solid #273449;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                line-height: 1.4;
            }
            QTextEdit:focus {
                border-color: #00D1FF;
            }
        """)
        t_layout.addWidget(self.content_edit)

        # Submit & Status Row
        submit_row = QHBoxLayout()
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #00D1FF; font-size: 12px; font-weight: 600;")
        submit_row.addWidget(self.status_lbl, 1)

        self.teach_btn = QPushButton("✨  Teach Model (Remember Fact)")
        self.teach_btn.setObjectName("teachBtn")
        self.teach_btn.setMinimumHeight(36)
        self.teach_btn.setMinimumWidth(250)
        self.teach_btn.setCursor(Qt.PointingHandCursor)
        self.teach_btn.clicked.connect(self._handle_teach_submit)
        submit_row.addWidget(self.teach_btn)

        t_layout.addLayout(submit_row)
        c_layout.addWidget(self.teach_frame)

        # --- SECTION B: "Learned Memories & Knowledge Base" Explorer ---
        list_header_row = QHBoxLayout()
        list_header_row.setSpacing(12)

        list_title = QLabel("📚  Learned Memories & System Knowledge")
        list_title.setStyleSheet("color: #F8FAFC; font-size: 16px; font-weight: 700;")
        list_header_row.addWidget(list_title)
        list_header_row.addStretch()

        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍  Search memories by keyword or semantic query...")
        self.search_input.setFixedWidth(300)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #162033;
                color: #F8FAFC;
                border: 1px solid #273449;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #00D1FF;
            }
        """)
        self.search_input.textChanged.connect(self._on_search_changed)
        list_header_row.addWidget(self.search_input)

        c_layout.addLayout(list_header_row)

        # Filter Chips
        chips_row = QHBoxLayout()
        chips_row.setSpacing(8)

        filters = [
            ("all", "All"),
            ("directive", "Directives & Rules"),
            ("preference", "Preferences & Persona"),
            ("architecture", "Architecture"),
            ("fact", "Reference Notes"),
        ]

        self._filter_buttons = {}
        for f_key, f_label in filters:
            btn = QPushButton(f_label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            btn.setChecked(f_key == "all")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.04);
                    color: #94A3B8;
                    border: 1px solid #273449;
                    border-radius: 14px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 4px 12px;
                }
                QPushButton:hover {
                    color: #F8FAFC;
                    border-color: rgba(0, 209, 255, 0.3);
                }
                QPushButton:checked {
                    background-color: rgba(0, 209, 255, 0.15);
                    color: #00D1FF;
                    border-color: #00D1FF;
                    font-weight: 700;
                }
            """)
            btn.clicked.connect(lambda checked=False, k=f_key: self._set_filter(k))
            self._filter_buttons[f_key] = btn
            chips_row.addWidget(btn)

        chips_row.addStretch()
        c_layout.addLayout(chips_row)

        # Cards container
        self.cards_layout = QVBoxLayout()
        self.cards_layout.setSpacing(10)
        c_layout.addLayout(self.cards_layout)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _apply_preset(self, title: str, category: str, content: str, tags: str):
        self.title_input.setText(title)
        idx = self.category_combo.findData(category)
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        self.content_edit.setPlainText(content)
        self.tags_input.setText(tags)
        self.status_lbl.setText("Preset loaded. Click 'Teach Model' to save.")

    def _handle_teach_submit(self):
        title = self.title_input.text().strip()
        content = self.content_edit.toPlainText().strip()
        category = self.category_combo.currentData()
        tags = self.tags_input.text().strip()

        if not title:
            self.status_lbl.setText("⚠️ Please provide a title or topic.")
            self.status_lbl.setStyleSheet("color: #ff5c77; font-size: 12px; font-weight: 600;")
            return
        if not content:
            self.status_lbl.setText("⚠️ Please provide memory content to teach.")
            self.status_lbl.setStyleSheet("color: #ff5c77; font-size: 12px; font-weight: 600;")
            return

        # Save to Memory Manager
        res = self.memory_manager.teach_memory(
            title=title,
            content=content,
            category=category,
            tags=tags
        )

        # Clear form
        self.title_input.clear()
        self.content_edit.clear()
        self.tags_input.clear()

        self.status_lbl.setText(f"✓ Learned: '{res['title']}'! Available across all agents.")
        self.status_lbl.setStyleSheet("color: #00D1FF; font-size: 12px; font-weight: 600;")

        self.refresh_memories()

    def _set_filter(self, filter_key: str):
        self._current_filter = filter_key
        for k, btn in self._filter_buttons.items():
            btn.setChecked(k == filter_key)
        self.refresh_memories()

    def _on_search_changed(self, text: str):
        self.refresh_memories()

    def refresh_memories(self):
        """Reloads and displays memories matching current filter and query."""
        # Clear existing cards
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        all_memories = self.memory_manager.list_all_memories()
        query = self.search_input.text().strip().lower()

        # Update stats
        v_docs = self.vector_db.list_all_documents()
        kb_entries = self.knowledge_base.list_entries()
        self.stat_memories.setText(f"🧠 {len(all_memories)} Memories")
        self.stat_vectors.setText(f"⚡ {len(v_docs)} Vector Embeddings")

        displayed_count = 0
        for m in all_memories:
            tags = m.get("tags", "")
            title = m.get("title", "").lower()
            content = m.get("content", "").lower()

            # Filter by Category
            if self._current_filter != "all":
                t_str = ",".join(tags).lower() if isinstance(tags, list) else str(tags).lower()
                if self._current_filter not in t_str and self._current_filter not in title:
                    continue

            # Filter by Search Query
            if query:
                t_str = ",".join(tags).lower() if isinstance(tags, list) else str(tags).lower()
                if query not in title and query not in content and query not in t_str:
                    continue

            card = MemoryCard(m, self)
            card.deleted.connect(self._handle_delete_memory)
            card.copied.connect(lambda: self.status_lbl.setText("✓ Copied memory to clipboard!"))
            self.cards_layout.addWidget(card)
            displayed_count += 1

        if displayed_count == 0:
            empty_lbl = QLabel("No memories found matching your search. Use the form above to teach the model new facts!")
            empty_lbl.setStyleSheet("color: #626c85; font-size: 13px; padding: 20px; font-style: italic;")
            empty_lbl.setAlignment(Qt.AlignCenter)
            self.cards_layout.addWidget(empty_lbl)

    def _handle_delete_memory(self, mem_id: str):
        self.memory_manager.forget_memory(mem_id)
        self.status_lbl.setText("✓ Memory removed from model.")
        self.status_lbl.setStyleSheet("color: #00D1FF; font-size: 12px; font-weight: 600;")
        self.refresh_memories()

    def apply_theme(self, pal: Dict[str, str]):
        """Dynamically applies active theme palette to KnowledgeView components."""
        primary = pal.get("primary", "#00D1FF")
        primary_hover = pal.get("primary_hover", "#00BBE6")
        primary_dark = pal.get("primary_dark", "#008BB3")
        primary_rgba_12 = pal.get("primary_rgba_12", "rgba(0, 209, 255, 0.12)")
        primary_rgba_30 = pal.get("primary_rgba_30", "rgba(0, 209, 255, 0.30)")
        bg_main = pal.get("bg_main", "#0A0F14")
        bg_card = pal.get("bg_card", "#162033")

        self.teach_frame.setStyleSheet(f"""
            QFrame#teachFrame {{
                background-color: {bg_card};
                border: 1.5px solid {primary_rgba_30};
                border-radius: 14px;
            }}
        """)
        self.t_title.setStyleSheet(f"color: {primary}; font-size: 15px; font-weight: 800; letter-spacing: 0.5px;")
        self.stat_memories.setStyleSheet(f"background: {primary_rgba_12}; color: {primary}; border: 1px solid {primary_rgba_30}; border-radius: 8px; padding: 6px 12px; font-weight: 700; font-size: 12px;")
        self.teach_btn.setStyleSheet(f"""
            QPushButton#teachBtn {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {primary}, stop:1 {primary_dark});
                color: {bg_main};
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 700;
                padding: 8px 18px;
            }}
            QPushButton#teachBtn:hover {{
                background: {primary_hover};
            }}
        """)
