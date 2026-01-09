# coding=utf-8
"""
AnkiConnect Integration Module for KOHighlights

This module provides a complete interface to AnkiConnect for managing
Anki decks, notes, and cards from within KOHighlights.

AnkiConnect API documentation: https://foosoft.net/projects/anki-connect/
"""

import json
import urllib.request
import urllib.error
from typing import Optional, List, Dict, Any, Tuple

__author__ = "KOHighlights"

# Default AnkiConnect settings
DEFAULT_ANKI_URL = "http://127.0.0.1:8765"
DEFAULT_ANKI_VERSION = 6

# Default note types
DEFAULT_NOTE_TYPE = "Makhfouz Highlight"
MAKHFOUZ_NOTE_TYPE = "Makhfouz Highlight"
DEFAULT_CLOZE_TYPE = "Cloze"

# Default field mappings for the Makhfouz note type
DEFAULT_FIELD_MAPPINGS = {
    "highlight": "Front",
    "comment": "Back",
    "book_title": "Source",
    "chapter": "Chapter",
    "page": "Page",
    "date": "Date",
    "author": "Author",
    "uid": "UID"
}


class AnkiConnectError(Exception):
    """Custom exception for AnkiConnect errors"""
    pass


class AnkiConnect:
    """
    A class to interface with AnkiConnect for managing Anki decks and cards.
    
    This class provides methods to:
    - Test connection to Anki
    - Get available decks and note types
    - Create decks and subdecks
    - Add notes/cards to decks
    - Update existing notes
    - Delete notes
    - Get deck statistics
    """
    
    def __init__(self, url: str = DEFAULT_ANKI_URL, version: int = DEFAULT_ANKI_VERSION):
        """
        Initialize AnkiConnect client.
        
        :param url: The URL where AnkiConnect is running
        :param version: The AnkiConnect API version to use
        """
        self.url = url
        self.version = version
        self._connected = False
        self._cached_note_types = None
        self._cached_decks = None
    
    def _request(self, action: str, **params) -> Any:
        """
        Send a request to AnkiConnect.
        
        :param action: The API action to perform
        :param params: Additional parameters for the action
        :return: The response from AnkiConnect
        :raises AnkiConnectError: If the request fails
        """
        request_data = {
            "action": action,
            "version": self.version,
        }
        if params:
            request_data["params"] = params
        
        try:
            request_json = json.dumps(request_data).encode('utf-8')
            req = urllib.request.Request(self.url, request_json)
            req.add_header('Content-Type', 'application/json')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
        except urllib.error.URLError as e:
            raise AnkiConnectError(f"Could not connect to Anki. Is Anki running with AnkiConnect? Error: {e}")
        except json.JSONDecodeError as e:
            raise AnkiConnectError(f"Invalid response from AnkiConnect: {e}")
        except Exception as e:
            raise AnkiConnectError(f"Unexpected error: {e}")
        
        if result.get("error"):
            raise AnkiConnectError(result["error"])
        
        return result.get("result")
    
    # ==================== Connection Methods ====================
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test the connection to AnkiConnect.
        
        :return: Tuple of (success: bool, message: str)
        """
        try:
            version = self._request("version")
            self._connected = True
            return True, f"Connected to AnkiConnect (version {version})"
        except AnkiConnectError as e:
            self._connected = False
            return False, str(e)
    
    def is_connected(self) -> bool:
        """Check if currently connected to Anki."""
        return self._connected
    
    def request_permission(self) -> bool:
        """
        Request permission to access AnkiConnect.
        Shows a dialog in Anki asking for permission.
        
        :return: True if permission granted
        """
        try:
            result = self._request("requestPermission")
            return result.get("permission") == "granted"
        except AnkiConnectError:
            return False
    
    def get_anki_version(self) -> str:
        """Get the version of Anki."""
        try:
            return str(self._request("version"))
        except AnkiConnectError:
            return "Unknown"
    
    # ==================== Deck Methods ====================
    
    def get_deck_names(self, force_refresh: bool = False) -> List[str]:
        """
        Get all deck names.
        
        :param force_refresh: Force refresh of cached deck names
        :return: List of deck names
        """
        if self._cached_decks is None or force_refresh:
            self._cached_decks = self._request("deckNames")
        return self._cached_decks or []
    
    def get_deck_names_and_ids(self) -> Dict[str, int]:
        """
        Get deck names and their IDs.
        
        :return: Dictionary mapping deck names to IDs
        """
        return self._request("deckNamesAndIds")
    
    def create_deck(self, deck_name: str) -> int:
        """
        Create a new deck.
        
        :param deck_name: Name of the deck to create (use :: for subdecks)
        :return: The ID of the created deck
        """
        result = self._request("createDeck", deck=deck_name)
        self._cached_decks = None  # Invalidate cache
        return result
    
    def delete_decks(self, deck_names: List[str], cards_too: bool = True) -> None:
        """
        Delete decks.
        
        :param deck_names: List of deck names to delete
        :param cards_too: Whether to delete cards in the decks
        """
        self._request("deleteDecks", decks=deck_names, cardsToo=cards_too)
        self._cached_decks = None  # Invalidate cache
    
    def get_deck_stats(self, deck_names: List[str]) -> Dict[str, Dict]:
        """
        Get statistics for decks.
        
        :param deck_names: List of deck names
        :return: Dictionary with deck statistics
        """
        return self._request("getDeckStats", decks=deck_names)
    
    def deck_exists(self, deck_name: str) -> bool:
        """
        Check if a deck exists.
        
        :param deck_name: Name of the deck to check
        :return: True if deck exists
        """
        return deck_name in self.get_deck_names()
    
    def create_deck_hierarchy(self, parent_deck: str, book_title: str) -> str:
        """
        Create a deck hierarchy for a book.
        Creates parent deck if it doesn't exist, and creates subdeck for book.
        
        :param parent_deck: The parent deck name (e.g., "KOHighlights")
        :param book_title: The book title for the subdeck
        :return: Full deck path (e.g., "KOHighlights::Book Title")
        """
        # Sanitize book title for deck name
        safe_title = self._sanitize_deck_name(book_title)
        full_deck_name = f"{parent_deck}::{safe_title}" if parent_deck else safe_title
        
        # Create the deck (AnkiConnect will create parent decks automatically)
        self.create_deck(full_deck_name)
        return full_deck_name
    
    @staticmethod
    def _sanitize_deck_name(name: str) -> str:
        """
        Sanitize a string for use as a deck name.
        
        :param name: The name to sanitize
        :return: Sanitized deck name
        """
        # Remove or replace invalid characters
        invalid_chars = [':', '"', '*', '/', '\\', '<', '>', '|', '?']
        result = name
        for char in invalid_chars:
            result = result.replace(char, '_')
        return result.strip()
    
    # ==================== Note Type Methods ====================
    
    def get_model_names(self, force_refresh: bool = False) -> List[str]:
        """
        Get all note type (model) names.
        
        :param force_refresh: Force refresh of cached model names
        :return: List of note type names
        """
        if self._cached_note_types is None or force_refresh:
            self._cached_note_types = self._request("modelNames")
        return self._cached_note_types or []
    
    def get_model_names_and_ids(self) -> Dict[str, int]:
        """
        Get note type names and their IDs.
        
        :return: Dictionary mapping model names to IDs
        """
        return self._request("modelNamesAndIds")
    
    def get_model_field_names(self, model_name: str) -> List[str]:
        """
        Get field names for a note type.
        
        :param model_name: Name of the note type
        :return: List of field names
        """
        return self._request("modelFieldNames", modelName=model_name)

    def add_field_to_model(self, model_name: str, field_name: str, index: Optional[int] = None):
        """Add a field to an existing note type if supported by AnkiConnect."""
        params = {"modelName": model_name, "fieldName": field_name}
        if index is not None:
            params["index"] = index
        self._request("modelFieldAdd", **params)

    def create_model(self, name: str, fields: List[str], css: str, templates: List[Dict[str, Any]]):
        """
        Create a custom note model.
        
        :param name: Model name
        :param fields: List of field names
        :param css: CSS styling
        :param templates: Card templates definitions
        """
        return self._request("createModel", modelName=name, inOrderFields=fields,
                              css=css, cardTemplates=templates)

    def ensure_makhfouz_model(self, field_mapping: Dict[str, str]):
        """Ensure the custom Makhfouz note type exists with expected fields/templates."""
        try:
            models = self.get_model_names()
        except AnkiConnectError:
            pass

        fields = ["Front", "Back", "Source", "Author", "Chapter", "Page", "Date", "UID"]

        css = """
        .card {
            font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
            font-size: 17px;
            color: #1f2933;
            background: #e5e7eb;
        }
        .card-body {
            max-width: 720px;
            margin: 0 auto;
            padding: 18px;
        }
        .panel {
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 12px 28px rgba(15, 23, 42, 0.12);
            border: 1px solid #e5e7eb;
            padding: 18px 20px;
        }
        .comment {
            font-weight: 600;
            line-height: 1.6;
            color: #111827;
        }
        .comment.empty {
            font-weight: 500;
            color: #6b7280;
        }
        .title {
            text-align: center;
            font-size: 14px;
            font-weight: 600;
            letter-spacing: 0.01em;
            color: #334155;
            margin: 6px 0 10px;
        }
        .divider {
            margin: 16px 0 12px;
            border: none;
            border-top: 1px solid #e5e7eb;
        }
        .divider.short {
            width: 46px;
            margin: 14px auto;
        }
        .highlight {
            background: #ffffff;
            border-radius: 10px;
            padding: 6px 0;
            font-family: 'Georgia', 'Times New Roman', serif;
            font-size: 18px;
            line-height: 1.7;
            color: #0f172a;
            text-align: left;
        }
        .highlight p { margin: 0 0 12px; }
        .highlight p:last-child { margin-bottom: 0; }
        .author {
            margin-top: 12px;
            font-size: 14px;
            color: #475569;
            text-align: left;
            font-style: italic;
        }
        .pagech {
            margin-top: 10px;
            font-size: 13px;
            color: #475569;
            text-align: center;
        }
        .date {
            margin-top: 8px;
            font-size: 12px;
            color: #6b7280;
            text-align: left;
        }
        """

        front_template = {
            "Name": "Card 1",
            "Front": """
