# -*- coding: utf-8 -*-
"""
Anki UI Module for KOHighlights

This module provides the GUI components for Anki integration:
- AnkiPrefsWidget: Preferences widget for Anki settings
- AnkiExportDialog: Dialog for exporting highlights to Anki
- FieldMappingDialog: Dialog for configuring field mappings
"""

from boot_config import *
from boot_config import _
import json
from functools import partial
from typing import Optional, List, Dict, Any

if QT5:
    from PySide2.QtCore import Qt, QTimer, Signal, Slot, QThread
    from PySide2.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout, 
                                   QGridLayout, QGroupBox, QLabel, QLineEdit,
                                   QComboBox, QPushButton, QCheckBox, QListWidget,
                                   QListWidgetItem, QProgressBar, QTextEdit,
                                   QDialogButtonBox, QFrame, QMessageBox, QSpacerItem,
                                   QSizePolicy, QApplication)
    from PySide2.QtGui import QIcon
else:  # Qt6
    from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread
    from PySide6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout,
                                   QGridLayout, QGroupBox, QLabel, QLineEdit,
                                   QComboBox, QPushButton, QCheckBox, QListWidget,
                                   QListWidgetItem, QProgressBar, QTextEdit,
                                   QDialogButtonBox, QFrame, QMessageBox, QSpacerItem,
                                   QSizePolicy, QApplication)
    from PySide6.QtGui import QIcon

from anki_connect import (AnkiConnect, AnkiConnectError, get_anki_connect,
                          DEFAULT_ANKI_URL, DEFAULT_NOTE_TYPE, DEFAULT_FIELD_MAPPINGS)

__author__ = "KOHighlights"


class AnkiExportThread(QThread):
    """Thread for exporting highlights to Anki without blocking the UI."""
    
    progress = Signal(int, int)  # current, total
    finished_export = Signal(int, int, list)  # success, fail, errors
    error = Signal(str)
    
    def __init__(self, anki: AnkiConnect, deck_name: str, model_name: str,
                 highlights: List[Dict], field_mapping: Dict, tags: List[str],
                 allow_duplicate: bool, create_subdecks: bool, parent=None):
        super().__init__(parent)
        self.anki = anki
        self.deck_name = deck_name
        self.model_name = model_name
        self.highlights = highlights
        self.field_mapping = field_mapping
        self.tags = tags
        self.allow_duplicate = allow_duplicate
        self.create_subdecks = create_subdecks
    
    def run(self):
        try:
            success, fail, errors = self.anki.bulk_add_highlights(
                self.deck_name,
                self.model_name,
                self.highlights,
                self.field_mapping,
                self.tags,
                self.allow_duplicate,
                lambda current, total: self.progress.emit(current, total)
            )
            self.finished_export.emit(success, fail, errors)
        except AnkiConnectError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Unexpected error: {str(e)}")


