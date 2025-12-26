# coding=utf-8
"""
Anki Integration for KOHighlights

This module provides the integration layer between KOHighlights and Anki,
connecting the existing highlight data with the AnkiConnect API.
"""

from boot_config import *
from boot_config import _
from anki_connect import (AnkiConnect, AnkiConnectError, get_anki_connect,
                          DEFAULT_ANKI_URL, DEFAULT_NOTE_TYPE, DEFAULT_FIELD_MAPPINGS)
from anki_ui import AnkiExportDialog, AnkiPrefsWidget

__author__ = "KOHighlights"


class AnkiIntegration:
    """
    Integration class that connects KOHighlights with Anki.
    
    This class provides methods to:
    - Extract highlights from the application
    - Format them for Anki export
    - Manage export dialogs
    - Handle settings
    """
    
    def __init__(self, base):
        """
        Initialize Anki integration.
        
        :param base: The main application window (Base class instance)
        """
        self.base = base
        self.anki = None
        self._settings = self._get_default_settings()
    
    def _get_default_settings(self) -> dict:
        """Get default Anki settings."""
        return {
            "anki_url": DEFAULT_ANKI_URL,
            "parent_deck": "KOHighlights",
            "create_subdecks": True,
            "note_type": DEFAULT_NOTE_TYPE,
            "allow_duplicates": False,
            "add_tags": True,
            "include_chapter": True,
            "include_page": True,
            "include_date": False,
            "show_export_dialog": True,
            "field_mappings": DEFAULT_FIELD_MAPPINGS.copy()
        }
    
    def get_settings(self) -> dict:
        """Get current Anki settings."""
        return self._settings.copy()
    
    def set_settings(self, settings: dict):
        """Set Anki settings."""
        self._settings.update(settings)
    
    def load_settings(self, app_config: dict):
        """Load Anki settings from app configuration."""
        anki_config = app_config.get("anki_settings", {})
        self._settings.update(anki_config)
    
    def save_settings(self) -> dict:
        """Return settings dictionary for saving."""
        return {"anki_settings": self._settings}
    
    def get_anki_connect(self) -> AnkiConnect:
        """Get or create AnkiConnect instance."""
        url = self._settings.get("anki_url", DEFAULT_ANKI_URL)
        if self.anki is None or self.anki.url != url:
            self.anki = AnkiConnect(url)
        return self.anki
    
    def test_connection(self) -> tuple:
        """
        Test connection to Anki.
        
        :return: Tuple of (success: bool, message: str)
        """
        anki = self.get_anki_connect()
        return anki.test_connection()
    
    def get_selected_books_data(self) -> list:
        """
        Get highlight data for selected books in the file_table.
        
        :return: List of book dictionaries with highlights
        """
        books_data = []
        
        for idx in self.base.sel_indexes:
            row = idx.row()
            data = self.base.file_table.item(row, 0).data(Qt.UserRole)
            path = self.base.file_table.item(row, PATH).data(0)
            
            # Get book info
            title = self.base.file_table.item(row, TITLE).data(0)
            author = self.base.file_table.item(row, AUTHOR).data(0)
            if author in [OLD_TYPE, NO_AUTHOR]:
                author = ""
            
            # Get highlights
            highlights = self._extract_highlights(data, path)
            
            if highlights:
                books_data.append({
                    "title": title,
                    "author": author,
                    "highlights": highlights,
                    "path": path,
                    "data": data
                })
        
        return books_data
    
    def get_all_books_data(self) -> list:
        """
        Get highlight data for all books in the file_table.
        
        :return: List of book dictionaries with highlights
        """
        books_data = []
        
        for row in range(self.base.file_table.rowCount()):
            data = self.base.file_table.item(row, 0).data(Qt.UserRole)
            path = self.base.file_table.item(row, PATH).data(0)
            
            # Get book info
            title = self.base.file_table.item(row, TITLE).data(0)
            author = self.base.file_table.item(row, AUTHOR).data(0)
            if author in [OLD_TYPE, NO_AUTHOR]:
                author = ""
            
            # Get highlights
            highlights = self._extract_highlights(data, path)
            
            if highlights:
                books_data.append({
                    "title": title,
                    "author": author,
                    "highlights": highlights,
                    "path": path,
                    "data": data
                })
        
        return books_data
    
    def _extract_highlights(self, data: dict, path: str) -> list:
        """
        Extract highlights from book data in a format suitable for Anki.
        
        :param data: The book's metadata dictionary
        :param path: The book's file path
        :return: List of highlight dictionaries
        """
        highlights = []
        
        if not data:
            return highlights
        
        annotations = data.get("annotations")
        if annotations is not None:  # new format metadata
            for idx in annotations:
                high_info = self._get_new_highlight_info(data, idx)
                if high_info:
                    highlights.append(high_info)
        else:  # old format metadata
            try:
                for page in data.get("highlight", {}):
                    for page_id in data["highlight"][page]:
                        high_info = self._get_old_highlight_info(data, page, page_id)
                        if high_info:
                            highlights.append(high_info)
            except (KeyError, TypeError):
                pass
        
        return highlights
    
    def _get_new_highlight_info(self, data: dict, idx: int) -> dict:
        """
        Extract highlight info from new format metadata.
        
        :param data: The book's metadata
        :param idx: The highlight's index
        :return: Dictionary with highlight info or None
        """
        high_data = data["annotations"][idx]
        
        # Skip bookmarks (no pos0 means it's a bookmark)
        if not high_data.get("pos0"):
            return None
        
        page = high_data.get("pageno", 0)
        ref_page = high_data.get("pageref")
        if ref_page and str(ref_page).isdigit():
            ref_page = int(ref_page)
        else:
            ref_page = page
        
        return {
            "text": high_data.get("text", "").replace("\\\n", "\n"),
            "highlight": high_data.get("text", "").replace("\\\n", "\n"),  # Alias for Anki
            "chapter": high_data.get("chapter", ""),
            "comment": high_data.get("note", "").replace("\\\n", "\n"),
            "date": high_data.get("datetime", ""),
            "page": str(ref_page if self.base.show_ref_pg else page),
            "idx": idx
        }
    
    def _get_old_highlight_info(self, data: dict, page: int, page_id: int) -> dict:
        """
        Extract highlight info from old format metadata.
        
        :param data: The book's metadata
        :param page: The page number
        :param page_id: The highlight ID on that page
        :return: Dictionary with highlight info or None
        """
        try:
            high_data = data["highlight"][page][page_id]
            text = high_data.get("text", "").replace("\\\n", "\n")
            
            # Look for comment in bookmarks
            comment = ""
            for idx in data.get("bookmarks", {}):
                bookmark = data["bookmarks"][idx]
                if text == bookmark.get("notes"):
                    bkm_text = bookmark.get("text", "")
                    if bkm_text and bkm_text != text:
                        # Extract comment from bookmark
                        import re
                        pat = r"Page \d+ (.+?) @ \d+-\d+-\d+ \d+:\d+:\d+"
                        bkm_text = re.sub(pat, r"\1", bkm_text, 1, re.DOTALL | re.MULTILINE)
                        if text != bkm_text:
                            comment = bkm_text.replace("\\\n", "\n")
                    break
            
            return {
                "text": text,
                "highlight": text,  # Alias for Anki
                "chapter": high_data.get("chapter", ""),
                "comment": comment,
                "date": high_data.get("datetime", ""),
                "page": str(page),
                "page_id": page_id
            }
        except (KeyError, TypeError):
            return None
    
    def export_to_anki(self, books_data: list = None):
        """
        Export highlights to Anki.
        
        :param books_data: Optional list of book data. If None, uses selected books.
        """
        if books_data is None:
            books_data = self.get_selected_books_data()
        
        if not books_data:
            self.base.popup(_("Warning"), 
                           _("No books with highlights selected for export."))
            return
        
        # Check if we should show dialog
        if self._settings.get("show_export_dialog", True):
            self._show_export_dialog(books_data)
        else:
            self._quick_export(books_data)
    
    def _show_export_dialog(self, books_data: list):
        """
        Show the Anki export dialog.
        
        :param books_data: List of book data to export
        """
        dialog = AnkiExportDialog(self.base, books_data, self._settings, self.base)
        if QT6:  # QT6 requires exec() instead of exec_()
            dialog.exec_ = getattr(dialog, "exec")
        dialog.exec_()
    
    def _quick_export(self, books_data: list):
        """
        Perform quick export without showing dialog.
        
        :param books_data: List of book data to export
        """
        try:
            anki = self.get_anki_connect()
            success, message = anki.test_connection()
            
            if not success:
                self.base.popup(_("Error"), 
                               _("Could not connect to Anki: {}").format(message))
                return
            
            parent_deck = self._settings.get("parent_deck", "KOHighlights")
            model_name = self._settings.get("note_type", DEFAULT_NOTE_TYPE)
            create_subdecks = self._settings.get("create_subdecks", True)
            field_mapping = self._settings.get("field_mappings", DEFAULT_FIELD_MAPPINGS)
            allow_duplicates = self._settings.get("allow_duplicates", False)
            add_tags = self._settings.get("add_tags", True)
            
            total_success = 0
            total_fail = 0
            
            for book in books_data:
                book_title = book.get("title", "")
                
                # Create deck
                if create_subdecks:
                    deck_name = anki.create_deck_hierarchy(parent_deck, book_title)
                else:
                    deck_name = parent_deck
                    if not anki.deck_exists(deck_name):
                        anki.create_deck(deck_name)
                
                # Prepare tags
                tags = []
                if add_tags:
                    tags.append("KOHighlights")
                    safe_title = book_title.replace(" ", "_").replace("::", "_")
                    tags.append(f"book::{safe_title}")
                
                # Add book info to highlights
                for highlight in book.get("highlights", []):
                    highlight["book_title"] = book_title
                    highlight["author"] = book.get("author", "")
                
                # Export
                success, fail, _ = anki.bulk_add_highlights(
                    deck_name,
                    model_name,
                    book.get("highlights", []),
                    field_mapping,
                    tags,
                    allow_duplicates
                )
                
                total_success += success
                total_fail += fail
            
            if total_success > 0:
                msg = _("{} cards exported to Anki!").format(total_success)
                if total_fail > 0:
                    msg += _(" ({} failed)").format(total_fail)
                self.base.popup(_("Success"), msg, icon=QMessageBox.Information)
            else:
                self.base.popup(_("Warning"), _("No cards were exported."))
                
        except AnkiConnectError as e:
            self.base.popup(_("Error"), str(e))
        except Exception as e:
            self.base.popup(_("Error"), _("Unexpected error: {}").format(str(e)))


# Additional imports needed
if QT5:
    from PySide2.QtWidgets import QMessageBox
    from PySide2.QtCore import Qt
else:
    from PySide6.QtWidgets import QMessageBox
    from PySide6.QtCore import Qt

# Constants from boot_config that we need
try:
    from boot_config import (PATH, TITLE, AUTHOR, OLD_TYPE, NO_AUTHOR, 
                             NO_TITLE, DATE_FORMAT)
except ImportError:
    # Fallback values if not available
    PATH = 7
    TITLE = 0
    AUTHOR = 1
    OLD_TYPE = "OLD TYPE FILE"
    NO_AUTHOR = "NO AUTHOR FOUND"
    NO_TITLE = "NO TITLE FOUND"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


__all__ = ["AnkiIntegration"]