<div class="card-body">
    <div class="panel">
        {{#Back}}
        <div class="comment">{{Back}}</div>
        {{/Back}}
        {{^Back}}
            {{#Front}}
            <div class="comment">{{Front}}</div>
            {{/Front}}
            {{^Front}}
            <div class="comment empty">💬 Keine Notiz</div>
            {{/Front}}
        {{/Back}}
        <hr class="divider short">
        {{#Source}}<div class="title">{{Source}}</div>{{/Source}}
    </div>
</div>
""",
            "Back": """
{{FrontSide}}
<hr class="divider" id="answer">
<div class="card-body">
    <div class="panel">
        {{#Source}}<div class="title">{{Source}}</div>{{/Source}}
        {{#Front}}<div class="highlight">{{Front}}</div>{{/Front}}
        {{#Author}}<div class="author">~{{Author}}</div>{{/Author}}
        {{#Page}}{{#Chapter}}<div class="pagech">{{Page}} – {{Chapter}}</div>{{/Chapter}}{{/Page}}
        {{#Page}}{{^Chapter}}<div class="pagech">{{Page}}</div>{{/Chapter}}{{/Page}}
        {{^Page}}{{#Chapter}}<div class="pagech">{{Chapter}}</div>{{/Chapter}}{{/Page}}
        {{#Date}}<div class="date">{{Date}}</div>{{/Date}}
    </div>
</div>
"""
        }

        # If model exists, update styling/templates instead of recreating
        try:
            if MAKHFOUZ_NOTE_TYPE in (models if 'models' in locals() else []):
                try:
                    existing_fields = self.get_model_field_names(MAKHFOUZ_NOTE_TYPE)
                    missing_fields = [f for f in fields if f not in existing_fields]
                    for mf in missing_fields:
                        try:
                            self.add_field_to_model(MAKHFOUZ_NOTE_TYPE, mf)
                        except AnkiConnectError:
                            pass

                    self._request("updateModelStyling", model={"name": MAKHFOUZ_NOTE_TYPE, "css": css})
                    self._request("updateModelTemplates", model={
                        "name": MAKHFOUZ_NOTE_TYPE,
                        "templates": {
                            "Card 1": {
                                "Front": front_template["Front"],
                                "Back": front_template["Back"],
                            }
                        }
                    })
                except AnkiConnectError:
                    pass
                return
        except AnkiConnectError:
            pass

        try:
            self.create_model(MAKHFOUZ_NOTE_TYPE, fields, css, [front_template])
        except AnkiConnectError:
            # If model creation fails (e.g., insufficient permissions), just continue;
            # user can select an existing model.
            pass
    
    def get_model_templates(self, model_name: str) -> Dict:
        """
        Get card templates for a note type.
        
        :param model_name: Name of the note type
        :return: Dictionary with template information
        """
        return self._request("modelTemplates", modelName=model_name)
    
    # ==================== Note Methods ====================
    
    def add_note(self, deck_name: str, model_name: str, fields: Dict[str, str],
                 tags: Optional[List[str]] = None, allow_duplicate: bool = False,
                 duplicate_scope: str = "deck") -> int:
        """
        Add a new note to a deck.
        
        :param deck_name: Name of the deck
        :param model_name: Name of the note type
        :param fields: Dictionary of field names and values
        :param tags: Optional list of tags
        :param allow_duplicate: Allow duplicate notes
        :param duplicate_scope: Scope for duplicate checking ("deck" or "collection")
        :return: Note ID
        """
        note = {
            "deckName": deck_name,
            "modelName": model_name,
            "fields": fields,
            "options": {
                "allowDuplicate": allow_duplicate,
                "duplicateScope": duplicate_scope,
            }
        }
        if tags:
            note["tags"] = tags
        
        return self._request("addNote", note=note)
    
    def add_notes(self, notes: List[Dict]) -> List[Optional[int]]:
        """
        Add multiple notes at once.
        
        :param notes: List of note dictionaries
        :return: List of note IDs (None for failed notes)
        """
        return self._request("addNotes", notes=notes)
    
    def can_add_notes(self, notes: List[Dict]) -> List[bool]:
        """
        Check if notes can be added (e.g., not duplicates).
        
        :param notes: List of note dictionaries
        :return: List of booleans indicating if each note can be added
        """
        return self._request("canAddNotes", notes=notes)
    
    def update_note_fields(self, note_id: int, fields: Dict[str, str]) -> None:
        """
        Update the fields of an existing note.
        
        :param note_id: ID of the note to update
        :param fields: Dictionary of field names and new values
        """
        self._request("updateNoteFields", note={"id": note_id, "fields": fields})
    
    def delete_notes(self, note_ids: List[int]) -> None:
        """
        Delete notes by their IDs.
        
        :param note_ids: List of note IDs to delete
        """
        self._request("deleteNotes", notes=note_ids)
    
    def find_notes(self, query: str) -> List[int]:
        """
        Find notes matching a query.
        
        :param query: Anki search query
        :return: List of matching note IDs
        """
        return self._request("findNotes", query=query)
    
    def get_notes_info(self, note_ids: List[int]) -> List[Dict]:
        """
        Get information about notes.
        
        :param note_ids: List of note IDs
        :return: List of note information dictionaries
        """
        return self._request("notesInfo", notes=note_ids)
    
    def add_tags(self, note_ids: List[int], tags: str) -> None:
        """
        Add tags to notes.
        
        :param note_ids: List of note IDs
        :param tags: Space-separated tags to add
        """
        self._request("addTags", notes=note_ids, tags=tags)
    
    def remove_tags(self, note_ids: List[int], tags: str) -> None:
        """
        Remove tags from notes.
        
        :param note_ids: List of note IDs
        :param tags: Space-separated tags to remove
        """
        self._request("removeTags", notes=note_ids, tags=tags)
    
    def get_tags(self) -> List[str]:
        """
        Get all tags in the collection.
        
        :return: List of tags
        """
        return self._request("getTags")
    
    # ==================== Card Methods ====================
    
    def find_cards(self, query: str) -> List[int]:
        """
        Find cards matching a query.
        
        :param query: Anki search query
        :return: List of matching card IDs
        """
        return self._request("findCards", query=query)
    
    def get_cards_info(self, card_ids: List[int]) -> List[Dict]:
        """
        Get information about cards.
        
        :param card_ids: List of card IDs
        :return: List of card information dictionaries
        """
        return self._request("cardsInfo", cards=card_ids)
    
    def suspend_cards(self, card_ids: List[int]) -> bool:
        """
        Suspend cards.
        
        :param card_ids: List of card IDs
        :return: True if successful
        """
        return self._request("suspend", cards=card_ids)
    
    def unsuspend_cards(self, card_ids: List[int]) -> bool:
        """
        Unsuspend cards.
        
        :param card_ids: List of card IDs
        :return: True if successful
        """
        return self._request("unsuspend", cards=card_ids)
    
    # ==================== GUI Methods ====================
    
    def gui_browse(self, query: str) -> List[int]:
        """
        Open the card browser in Anki with a query.
        
        :param query: Search query
        :return: List of card IDs shown
        """
        return self._request("guiBrowse", query=query)
    
    def gui_deck_overview(self, deck_name: str) -> bool:
        """
        Show deck overview in Anki.
        
        :param deck_name: Name of the deck
        :return: True if successful
        """
        return self._request("guiDeckOverview", name=deck_name)
    
    def gui_show_answer(self) -> bool:
        """Show the answer on the current card."""
        return self._request("guiShowAnswer")
    
    def gui_current_card(self) -> Optional[Dict]:
        """Get information about the current card being reviewed."""
        return self._request("guiCurrentCard")
    
    # ==================== Media Methods ====================
    
    def store_media_file(self, filename: str, data: Optional[str] = None,
                         path: Optional[str] = None, url: Optional[str] = None) -> str:
        """
        Store a media file in Anki's media folder.
        
        :param filename: Name for the file
        :param data: Base64 encoded file data
        :param path: Path to file on disk
        :param url: URL to download file from
        :return: Actual filename used
        """
        params = {"filename": filename}
        if data:
            params["data"] = data
        elif path:
            params["path"] = path
        elif url:
            params["url"] = url
        return self._request("storeMediaFile", **params)
    
    # ==================== Sync Methods ====================
    
    def sync(self) -> None:
        """Trigger a sync with AnkiWeb."""
        self._request("sync")
    
    # ==================== Helper Methods for Highlights ====================
    
    def create_highlight_note(self, deck_name: str, model_name: str,
                              highlight_data: Dict, field_mapping: Dict[str, str],
                              tags: Optional[List[str]] = None,
                              allow_duplicate: bool = False) -> Optional[int]:
        """
        Create a note from highlight data using field mapping.
        
        :param deck_name: Target deck name
        :param model_name: Note type name
        :param highlight_data: Dictionary with highlight information
                              (highlight, comment, page, chapter, date, book_title, author)
        :param field_mapping: Dictionary mapping highlight fields to note fields
        :param tags: Optional tags to add
        :param allow_duplicate: Allow duplicate notes
        :return: Note ID or None if failed
        """
        # Get available fields for the model
        available_fields = self.get_model_field_names(model_name)
        
        # Build the fields dictionary based on mapping
        fields = {field: "" for field in available_fields}  # Initialize all fields
        
        for source_field, target_field in field_mapping.items():
            if target_field in available_fields:
                value = highlight_data.get(source_field, "")
                if value:
                    # If field already has content, append with separator
                    if fields[target_field]:
                        fields[target_field] += f"<br><br>{value}"
                    else:
                        fields[target_field] = value
        
        try:
            return self.add_note(deck_name, model_name, fields, tags, allow_duplicate)
        except AnkiConnectError:
            return None
    
    def bulk_add_highlights(self, deck_name: str, model_name: str,
                            highlights: List[Dict], field_mapping: Dict[str, str],
                            tags: Optional[List[str]] = None,
                            allow_duplicate: bool = False,
                            progress_callback: Optional[callable] = None,
                            front_content: str = "comment") -> Tuple[int, int, List[str]]:
        """
        Add multiple highlights as notes.
        
        :param deck_name: Target deck name
        :param model_name: Note type name
        :param highlights: List of highlight data dictionaries
        :param field_mapping: Dictionary mapping highlight fields to note fields
        :param tags: Optional tags to add
        :param allow_duplicate: Allow duplicate notes
        :param progress_callback: Optional callback(current, total) for progress updates
        :return: Tuple of (success_count, fail_count, error_messages)
        """
        # Get available fields for the model
        available_fields = self.get_model_field_names(model_name)

        # Adapt mapping to available fields to avoid dropping all content
        def pick_fallback(preferred: List[str]) -> Optional[str]:
            for name in preferred:
                if name in available_fields:
                    return name
            return available_fields[0] if available_fields else None

        if not available_fields:
            raise AnkiConnectError("Selected note type has no fields.")

        remapped_mapping: Dict[str, str] = {}
        for source, target in field_mapping.items():
            if target in available_fields:
                remapped_mapping[source] = target
            else:
                # choose sensible fallback
                if source == "highlight":
                    fallback = pick_fallback(["Front", available_fields[0] if available_fields else None])
                elif source == "comment":
                    fallback = pick_fallback(["Back", "Front", available_fields[0] if available_fields else None])
                else:
                    fallback = pick_fallback(["Back", "Front", available_fields[-1] if available_fields else None])
                if fallback:
                    remapped_mapping[source] = fallback

        # Ensure highlight/comment always have a target
        if "highlight" not in remapped_mapping:
            remapped_mapping["highlight"] = pick_fallback(["Front", available_fields[0]])
        if "comment" not in remapped_mapping:
            remapped_mapping["comment"] = pick_fallback(["Back", "Front", available_fields[min(1, len(available_fields)-1)]])

        # Prepare all notes
        notes = []
        note_debugs = []  # keep debug info aligned with notes list
        skipped_empty = 0
        success_count = 0
        fail_count = 0
        errors = []
        total_items = len(highlights)
        processed = 0

        highlight_field_name = remapped_mapping.get("highlight")
        comment_field_name = remapped_mapping.get("comment")

        for highlight_data in highlights:
            # Drop notes with no textual content up front
            base_highlight = str(highlight_data.get("highlight", highlight_data.get("text", "")) or "").strip()
            base_comment = str(highlight_data.get("comment", "") or "").strip()
            if not (base_highlight or base_comment):
                skipped_empty += 1
                processed += 1
                if progress_callback:
                    progress_callback(processed, total_items)
                continue

            fields = {field: "" for field in available_fields}
            
            for source_field, target_field in remapped_mapping.items():
                if target_field in available_fields:
                    value = highlight_data.get(source_field, "")
                    if value:
                        if fields[target_field]:
                            fields[target_field] += f"<br><br>{value}"
                        else:
                            fields[target_field] = value

            # If still empty after mapping, force a fallback placement of base text
            if not any(str(val).strip() for val in fields.values()):
                fallback_field = highlight_field_name or available_fields[0]
                fields[fallback_field] = base_highlight or base_comment
            # If there is no comment, copy the highlight into the comment field (keep highlight field intact for Front)
            if not base_comment and base_highlight:
                target_comment_field = comment_field_name
                if not target_comment_field:
                    target_comment_field = "Back" if "Back" in available_fields else pick_fallback([available_fields[0]])
                if target_comment_field:
                    fields[target_comment_field] = base_highlight

            # Apply front/back preference
            if front_content == "highlight" and highlight_field_name:
                highlight_val = fields.get(highlight_field_name, "")
                comment_val = fields.get(comment_field_name, fields.get("Back", ""))
                if highlight_val:
                    fields["Front"] = highlight_val
                if comment_val:
                    fields["Back"] = comment_val

            # Final guard: if still empty after front/back adjustments, skip
            if not any(str(val).strip() for val in fields.values()):
                skipped_empty += 1
                processed += 1
                if progress_callback:
                    progress_callback(processed, total_items)
                continue

            note = {
                "deckName": deck_name,
                "modelName": model_name,
                "fields": fields,
                "options": {
                    "allowDuplicate": allow_duplicate,
                    "duplicateScope": "deck",
                }
            }
            if tags:
                note["tags"] = tags
            notes.append(note)

            # capture debug info for clearer error messages
            note_debugs.append({
                "front": fields.get("Front", ""),
                "back": fields.get("Back", ""),
                "highlight": base_highlight,
                "comment": base_comment,
                "book": highlight_data.get("book_title") or highlight_data.get("title") or "",
                "chapter": str(highlight_data.get("chapter", "")),
                "page": str(highlight_data.get("page", "")),
            })
        
        # Add remaining notes (without UID) in batches
        batch_size = 50  # Add notes in batches of 50
        
        for i in range(0, len(notes), batch_size):
            batch = notes[i:i + batch_size]
            debug_batch = note_debugs[i:i + batch_size]

            # If duplicates are disallowed, pre-check which notes can be added
            eligible_batch = batch
            eligible_debug = debug_batch
            if not allow_duplicate:
                try:
                    eligibility = self.can_add_notes(batch)
                    eligible_batch = []
                    eligible_debug = []
                    for note, dbg, ok in zip(batch, debug_batch, eligibility):
                        if ok:
                            eligible_batch.append(note)
                            eligible_debug.append(dbg)
                        else:
                            fail_count += 1
                            front_preview = dbg.get("front") or dbg.get("highlight") or ""
                            back_preview = dbg.get("back") or dbg.get("comment") or ""
                            book = dbg.get("book", "")
                            chapter = dbg.get("chapter", "")
                            page = dbg.get("page", "")
                            errors.append(
                                f"Duplicate skipped @batch {i//batch_size+1}: book='{book}' chapter='{chapter}' page='{page}' front='{front_preview[:80]}' back='{back_preview[:80]}'"
                            )
                except AnkiConnectError:
                    # If canAddNotes fails, fall back to attempting addNotes
                    eligible_batch = batch
                    eligible_debug = debug_batch

            try:
                if not eligible_batch:
                    processed += len(batch)
                    if progress_callback:
                        progress_callback(processed, total_items)
                    continue

                results = self.add_notes(eligible_batch)
                for j, result in enumerate(results):
                    if result is not None:
                        success_count += 1
                    else:
                        fail_count += 1
                        dbg = eligible_debug[j] if j < len(eligible_debug) else {}
                        front_preview = dbg.get("front") or dbg.get("highlight") or ""
                        back_preview = dbg.get("back") or dbg.get("comment") or ""
                        book = dbg.get("book", "")
                        chapter = dbg.get("chapter", "")
                        page = dbg.get("page", "")
                        errors.append(
                            f"Failed to add note @batch {i//batch_size+1}, idx {j+1}: book='{book}' chapter='{chapter}' page='{page}' front='{front_preview[:80]}' back='{back_preview[:80]}'"
                        )
            except AnkiConnectError as e:
                fail_count += len(batch)
                errors.append(str(e))
            
            processed += len(batch)
            if progress_callback:
                progress_callback(processed, total_items)
        
        # Account for skipped empties
        if skipped_empty:
            fail_count += skipped_empty
            errors.append(f"Skipped {skipped_empty} empty highlight(s)")
        return success_count, fail_count, errors


# Singleton instance for easy access
_anki_instance: Optional[AnkiConnect] = None


def get_anki_connect(url: str = DEFAULT_ANKI_URL) -> AnkiConnect:
    """
    Get or create an AnkiConnect instance.
    
    :param url: The URL where AnkiConnect is running
    :return: AnkiConnect instance
    """
    global _anki_instance
    if _anki_instance is None or _anki_instance.url != url:
        _anki_instance = AnkiConnect(url)
    return _anki_instance


# Export all public symbols
__all__ = [
    "AnkiConnect",
    "AnkiConnectError", 
    "get_anki_connect",
    "DEFAULT_ANKI_URL",
    "DEFAULT_ANKI_VERSION",
    "DEFAULT_NOTE_TYPE",
    "DEFAULT_CLOZE_TYPE",
    "DEFAULT_FIELD_MAPPINGS"
]