class AnkiPrefsWidget(QWidget):
    """
    Widget for Anki preferences in the settings dialog.
    
    Provides configuration for:
    - AnkiConnect URL and connection status
    - Default parent deck
    - Default note type
    - Field mappings
    - Export options
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.base = parent
        self.anki = None
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Connection Group
        conn_group = QGroupBox(_("Connection"))
        conn_layout = QGridLayout(conn_group)
        
        conn_layout.addWidget(QLabel(_("AnkiConnect URL:")), 0, 0)
        self.url_edit = QLineEdit(DEFAULT_ANKI_URL)
        self.url_edit.setPlaceholderText(DEFAULT_ANKI_URL)
        conn_layout.addWidget(self.url_edit, 0, 1)
        
        status_frame = QFrame()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(6, 6, 6, 6)
        
        self.status_icon = QLabel("●")
        self.status_icon.setStyleSheet("color: gray;")
        status_layout.addWidget(self.status_icon)
        
        self.status_label = QLabel(_("Not connected"))
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        self.test_btn = QPushButton(_("Test Connection"))
        self.test_btn.setToolTip(_("Test the connection to Anki"))
        status_layout.addWidget(self.test_btn)
        
        conn_layout.addWidget(status_frame, 1, 0, 1, 2)
        layout.addWidget(conn_group)
        
        # Deck Settings Group
        deck_group = QGroupBox(_("Deck Settings"))
        deck_layout = QGridLayout(deck_group)
        
        deck_layout.addWidget(QLabel(_("Parent Deck:")), 0, 0)
        self.parent_deck_combo = QComboBox()
        self.parent_deck_combo.setEditable(True)
        self.parent_deck_combo.setToolTip(_("Select or type the parent deck name"))
        deck_layout.addWidget(self.parent_deck_combo, 0, 1)
        
        self.refresh_decks_btn = QPushButton("↻")
        self.refresh_decks_btn.setMaximumWidth(30)
        self.refresh_decks_btn.setToolTip(_("Refresh deck list from Anki"))
        deck_layout.addWidget(self.refresh_decks_btn, 0, 2)
        
        self.create_subdecks_chk = QCheckBox(_("Create subdecks for each book"))
        self.create_subdecks_chk.setChecked(True)
        self.create_subdecks_chk.setToolTip(_("Each book will have its own subdeck"))
        deck_layout.addWidget(self.create_subdecks_chk, 1, 0, 1, 3)
        
        layout.addWidget(deck_group)
        
        # Note Type Settings Group
        note_group = QGroupBox(_("Note Type Settings"))
        note_layout = QGridLayout(note_group)
        
        note_layout.addWidget(QLabel(_("Default Note Type:")), 0, 0)
        self.note_type_combo = QComboBox()
        self.note_type_combo.setToolTip(_("Select the default note type for new cards"))
        note_layout.addWidget(self.note_type_combo, 0, 1)
        
        self.refresh_models_btn = QPushButton("↻")
        self.refresh_models_btn.setMaximumWidth(30)
        self.refresh_models_btn.setToolTip(_("Refresh note type list from Anki"))
        note_layout.addWidget(self.refresh_models_btn, 0, 2)
        
        self.configure_fields_btn = QPushButton(_("Configure Field Mappings..."))
        self.configure_fields_btn.setToolTip(_("Configure how highlight data maps to note fields"))
        note_layout.addWidget(self.configure_fields_btn, 1, 0, 1, 3)
        
        layout.addWidget(note_group)
        
        # Export Options Group
        options_group = QGroupBox(_("Export Options"))
        options_layout = QVBoxLayout(options_group)
        
        self.allow_duplicates_chk = QCheckBox(_("Allow duplicate notes"))
        self.allow_duplicates_chk.setToolTip(_("When disabled, identical notes will be skipped"))
        options_layout.addWidget(self.allow_duplicates_chk)
        
        self.add_tags_chk = QCheckBox(_("Add tags to notes"))
        self.add_tags_chk.setChecked(True)
        self.add_tags_chk.setToolTip(_("Add book title and chapter as tags"))
        options_layout.addWidget(self.add_tags_chk)
        
        self.include_chapter_chk = QCheckBox(_("Include chapter in cards"))
        self.include_chapter_chk.setChecked(True)
        options_layout.addWidget(self.include_chapter_chk)
        
        self.include_page_chk = QCheckBox(_("Include page number in cards"))
        self.include_page_chk.setChecked(True)
        options_layout.addWidget(self.include_page_chk)
        
        self.include_date_chk = QCheckBox(_("Include highlight date in cards"))
        options_layout.addWidget(self.include_date_chk)
        
        self.show_export_dialog_chk = QCheckBox(_("Always show export dialog before sending"))
        self.show_export_dialog_chk.setChecked(True)
        self.show_export_dialog_chk.setToolTip(_("Show a dialog with options each time you export"))
        options_layout.addWidget(self.show_export_dialog_chk)
        
        layout.addWidget(options_group)
        
        # Add stretch at the end
        layout.addStretch()
    
    def _connect_signals(self):
        """Connect signals to slots."""
        self.test_btn.clicked.connect(self.test_connection)
        self.refresh_decks_btn.clicked.connect(self.refresh_decks)
        self.refresh_models_btn.clicked.connect(self.refresh_note_types)
        self.configure_fields_btn.clicked.connect(self.configure_field_mappings)
        self.note_type_combo.currentTextChanged.connect(self.on_note_type_changed)
    
    def get_anki(self) -> Optional[AnkiConnect]:
        """Get or create AnkiConnect instance."""
        url = self.url_edit.text() or DEFAULT_ANKI_URL
        if self.anki is None or self.anki.url != url:
            self.anki = AnkiConnect(url)
        return self.anki
    
    @Slot()
    def test_connection(self):
        """Test the connection to Anki."""
        self.test_btn.setEnabled(False)
        self.status_label.setText(_("Connecting..."))
        self.status_icon.setStyleSheet("color: orange;")
        QApplication.processEvents()
        
        try:
            anki = self.get_anki()
            success, message = anki.test_connection()
            
            if success:
                self.status_icon.setStyleSheet("color: green;")
                self.status_label.setText(message)
                # Auto-refresh decks and note types
                self.refresh_decks()
                self.refresh_note_types()
            else:
                self.status_icon.setStyleSheet("color: red;")
                self.status_label.setText(_("Connection failed"))
        except Exception as e:
            self.status_icon.setStyleSheet("color: red;")
            self.status_label.setText(str(e)[:50] + "..." if len(str(e)) > 50 else str(e))
        
        self.test_btn.setEnabled(True)
    
    @Slot()
    def refresh_decks(self):
        """Refresh the list of decks from Anki."""
        try:
            anki = self.get_anki()
            decks = anki.get_deck_names(force_refresh=True)
            
            current = self.parent_deck_combo.currentText()
            self.parent_deck_combo.clear()
            self.parent_deck_combo.addItem("KOHighlights")  # Default parent deck
            self.parent_deck_combo.addItems(sorted(decks))
            
            # Restore previous selection if it exists
            idx = self.parent_deck_combo.findText(current)
            if idx >= 0:
                self.parent_deck_combo.setCurrentIndex(idx)
            else:
                self.parent_deck_combo.setCurrentIndex(0)
        except AnkiConnectError as e:
            self.status_label.setText(_("Failed to get decks"))
    
    @Slot()
    def refresh_note_types(self):
        """Refresh the list of note types from Anki."""
        try:
            anki = self.get_anki()
            models = anki.get_model_names(force_refresh=True)
            
            current = self.note_type_combo.currentText()
            self.note_type_combo.clear()
            self.note_type_combo.addItems(sorted(models))
            
            # Try to select Basic or previous selection
            idx = self.note_type_combo.findText(current)
            if idx < 0:
                idx = self.note_type_combo.findText(DEFAULT_NOTE_TYPE)
            if idx >= 0:
                self.note_type_combo.setCurrentIndex(idx)
        except AnkiConnectError as e:
            self.status_label.setText(_("Failed to get note types"))
    
    @Slot(str)
    def on_note_type_changed(self, model_name: str):
        """Handle note type selection change."""
        # Could auto-update field mappings preview here
        pass
    
    @Slot()
    def configure_field_mappings(self):
        """Open the field mapping configuration dialog."""
        dialog = FieldMappingDialog(self.get_anki(), self.get_settings(), self)
        if QT6:  # QT6 requires exec() instead of exec_()
            dialog.exec_ = getattr(dialog, "exec")
        if dialog.exec_():
            # Get updated mappings from dialog
            self._field_mappings = dialog.get_field_mappings()
    
    def get_settings(self) -> Dict:
        """Get the current Anki settings as a dictionary."""
        return {
            "anki_url": self.url_edit.text() or DEFAULT_ANKI_URL,
            "parent_deck": self.parent_deck_combo.currentText() or "KOHighlights",
            "create_subdecks": self.create_subdecks_chk.isChecked(),
            "note_type": self.note_type_combo.currentText() or DEFAULT_NOTE_TYPE,
            "allow_duplicates": self.allow_duplicates_chk.isChecked(),
            "add_tags": self.add_tags_chk.isChecked(),
            "include_chapter": self.include_chapter_chk.isChecked(),
            "include_page": self.include_page_chk.isChecked(),
            "include_date": self.include_date_chk.isChecked(),
            "show_export_dialog": self.show_export_dialog_chk.isChecked(),
            "field_mappings": getattr(self, '_field_mappings', DEFAULT_FIELD_MAPPINGS.copy())
        }
    
    def set_settings(self, settings: Dict):
        """Apply settings from a dictionary."""
        self.url_edit.setText(settings.get("anki_url", DEFAULT_ANKI_URL))
        
        parent_deck = settings.get("parent_deck", "KOHighlights")
        idx = self.parent_deck_combo.findText(parent_deck)
        if idx >= 0:
            self.parent_deck_combo.setCurrentIndex(idx)
        else:
            self.parent_deck_combo.setCurrentText(parent_deck)
        
        self.create_subdecks_chk.setChecked(settings.get("create_subdecks", True))
        
        note_type = settings.get("note_type", DEFAULT_NOTE_TYPE)
        idx = self.note_type_combo.findText(note_type)
        if idx >= 0:
            self.note_type_combo.setCurrentIndex(idx)
        
        self.allow_duplicates_chk.setChecked(settings.get("allow_duplicates", False))
        self.add_tags_chk.setChecked(settings.get("add_tags", True))
        self.include_chapter_chk.setChecked(settings.get("include_chapter", True))
        self.include_page_chk.setChecked(settings.get("include_page", True))
        self.include_date_chk.setChecked(settings.get("include_date", False))
        self.show_export_dialog_chk.setChecked(settings.get("show_export_dialog", True))
        
        self._field_mappings = settings.get("field_mappings", DEFAULT_FIELD_MAPPINGS.copy())


class AnkiPrefsDialog(QDialog):
    """
    Standalone dialog that wraps AnkiPrefsWidget.
    
    Used for opening Anki settings from the Preferences dialog.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Anki Settings"))
        self.setMinimumWidth(450)
        self.setMinimumHeight(500)
        
        layout = QVBoxLayout(self)
        
        # Add the preferences widget
        self.prefs_widget = AnkiPrefsWidget(parent)
        layout.addWidget(self.prefs_widget)
        
        # Add button box
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
    
    def get_settings(self) -> Dict:
        """Get the current Anki settings."""
        return self.prefs_widget.get_settings()
    
    def set_settings(self, settings: Dict):
        """Apply settings to the widget."""
        self.prefs_widget.set_settings(settings)


