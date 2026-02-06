"""Tests for db.py - schema creation, CRUD operations, wear log, settings."""

import sqlite3
from pathlib import Path

import pytest

from db import (
    add_item,
    clear_all_data,
    delete_item,
    get_all_items,
    get_all_settings,
    get_battle_history,
    get_battle_item_stats,
    get_connection,
    get_forgotten_items,
    get_item,
    get_item_count_by_category,
    get_items_worn_recently,
    get_last_worn_date,
    get_least_worn_items,
    get_most_worn_items,
    get_setting,
    get_wear_log,
    init_db,
    log_wear,
    rate_outfit,
    save_battle,
    save_outfit,
    set_setting,
    update_item,
)


@pytest.fixture
def conn(tmp_path):
    """Create a fresh in-memory database for each test."""
    db_path = tmp_path / "test.db"
    connection = get_connection(db_path)
    init_db(connection)
    yield connection
    connection.close()


# --- Schema creation ---


class TestSchema:
    def test_tables_exist(self, conn):
        """All five tables should be created."""
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {row["name"] for row in tables}
        assert "wardrobe_items" in table_names
        assert "outfits" in table_names
        assert "wear_log" in table_names
        assert "user_settings" in table_names
        assert "battles" in table_names

    def test_default_settings_seeded(self, conn):
        """Default settings should be seeded on init."""
        settings = get_all_settings(conn)
        assert settings["location_lat"] == "39.89"
        assert settings["location_lon"] == "-86.16"
        assert settings["location_name"] == "Indianapolis, IN"
        assert settings["no_repeat_days"] == "7"
        assert settings["style_vibe"] == "smart casual"

    def test_init_db_idempotent(self, conn):
        """Calling init_db multiple times should not fail or duplicate settings."""
        init_db(conn)
        init_db(conn)
        settings = get_all_settings(conn)
        assert settings["location_lat"] == "39.89"


# --- Settings CRUD ---


class TestSettings:
    def test_get_setting(self, conn):
        assert get_setting(conn, "location_lat") == "39.89"

    def test_get_setting_default(self, conn):
        assert get_setting(conn, "nonexistent", "fallback") == "fallback"

    def test_set_setting(self, conn):
        set_setting(conn, "location_name", "New York, NY")
        assert get_setting(conn, "location_name") == "New York, NY"

    def test_set_setting_overwrite(self, conn):
        set_setting(conn, "no_repeat_days", "14")
        assert get_setting(conn, "no_repeat_days") == "14"

    def test_get_all_settings(self, conn):
        all_settings = get_all_settings(conn)
        assert isinstance(all_settings, dict)
        assert len(all_settings) >= 5


# --- Wardrobe Items CRUD ---


class TestItems:
    def test_add_item(self, conn):
        item_id = add_item(
            conn,
            image_filename="test.jpg",
            name="Blue Oxford",
            category="top",
            subcategory="oxford-shirt",
            colors=["navy blue"],
            pattern="solid",
            material="cotton",
            formality=4,
            seasons=["fall", "winter", "spring"],
            notes="test item",
        )
        assert item_id is not None
        assert item_id > 0

    def test_get_item(self, conn):
        item_id = add_item(conn, image_filename="test.jpg", name="Blue Oxford", category="top")
        item = get_item(conn, item_id)
        assert item is not None
        assert item["name"] == "Blue Oxford"
        assert item["category"] == "top"
        assert isinstance(item["colors"], list)
        assert isinstance(item["seasons"], list)

    def test_get_item_not_found(self, conn):
        assert get_item(conn, 99999) is None

    def test_get_all_items(self, conn):
        add_item(conn, image_filename="a.jpg", name="Item A", category="top")
        add_item(conn, image_filename="b.jpg", name="Item B", category="bottom")
        items = get_all_items(conn)
        assert len(items) == 2

    def test_get_all_items_active_only(self, conn):
        id1 = add_item(conn, image_filename="a.jpg", name="Active", category="top")
        id2 = add_item(conn, image_filename="b.jpg", name="Archived", category="top")
        update_item(conn, id2, active=0)

        active = get_all_items(conn, active_only=True)
        assert len(active) == 1
        assert active[0]["name"] == "Active"

        all_items = get_all_items(conn, active_only=False)
        assert len(all_items) == 2

    def test_get_all_items_category_filter(self, conn):
        add_item(conn, image_filename="a.jpg", name="Top", category="top")
        add_item(conn, image_filename="b.jpg", name="Bottom", category="bottom")
        tops = get_all_items(conn, category="top")
        assert len(tops) == 1
        assert tops[0]["category"] == "top"

    def test_get_all_items_formality_filter(self, conn):
        add_item(conn, image_filename="a.jpg", name="Casual", category="top", formality=1)
        add_item(conn, image_filename="b.jpg", name="Formal", category="top", formality=5)
        items = get_all_items(conn, formality_min=4, formality_max=5)
        assert len(items) == 1
        assert items[0]["name"] == "Formal"

    def test_get_all_items_season_filter(self, conn):
        add_item(
            conn,
            image_filename="a.jpg",
            name="Summer",
            category="top",
            seasons=["summer"],
        )
        add_item(
            conn,
            image_filename="b.jpg",
            name="Winter",
            category="top",
            seasons=["winter"],
        )
        items = get_all_items(conn, seasons=["summer"])
        assert len(items) == 1
        assert items[0]["name"] == "Summer"

    def test_update_item(self, conn):
        item_id = add_item(conn, image_filename="a.jpg", name="Old Name", category="top")
        success = update_item(conn, item_id, name="New Name", formality=5)
        assert success
        item = get_item(conn, item_id)
        assert item["name"] == "New Name"
        assert item["formality"] == 5

    def test_update_item_colors(self, conn):
        item_id = add_item(conn, image_filename="a.jpg", name="Test", category="top")
        update_item(conn, item_id, colors=["red", "blue"])
        item = get_item(conn, item_id)
        assert item["colors"] == ["red", "blue"]

    def test_update_item_no_fields(self, conn):
        item_id = add_item(conn, image_filename="a.jpg", name="Test", category="top")
        assert not update_item(conn, item_id)

    def test_delete_item(self, conn):
        item_id = add_item(conn, image_filename="a.jpg", name="Test", category="top")
        assert delete_item(conn, item_id)
        assert get_item(conn, item_id) is None

    def test_delete_item_cascades_wear_log(self, conn):
        item_id = add_item(conn, image_filename="a.jpg", name="Test", category="top")
        log_wear(conn, item_id, date_worn="2024-01-01")
        delete_item(conn, item_id)
        entries = get_wear_log(conn, item_id=item_id)
        assert len(entries) == 0

    def test_get_item_count_by_category(self, conn):
        add_item(conn, image_filename="a.jpg", name="Top 1", category="top")
        add_item(conn, image_filename="b.jpg", name="Top 2", category="top")
        add_item(conn, image_filename="c.jpg", name="Bottom 1", category="bottom")
        counts = get_item_count_by_category(conn)
        assert counts["top"] == 2
        assert counts["bottom"] == 1


