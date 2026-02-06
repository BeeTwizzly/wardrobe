"""Tests for outfits.py - wardrobe manifest formatting and wear-history filtering."""

import pytest

from db import add_item, get_connection, init_db, log_wear
from outfits import build_wardrobe_manifest, format_locked_items, get_available_items


@pytest.fixture
def conn(tmp_path):
    """Create a fresh database for each test."""
    db_path = tmp_path / "test.db"
    connection = get_connection(db_path)
    init_db(connection)
    yield connection
    connection.close()


# --- Wardrobe manifest formatting ---


class TestBuildManifest:
    def test_basic_manifest(self):
        items = [
            {
                "id": 1,
                "name": "Navy Blue Oxford",
                "category": "top",
                "subcategory": "oxford-shirt",
                "colors": ["navy blue"],
                "pattern": "solid",
                "material": "cotton",
                "formality": 4,
                "seasons": ["fall", "winter", "spring"],
            },
            {
                "id": 5,
                "name": "Dark Wash Jeans",
                "category": "bottom",
                "subcategory": "jeans",
                "colors": ["dark indigo"],
                "pattern": "solid",
                "material": "denim",
                "formality": 2,
                "seasons": ["fall", "winter", "spring"],
            },
        ]
        manifest = build_wardrobe_manifest(items)
        lines = manifest.strip().split("\n")
        assert len(lines) == 2
        assert "ID:1" in lines[0]
        assert "Navy Blue Oxford" in lines[0]
        assert "top/oxford-shirt" in lines[0]
        assert "navy blue" in lines[0]
        assert "formality:4" in lines[0]
        assert "ID:5" in lines[1]

    def test_empty_manifest(self):
        manifest = build_wardrobe_manifest([])
        assert manifest == ""

    def test_multiple_colors(self):
        items = [
            {
                "id": 1,
                "name": "Striped Shirt",
                "category": "top",
                "subcategory": "dress-shirt",
                "colors": ["white", "blue"],
                "pattern": "striped",
                "material": "cotton",
                "formality": 4,
                "seasons": ["spring", "summer"],
            },
        ]
        manifest = build_wardrobe_manifest(items)
        assert "white, blue" in manifest

    def test_missing_fields_handled(self):
        """Manifest should handle items with missing optional fields."""
        items = [
            {
                "id": 1,
                "name": "Basic Item",
                "category": "top",
            },
        ]
        manifest = build_wardrobe_manifest(items)
        assert "ID:1" in manifest
        assert "Basic Item" in manifest


# --- Locked items formatting ---


class TestFormatLocked:
    def test_no_locked_items(self):
        assert format_locked_items([]) == "None"

    def test_locked_items(self):
        items = [
            {"id": 1, "name": "Blue Jacket", "category": "outerwear"},
            {"id": 3, "name": "White Sneakers", "category": "shoes"},
        ]
        text = format_locked_items(items)
        assert "ID:1" in text
        assert "Blue Jacket" in text
        assert "ID:3" in text
        assert "outerwear" in text


# --- Wear-history filtering ---


class TestGetAvailableItems:
    def test_all_items_available_when_none_worn(self, conn):
        add_item(conn, image_filename="a.jpg", name="Item A", category="top")
        add_item(conn, image_filename="b.jpg", name="Item B", category="bottom")
        available = get_available_items(conn, no_repeat_days=7)
        assert len(available) == 2

    def test_recently_worn_excluded(self, conn):
        id1 = add_item(conn, image_filename="a.jpg", name="Worn", category="top")
        id2 = add_item(conn, image_filename="b.jpg", name="Fresh", category="top")

        from datetime import date
        log_wear(conn, id1, date_worn=date.today().isoformat())

        available = get_available_items(conn, no_repeat_days=7)
        available_ids = {item["id"] for item in available}
        assert id1 not in available_ids
        assert id2 in available_ids

    def test_exclude_ids(self, conn):
        id1 = add_item(conn, image_filename="a.jpg", name="Excluded", category="top")
        id2 = add_item(conn, image_filename="b.jpg", name="Available", category="top")

        available = get_available_items(conn, no_repeat_days=7, exclude_ids={id1})
        available_ids = {item["id"] for item in available}
        assert id1 not in available_ids
        assert id2 in available_ids

    def test_archived_items_excluded(self, conn):
        from db import update_item

        id1 = add_item(conn, image_filename="a.jpg", name="Active", category="top")
        id2 = add_item(conn, image_filename="b.jpg", name="Archived", category="top")
        update_item(conn, id2, active=0)

        available = get_available_items(conn, no_repeat_days=7)
        available_ids = {item["id"] for item in available}
        assert id1 in available_ids
        assert id2 not in available_ids

    def test_no_repeat_window_respected(self, conn):
        """Items worn outside the no-repeat window should be available."""
        from datetime import date, timedelta

        item_id = add_item(conn, image_filename="a.jpg", name="Test", category="top")
        # Worn 10 days ago
        worn_date = (date.today() - timedelta(days=10)).isoformat()
        log_wear(conn, item_id, date_worn=worn_date)

        # With 7-day window, item should be available
        available = get_available_items(conn, no_repeat_days=7)
        available_ids = {item["id"] for item in available}
        assert item_id in available_ids

        # With 14-day window, item should be excluded
        available = get_available_items(conn, no_repeat_days=14)
        available_ids = {item["id"] for item in available}
        assert item_id not in available_ids