class FieldMappingDialog(QDialog):
    """Dialog for configuring how highlight data maps to Anki note fields."""
    
    def __init__(self, anki: Optional[AnkiConnect], settings: Dict, parent=None):
        super().__init__(parent)
        self.anki = anki
        self.settings = settings
        self.field_combos = {}
        self._setup_ui()
        self._connect_signals()
        self._load_note_types()
    
    def _setup_ui(self):
        """Set up the UI components."""
        self.setWindowTitle(_("Configure Field Mappings"))
        self.resize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # Info label
        info_label = QLabel(_("Configure how highlight data is mapped to Anki note fields.\n"
                              "Select which note field each type of data should go to."))
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Note Type Selection
        note_group = QGroupBox(_("Note Type"))
        note_layout = QHBoxLayout(note_group)
        
        note_layout.addWidget(QLabel(_("Note Type:")))
        self.note_type_combo = QComboBox()
        self.note_type_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        note_layout.addWidget(self.note_type_combo)
        
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setMaximumWidth(30)
        self.refresh_btn.setToolTip(_("Refresh note types from Anki"))
        note_layout.addWidget(self.refresh_btn)
        
        layout.addWidget(note_group)
        
        # Field Mappings
        mapping_group = QGroupBox(_("Field Mappings"))
        mapping_layout = QGridLayout(mapping_group)
        
        # Headers
        header_source = QLabel(_("Source Data"))
        header_source.setStyleSheet("font-weight: bold;")
        mapping_layout.addWidget(header_source, 0, 0)
        
        header_target = QLabel(_("Target Field"))
        header_target.setStyleSheet("font-weight: bold;")
        mapping_layout.addWidget(header_target, 0, 1)
        
        # Mapping rows
        self.source_fields = [
            ("highlight", _("Highlight Text")),
            ("comment", _("Comment/Note")),
            ("page", _("Page Number")),
            ("chapter", _("Chapter")),
            ("date", _("Date Created")),
            ("book_title", _("Book Title")),
            ("author", _("Author"))
        ]
        
        for i, (key, label) in enumerate(self.source_fields, 1):
            mapping_layout.addWidget(QLabel(label), i, 0)
            combo = QComboBox()
            combo.addItem(_("(None)"), "")
            self.field_combos[key] = combo
            mapping_layout.addWidget(combo, i, 1)
        
        layout.addWidget(mapping_group)
        
        # Buttons
        btn_frame = QFrame()
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        
        self.reset_btn = QPushButton(_("Reset to Defaults"))
        self.reset_btn.setToolTip(_("Reset field mappings to default values"))
        btn_layout.addWidget(self.reset_btn)
        
        btn_layout.addStretch()
        layout.addWidget(btn_frame)
        
        layout.addStretch()
        
        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        layout.addWidget(self.button_box)
    
    def _connect_signals(self):
        """Connect signals to slots."""
        self.note_type_combo.currentTextChanged.connect(self._load_fields)
        self.refresh_btn.clicked.connect(self._load_note_types)
        self.reset_btn.clicked.connect(self._reset_to_defaults)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
    
    def _load_note_types(self):
        """Load available note types from Anki."""
        if not self.anki:
            self.note_type_combo.addItem(DEFAULT_NOTE_TYPE)
            return
        
        try:
            models = self.anki.get_model_names(force_refresh=True)
            current = self.note_type_combo.currentText() or self.settings.get("note_type", DEFAULT_NOTE_TYPE)
            
            self.note_type_combo.clear()
            self.note_type_combo.addItems(sorted(models))
            
            idx = self.note_type_combo.findText(current)
            if idx >= 0:
                self.note_type_combo.setCurrentIndex(idx)
            else:
                idx = self.note_type_combo.findText(DEFAULT_NOTE_TYPE)
                if idx >= 0:
                    self.note_type_combo.setCurrentIndex(idx)
        except AnkiConnectError:
            self.note_type_combo.addItem(DEFAULT_NOTE_TYPE)
    
    def _load_fields(self, model_name: str):
        """Load available fields for the selected note type."""
        fields = [""]  # Empty option
        
        if self.anki and model_name:
            try:
                fields.extend(self.anki.get_model_field_names(model_name))
            except AnkiConnectError:
                fields.extend(["Front", "Back"])  # Fallback for Basic note type
        else:
            fields.extend(["Front", "Back"])
        
        # Update all combo boxes
        current_mappings = self.settings.get("field_mappings", DEFAULT_FIELD_MAPPINGS)
        
        for key, combo in self.field_combos.items():
            current = combo.currentData() or current_mappings.get(key, "")
            combo.clear()
            for field in fields:
                combo.addItem(field if field else _("(None)"), field)
            
            # Try to restore selection
            idx = combo.findData(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)
    
    def _reset_to_defaults(self):
        """Reset mappings to default values."""
        for key, default_field in DEFAULT_FIELD_MAPPINGS.items():
            if key in self.field_combos:
                combo = self.field_combos[key]
                idx = combo.findData(default_field)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
    
    def get_mappings(self) -> Dict[str, str]:
        """Get the current field mappings."""
        return {key: combo.currentData() or "" 
                for key, combo in self.field_combos.items()}
    
    def get_field_mappings(self) -> Dict[str, str]:
        """Alias for get_mappings() for compatibility."""
        return self.get_mappings()