# --- Outfits CRUD ---


class TestOutfits:
    def test_save_outfit(self, conn):
        outfit_id = save_outfit(
            conn,
            name="Test Outfit",
            occasion="everyday",
            weather_summary="70F, Clear",
            item_ids=[1, 2, 3],
            reasoning="test reasoning",
        )
        assert outfit_id is not None
        assert outfit_id > 0

    def test_rate_outfit(self, conn):
        outfit_id = save_outfit(
            conn,
            name="Test",
            occasion="work",
            weather_summary="",
            item_ids=[],
            reasoning="",
        )
        assert rate_outfit(conn, outfit_id, 4)
        row = conn.execute(
            "SELECT rating FROM outfits WHERE id = ?", (outfit_id,)
        ).fetchone()
        assert row["rating"] == 4


# --- Wear Log ---


class TestWearLog:
    def test_log_wear(self, conn):
        item_id = add_item(conn, image_filename="a.jpg", name="Test", category="top")
        assert log_wear(conn, item_id, date_worn="2024-06-15")

    def test_log_wear_uniqueness(self, conn):
        """Same item can't be logged twice for the same date."""
        item_id = add_item(conn, image_filename="a.jpg", name="Test", category="top")
        assert log_wear(conn, item_id, date_worn="2024-06-15")
        assert not log_wear(conn, item_id, date_worn="2024-06-15")

    def test_log_wear_different_dates(self, conn):
        """Same item CAN be logged for different dates."""
        item_id = add_item(conn, image_filename="a.jpg", name="Test", category="top")
        assert log_wear(conn, item_id, date_worn="2024-06-15")
        assert log_wear(conn, item_id, date_worn="2024-06-16")

    def test_get_wear_log(self, conn):
        item_id = add_item(conn, image_filename="a.jpg", name="Test", category="top")
        log_wear(conn, item_id, date_worn="2024-06-15")
        entries = get_wear_log(conn, item_id=item_id)
        assert len(entries) == 1

    def test_get_wear_log_date_range(self, conn):
        item_id = add_item(conn, image_filename="a.jpg", name="Test", category="top")
        log_wear(conn, item_id, date_worn="2024-06-10")
        log_wear(conn, item_id, date_worn="2024-06-20")
        entries = get_wear_log(conn, start_date="2024-06-15", end_date="2024-06-25")
        assert len(entries) == 1
        assert entries[0]["date_worn"] == "2024-06-20"

    def test_get_last_worn_date(self, conn):
        item_id = add_item(conn, image_filename="a.jpg", name="Test", category="top")
        log_wear(conn, item_id, date_worn="2024-06-10")
        log_wear(conn, item_id, date_worn="2024-06-20")
        assert get_last_worn_date(conn, item_id) == "2024-06-20"

    def test_get_last_worn_date_none(self, conn):
        item_id = add_item(conn, image_filename="a.jpg", name="Test", category="top")
        assert get_last_worn_date(conn, item_id) is None

    def test_get_items_worn_recently(self, conn):
        item_id = add_item(conn, image_filename="a.jpg", name="Test", category="top")
        from datetime import date, timedelta

        today = date.today().isoformat()
        log_wear(conn, item_id, date_worn=today)
        recent = get_items_worn_recently(conn, days=7)
        assert item_id in recent

    def test_get_most_worn_items(self, conn):
        id1 = add_item(conn, image_filename="a.jpg", name="Popular", category="top")
        id2 = add_item(conn, image_filename="b.jpg", name="Rare", category="top")
        log_wear(conn, id1, date_worn="2024-06-10")
        log_wear(conn, id1, date_worn="2024-06-11")
        log_wear(conn, id2, date_worn="2024-06-10")
        most = get_most_worn_items(conn, limit=5)
        assert most[0]["name"] == "Popular"

    def test_get_least_worn_items(self, conn):
        id1 = add_item(conn, image_filename="a.jpg", name="Popular", category="top")
        id2 = add_item(conn, image_filename="b.jpg", name="Rare", category="top")
        log_wear(conn, id1, date_worn="2024-06-10")
        log_wear(conn, id1, date_worn="2024-06-11")
        least = get_least_worn_items(conn, limit=5)
        assert least[0]["name"] == "Rare"


# --- Clear all data ---


class TestClearData:
    def test_clear_all_data(self, conn):
        add_item(conn, image_filename="a.jpg", name="Test", category="top")
        set_setting(conn, "custom", "value")
        clear_all_data(conn)

        items = get_all_items(conn, active_only=False)
        assert len(items) == 0
        assert get_setting(conn, "location_lat") == ""

    def test_clear_and_reinit(self, conn):
        clear_all_data(conn)
        init_db(conn)
        # Default settings should be back
        assert get_setting(conn, "location_lat") == "39.89"

    def test_clear_includes_battles(self, conn):
        save_battle(
            conn,
            outfit_a_ids=[1, 2],
            outfit_b_ids=[3, 4],
            outfit_a_name="A",
            outfit_b_name="B",
            winner="a",
            occasion="test",
        )
        clear_all_data(conn)
        assert len(get_battle_history(conn)) == 0


# --- Battles ---


class TestBattles:
    def test_save_battle(self, conn):
        battle_id = save_battle(
            conn,
            outfit_a_ids=[1, 2, 3],
            outfit_b_ids=[4, 5, 6],
            outfit_a_name="Outfit A",
            outfit_b_name="Outfit B",
            winner="a",
            occasion="everyday",
            weather_summary="70F, Clear",
        )
        assert battle_id is not None
        assert battle_id > 0

    def test_save_battle_winner_b(self, conn):
        battle_id = save_battle(
            conn,
            outfit_a_ids=[1],
            outfit_b_ids=[2],
            outfit_a_name="A",
            outfit_b_name="B",
            winner="b",
            occasion="work",
        )
        history = get_battle_history(conn, limit=1)
        assert history[0]["winner"] == "b"

    def test_get_battle_history(self, conn):
        for i in range(5):
            save_battle(
                conn,
                outfit_a_ids=[1],
                outfit_b_ids=[2],
                outfit_a_name=f"A{i}",
                outfit_b_name=f"B{i}",
                winner="a",
                occasion="test",
            )
        history = get_battle_history(conn, limit=3)
        assert len(history) == 3

    def test_get_battle_history_empty(self, conn):
        assert get_battle_history(conn) == []

    def test_battle_history_parses_json(self, conn):
        save_battle(
            conn,
            outfit_a_ids=[10, 20],
            outfit_b_ids=[30, 40],
            outfit_a_name="A",
            outfit_b_name="B",
            winner="a",
            occasion="test",
        )
        history = get_battle_history(conn, limit=1)
        assert history[0]["outfit_a_ids"] == [10, 20]
        assert history[0]["outfit_b_ids"] == [30, 40]

    def test_battle_item_stats(self, conn):
        # Battle 1: A wins (items 1,2 win; items 3,4 lose)
        save_battle(
            conn,
            outfit_a_ids=[1, 2],
            outfit_b_ids=[3, 4],
            outfit_a_name="A",
            outfit_b_name="B",
            winner="a",
            occasion="test",
        )
        # Battle 2: B wins (items 5,6 lose; items 1,3 win)
        save_battle(
            conn,
            outfit_a_ids=[5, 6],
            outfit_b_ids=[1, 3],
            outfit_a_name="C",
            outfit_b_name="D",
            winner="b",
            occasion="test",
        )
        stats = get_battle_item_stats(conn)
        assert stats["wins"][1] == 2  # item 1 won twice
        assert stats["wins"][2] == 1
        assert stats["wins"][3] == 1
        assert stats["losses"][3] == 1  # item 3 lost once
        assert stats["losses"][5] == 1
        assert stats["losses"][6] == 1

    def test_battle_item_stats_empty(self, conn):
        stats = get_battle_item_stats(conn)
        assert stats == {"wins": {}, "losses": {}}