class AnkiExportDialog(QDialog):
    """
    Dialog for exporting highlights to Anki.
    
    Provides a comprehensive UI for:
    - Selecting books to export
    - Configuring deck and note settings
    - Mapping highlight fields to note fields
    - Previewing card content
    - Progress tracking during export
    """
    
    def __init__(self, base, books_data: List[Dict], settings: Dict, parent=None):
        super().__init__(parent)
        self.base = base
        self.books_data = books_data  # List of {title, author, highlights: [...]}
        self.settings = settings
        self.anki = None
        self.export_thread = None
        
        self._setup_ui()
        self._connect_signals()
        self._populate_books()
        
        # Auto-test connection on open
        QTimer.singleShot(100, self._check_connection)
    
    def _setup_ui(self):
        """Set up the UI components."""
        self.setWindowTitle(_("Export to Anki"))
        self.resize(600, 700)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # Connection Status
        conn_group = QGroupBox(_("Connection Status"))
        conn_layout = QHBoxLayout(conn_group)
        
        self.conn_icon = QLabel("●")
        self.conn_icon.setStyleSheet("color: gray; font-size: 16px;")
        conn_layout.addWidget(self.conn_icon)
        
        self.conn_label = QLabel(_("Checking connection..."))
        conn_layout.addWidget(self.conn_label)
        
        conn_layout.addStretch()
        
        self.reconnect_btn = QPushButton(_("Reconnect"))
        self.reconnect_btn.setToolTip(_("Try to reconnect to Anki"))
        conn_layout.addWidget(self.reconnect_btn)
        
        layout.addWidget(conn_group)
        
        # Books to Export
        books_group = QGroupBox(_("Books to Export"))
        books_layout = QVBoxLayout(books_group)
        
        self.books_list = QListWidget()
        self.books_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.books_list.setMinimumHeight(100)
        self.books_list.setMaximumHeight(150)
        books_layout.addWidget(self.books_list)
        
        summary_frame = QFrame()
        summary_layout = QHBoxLayout(summary_frame)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        
        self.summary_label = QLabel(_("0 books selected, 0 highlights total"))
        summary_layout.addWidget(self.summary_label)
        
        summary_layout.addStretch()
        
        self.select_all_btn = QPushButton(_("Select All"))
        summary_layout.addWidget(self.select_all_btn)
        
        self.select_none_btn = QPushButton(_("Select None"))
        summary_layout.addWidget(self.select_none_btn)
        
        books_layout.addWidget(summary_frame)
        layout.addWidget(books_group)
        
        # Deck Settings
        deck_group = QGroupBox(_("Deck Settings"))
        deck_layout = QGridLayout(deck_group)
        
        deck_layout.addWidget(QLabel(_("Parent Deck:")), 0, 0)
        self.deck_combo = QComboBox()
        self.deck_combo.setEditable(True)
        self.deck_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        deck_layout.addWidget(self.deck_combo, 0, 1)
        
        self.refresh_decks_btn = QPushButton("↻")
        self.refresh_decks_btn.setMaximumWidth(30)
        self.refresh_decks_btn.setToolTip(_("Refresh deck list"))
        deck_layout.addWidget(self.refresh_decks_btn, 0, 2)
        
        self.create_subdecks_chk = QCheckBox(_("Create subdecks for each book (recommended)"))
        self.create_subdecks_chk.setChecked(self.settings.get("create_subdecks", True))
        deck_layout.addWidget(self.create_subdecks_chk, 1, 0, 1, 3)
        
        self.deck_preview_label = QLabel(_("Preview: KOHighlights::Book Title"))
        self.deck_preview_label.setStyleSheet("color: gray; font-style: italic;")
        deck_layout.addWidget(self.deck_preview_label, 2, 0, 1, 3)
        
        layout.addWidget(deck_group)
        
        # Note Settings
        note_group = QGroupBox(_("Note Settings"))
        note_layout = QGridLayout(note_group)
        
        note_layout.addWidget(QLabel(_("Note Type:")), 0, 0)
        self.note_type_combo = QComboBox()
        self.note_type_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        note_layout.addWidget(self.note_type_combo, 0, 1)
        
        self.refresh_models_btn = QPushButton("↻")
        self.refresh_models_btn.setMaximumWidth(30)
        self.refresh_models_btn.setToolTip(_("Refresh note type list"))
        note_layout.addWidget(self.refresh_models_btn, 0, 2)
        
        # Field Mappings Sub-group
        field_group = QGroupBox(_("Field Mappings"))
        field_layout = QGridLayout(field_group)
        
        field_layout.addWidget(QLabel(_("Highlight →")), 0, 0)
        self.highlight_field_combo = QComboBox()
        field_layout.addWidget(self.highlight_field_combo, 0, 1)
        
        field_layout.addWidget(QLabel(_("Comment →")), 1, 0)
        self.comment_field_combo = QComboBox()
        field_layout.addWidget(self.comment_field_combo, 1, 1)
        
        field_layout.addWidget(QLabel(_("Metadata →")), 2, 0)
        self.metadata_field_combo = QComboBox()
        field_layout.addWidget(self.metadata_field_combo, 2, 1)
        
        note_layout.addWidget(field_group, 1, 0, 1, 3)
        layout.addWidget(note_group)
        
        # Export Options
        options_group = QGroupBox(_("Export Options"))
        options_layout = QGridLayout(options_group)
        
        self.allow_duplicates_chk = QCheckBox(_("Allow duplicate notes"))
        self.allow_duplicates_chk.setChecked(self.settings.get("allow_duplicates", False))
        options_layout.addWidget(self.allow_duplicates_chk, 0, 0)
        
        self.add_tags_chk = QCheckBox(_("Add tags"))
        self.add_tags_chk.setChecked(self.settings.get("add_tags", True))
        options_layout.addWidget(self.add_tags_chk, 0, 1)
        
        self.include_chapter_chk = QCheckBox(_("Include chapter"))
        self.include_chapter_chk.setChecked(self.settings.get("include_chapter", True))
        options_layout.addWidget(self.include_chapter_chk, 1, 0)
        
        self.include_page_chk = QCheckBox(_("Include page number"))
        self.include_page_chk.setChecked(self.settings.get("include_page", True))
        options_layout.addWidget(self.include_page_chk, 1, 1)
        
        self.include_date_chk = QCheckBox(_("Include date"))
        self.include_date_chk.setChecked(self.settings.get("include_date", False))
        options_layout.addWidget(self.include_date_chk, 2, 0)
        
        self.include_book_info_chk = QCheckBox(_("Include book title/author"))
        self.include_book_info_chk.setChecked(True)
        options_layout.addWidget(self.include_book_info_chk, 2, 1)
        
        layout.addWidget(options_group)
        
        # Preview
        self.preview_group = QGroupBox(_("Card Preview"))
        self.preview_group.setCheckable(True)
        self.preview_group.setChecked(True)
        preview_layout = QVBoxLayout(self.preview_group)
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMinimumHeight(80)
        self.preview_text.setMaximumHeight(150)
        preview_layout.addWidget(self.preview_text)
        
        layout.addWidget(self.preview_group)
        
        # Progress
        self.progress_frame = QFrame()
        self.progress_frame.setVisible(False)
        progress_layout = QVBoxLayout(self.progress_frame)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel(_("Exporting..."))
        self.progress_label.setAlignment(Qt.AlignCenter)
        progress_layout.addWidget(self.progress_label)
        
        layout.addWidget(self.progress_frame)
        
        # Dialog Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.export_btn = self.button_box.button(QDialogButtonBox.Ok)
        self.export_btn.setText(_("Export to Anki"))
        layout.addWidget(self.button_box)
    
    def _connect_signals(self):
        """Connect signals to slots."""
        self.reconnect_btn.clicked.connect(self._check_connection)
        self.refresh_decks_btn.clicked.connect(self._refresh_decks)
        self.refresh_models_btn.clicked.connect(self._refresh_note_types)
        
        self.select_all_btn.clicked.connect(self._select_all_books)
        self.select_none_btn.clicked.connect(self._select_none_books)
        self.books_list.itemChanged.connect(self._update_summary)
        
        self.deck_combo.currentTextChanged.connect(self._update_deck_preview)
        self.create_subdecks_chk.stateChanged.connect(self._update_deck_preview)
        
        self.note_type_combo.currentTextChanged.connect(self._load_fields)
        
        # Update preview when options change
        for chk in [self.include_chapter_chk, self.include_page_chk, 
                    self.include_date_chk, self.include_book_info_chk]:
            chk.stateChanged.connect(self._update_preview)
        
        self.button_box.accepted.connect(self._start_export)
        self.button_box.rejected.connect(self.reject)
    
    def _check_connection(self):
        """Check connection to Anki."""
        self.conn_label.setText(_("Connecting..."))
        self.conn_icon.setStyleSheet("color: orange; font-size: 16px;")
        QApplication.processEvents()
        
        try:
            url = self.settings.get("anki_url", DEFAULT_ANKI_URL)
            self.anki = AnkiConnect(url)
            success, message = self.anki.test_connection()
            
            if success:
                self.conn_icon.setStyleSheet("color: green; font-size: 16px;")
                self.conn_label.setText(message)
                self.export_btn.setEnabled(True)
                self._refresh_decks()
                self._refresh_note_types()
            else:
                self.conn_icon.setStyleSheet("color: red; font-size: 16px;")
                self.conn_label.setText(_("Connection failed: ") + message[:30])
                self.export_btn.setEnabled(False)
        except Exception as e:
            self.conn_icon.setStyleSheet("color: red; font-size: 16px;")
            self.conn_label.setText(_("Error: ") + str(e)[:40])
            self.export_btn.setEnabled(False)
    
    def _populate_books(self):
        """Populate the books list with checkable items."""
        self.books_list.clear()
        for book in self.books_data:
            title = book.get("title", _("Unknown"))
            author = book.get("author", "")
            count = len(book.get("highlights", []))
            
            text = f"{title}"
            if author:
                text += f" - {author}"
            text += f" ({count} highlights)"
            
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            item.setData(Qt.UserRole, book)
            self.books_list.addItem(item)
        
        self._update_summary()
    
    def _select_all_books(self):
        """Select all books."""
        for i in range(self.books_list.count()):
            self.books_list.item(i).setCheckState(Qt.Checked)
    
    def _select_none_books(self):
        """Deselect all books."""
        for i in range(self.books_list.count()):
            self.books_list.item(i).setCheckState(Qt.Unchecked)
    
    def _update_summary(self):
        """Update the books summary label."""
        books_count = 0
        highlights_count = 0
        
        for i in range(self.books_list.count()):
            item = self.books_list.item(i)
            if item.checkState() == Qt.Checked:
                book = item.data(Qt.UserRole)
                books_count += 1
                highlights_count += len(book.get("highlights", []))
        
        self.summary_label.setText(
            _("{} books selected, {} highlights total").format(books_count, highlights_count)
        )
        self._update_preview()
    
    def _refresh_decks(self):
        """Refresh the deck list from Anki."""
        if not self.anki:
            return
        
        try:
            decks = self.anki.get_deck_names(force_refresh=True)
            current = self.deck_combo.currentText() or self.settings.get("parent_deck", "KOHighlights")
            
            self.deck_combo.clear()
            self.deck_combo.addItem("KOHighlights")
            self.deck_combo.addItems(sorted(d for d in decks if d != "Default"))
            
            idx = self.deck_combo.findText(current)
            if idx >= 0:
                self.deck_combo.setCurrentIndex(idx)
            else:
                self.deck_combo.setCurrentIndex(0)
        except AnkiConnectError:
            self.deck_combo.addItem("KOHighlights")
    
    def _refresh_note_types(self):
        """Refresh the note type list from Anki."""
        if not self.anki:
            return
        
        try:
            models = self.anki.get_model_names(force_refresh=True)
            current = self.note_type_combo.currentText() or self.settings.get("note_type", DEFAULT_NOTE_TYPE)
            
            self.note_type_combo.clear()
            self.note_type_combo.addItems(sorted(models))
            
            idx = self.note_type_combo.findText(current)
            if idx < 0:
                idx = self.note_type_combo.findText(DEFAULT_NOTE_TYPE)
            if idx >= 0:
                self.note_type_combo.setCurrentIndex(idx)
        except AnkiConnectError:
            self.note_type_combo.addItem(DEFAULT_NOTE_TYPE)
    
    def _load_fields(self, model_name: str):
        """Load fields for the selected note type."""
        fields = []
        
        if self.anki and model_name:
            try:
                fields = self.anki.get_model_field_names(model_name)
            except AnkiConnectError:
                fields = ["Front", "Back"]
        else:
            fields = ["Front", "Back"]
        
        for combo in [self.highlight_field_combo, self.comment_field_combo, 
                      self.metadata_field_combo]:
            current = combo.currentText()
            combo.clear()
            combo.addItems(fields)
            
            idx = combo.findText(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        
        # Set sensible defaults if fields are empty
        if fields:
            if self.highlight_field_combo.currentIndex() < 0:
                self.highlight_field_combo.setCurrentIndex(0)  # First field for highlight
            if self.comment_field_combo.currentIndex() < 0 and len(fields) > 1:
                self.comment_field_combo.setCurrentIndex(1)  # Second field for comment
            if self.metadata_field_combo.currentIndex() < 0 and len(fields) > 1:
                self.metadata_field_combo.setCurrentIndex(1)  # Second field for metadata
        
        self._update_preview()
    
    def _update_deck_preview(self):
        """Update the deck name preview."""
        parent = self.deck_combo.currentText() or "KOHighlights"
        
        if self.create_subdecks_chk.isChecked():
            preview = f"{parent}::Book Title"
        else:
            preview = parent
        
        self.deck_preview_label.setText(_("Preview: ") + preview)
    
    def _update_preview(self):
        """Update the card preview."""
        if not self.preview_group.isChecked():
            return
        
        # Get first highlight from first checked book
        highlight_data = None
        for i in range(self.books_list.count()):
            item = self.books_list.item(i)
            if item.checkState() == Qt.Checked:
                book = item.data(Qt.UserRole)
                highlights = book.get("highlights", [])
                if highlights:
                    highlight_data = highlights[0].copy()
                    highlight_data["book_title"] = book.get("title", "")
                    highlight_data["author"] = book.get("author", "")
                    break
        
        if not highlight_data:
            self.preview_text.setPlainText(_("No highlights selected"))
            return
        
        # Build preview
        front_field = self.highlight_field_combo.currentText()
        back_field = self.comment_field_combo.currentText()
        
        front = f"<b>{front_field}:</b><br>"
        front += highlight_data.get("highlight", highlight_data.get("text", ""))
        
        back = f"<b>{back_field}:</b><br>"
        parts = []
        
        if self.include_book_info_chk.isChecked():
            title = highlight_data.get("book_title", "")
            author = highlight_data.get("author", "")
            if title:
                parts.append(f"📚 {title}")
            if author:
                parts.append(f"✍️ {author}")
        
        if self.include_chapter_chk.isChecked():
            chapter = highlight_data.get("chapter", "")
            if chapter:
                parts.append(f"📖 {chapter}")
        
        if self.include_page_chk.isChecked():
            page = highlight_data.get("page", "")
            if page:
                parts.append(f"📄 Page {page}")
        
        if self.include_date_chk.isChecked():
            date = highlight_data.get("date", "")
            if date:
                parts.append(f"📅 {date}")
        
        comment = highlight_data.get("comment", "")
        if comment:
            parts.append(f"💭 {comment}")
        
        back += "<br>".join(parts)
        
        preview_html = f"""
        <div style="border: 1px solid #ccc; padding: 10px; margin-bottom: 10px;">
            {front}
        </div>
        <div style="border: 1px solid #ccc; padding: 10px;">
            {back}
        </div>
        """
        
        self.preview_text.setHtml(preview_html)
    
    def _get_selected_books(self) -> List[Dict]:
        """Get the list of selected books."""
        selected = []
        for i in range(self.books_list.count()):
            item = self.books_list.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.data(Qt.UserRole))
        return selected
    
    def _prepare_highlights(self, books: List[Dict]) -> List[Dict]:
        """Prepare highlights for export with all necessary data."""
        all_highlights = []
        
        for book in books:
            book_title = book.get("title", "")
            author = book.get("author", "")
            
            for highlight in book.get("highlights", []):
                prepared = {
                    "highlight": highlight.get("text", highlight.get("highlight", "")),
                    "comment": highlight.get("comment", "") if self.include_chapter_chk.isChecked() else "",
                    "page": highlight.get("page", "") if self.include_page_chk.isChecked() else "",
                    "chapter": highlight.get("chapter", "") if self.include_chapter_chk.isChecked() else "",
                    "date": highlight.get("date", "") if self.include_date_chk.isChecked() else "",
                    "book_title": book_title if self.include_book_info_chk.isChecked() else "",
                    "author": author if self.include_book_info_chk.isChecked() else "",
                }
                all_highlights.append(prepared)
        
        return all_highlights
    
    def _build_field_mapping(self) -> Dict[str, str]:
        """Build field mapping from UI selections."""
        highlight_field = self.highlight_field_combo.currentText()
        comment_field = self.comment_field_combo.currentText()
        metadata_field = self.metadata_field_combo.currentText()
        
        return {
            "highlight": highlight_field,
            "comment": comment_field,
            "page": metadata_field,
            "chapter": metadata_field,
            "date": metadata_field,
            "book_title": metadata_field,
            "author": metadata_field,
        }
    
    def _start_export(self):
        """Start the export process."""
        selected_books = self._get_selected_books()
        
        if not selected_books:
            QMessageBox.warning(self, _("Warning"), _("Please select at least one book to export."))
            return
        
        if not self.anki:
            QMessageBox.warning(self, _("Warning"), _("Not connected to Anki."))
            return
        
        # Disable UI during export
        self.export_btn.setEnabled(False)
        self.progress_frame.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText(_("Preparing export..."))
        QApplication.processEvents()
        
        # Prepare data
        parent_deck = self.deck_combo.currentText() or "KOHighlights"
        model_name = self.note_type_combo.currentText() or DEFAULT_NOTE_TYPE
        create_subdecks = self.create_subdecks_chk.isChecked()
        
        total_success = 0
        total_fail = 0
        all_errors = []
        
        for book in selected_books:
            book_title = book.get("title", _("Unknown"))
            
            # Create deck
            if create_subdecks:
                deck_name = self.anki.create_deck_hierarchy(parent_deck, book_title)
            else:
                deck_name = parent_deck
                if not self.anki.deck_exists(deck_name):
                    self.anki.create_deck(deck_name)
            
            # Prepare highlights for this book
            highlights = self._prepare_highlights([book])
            
            if not highlights:
                continue
            
            # Build field mapping
            field_mapping = self._build_field_mapping()
            
            # Build tags
            tags = []
            if self.add_tags_chk.isChecked():
                tags.append("KOHighlights")
                safe_title = book_title.replace(" ", "_").replace("::", "_")
                tags.append(f"book::{safe_title}")
            
            # Export
            try:
                success, fail, errors = self.anki.bulk_add_highlights(
                    deck_name,
                    model_name,
                    highlights,
                    field_mapping,
                    tags,
                    self.allow_duplicates_chk.isChecked(),
                    lambda c, t: self._update_progress(c, t, book_title)
                )
                total_success += success
                total_fail += fail
                all_errors.extend(errors)
            except AnkiConnectError as e:
                all_errors.append(f"{book_title}: {str(e)}")
                total_fail += len(highlights)
        
        # Show results
        self.progress_frame.setVisible(False)
        self.export_btn.setEnabled(True)
        
        if total_success > 0:
            msg = _("{} cards exported successfully!").format(total_success)
            if total_fail > 0:
                msg += _("\n{} cards failed.").format(total_fail)
            
            if all_errors:
                msg += _("\n\nErrors:\n") + "\n".join(all_errors[:5])
                if len(all_errors) > 5:
                    msg += _("\n... and {} more errors").format(len(all_errors) - 5)
            
            QMessageBox.information(self, _("Export Complete"), msg)
            self.accept()
        else:
            msg = _("Export failed. No cards were added.")
            if all_errors:
                msg += _("\n\nErrors:\n") + "\n".join(all_errors[:5])
            
            QMessageBox.warning(self, _("Export Failed"), msg)
    
    def _update_progress(self, current: int, total: int, book_title: str):
        """Update the progress bar during export."""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_label.setText(_("Exporting {} ({}/{})").format(book_title, current, total))
        QApplication.processEvents()


# Export public symbols
__all__ = [
    "AnkiPrefsWidget",
    "AnkiExportDialog", 
    "FieldMappingDialog",
    "AnkiExportThread"
]
