"""SQLite storage: the user's own Rubika account(s) + panel settings.

Deliberately minimal: just `accounts` and a single-row `settings`.
No proxy tables, no broadcast queues — this is a small personal tool.
"""
import os
import sqlite3
from datetime import datetime

import config

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "data.db")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    conn = _conn()
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            phone     TEXT UNIQUE,
            name      TEXT,
            user_id   TEXT,
            session   TEXT,
            added_at  TEXT,
            status    TEXT DEFAULT 'active'
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            id         INTEGER PRIMARY KEY CHECK (id = 1),
            send_delay REAL,
            marker     TEXT
        )
        """
    )
    c.execute(
        "INSERT OR IGNORE INTO settings (id, send_delay, marker) VALUES (1, ?, ?)",
        (config.DEFAULT_DELAY, config.FORWARD_MARKER),
    )

    # ---- Worker subsystem tables (additive; never touches the originals) ----
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS workers (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            tag          TEXT UNIQUE,
            ip           TEXT,
            ssh_port     INTEGER DEFAULT 22,
            ssh_user     TEXT,
            ssh_pass_enc TEXT,
            api_port     INTEGER,
            api_token_enc TEXT,
            is_master    INTEGER DEFAULT 0,
            enabled      INTEGER DEFAULT 1,
            status       TEXT DEFAULT 'unknown',
            ping_ms      INTEGER DEFAULT -1,
            file_ok      INTEGER DEFAULT 0,
            last_checked TEXT,
            created_at   TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS admins (
            user_id  INTEGER PRIMARY KEY,
            name     TEXT,
            added_at TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS worker_daily (
            worker_id INTEGER,
            day       TEXT,
            sent      INTEGER DEFAULT 0,
            PRIMARY KEY (worker_id, day)
        )
        """
    )

    # ---- Automation tables (rotating texts to an account's groups) ----
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS automation (
            account_id   INTEGER PRIMARY KEY,
            enabled      INTEGER DEFAULT 0,
            interval_sec INTEGER DEFAULT 30,
            sent_total   INTEGER DEFAULT 0,
            updated_at   TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS automation_texts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            text       TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS automation_links (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            link       TEXT
        )
        """
    )

    # ---- Automation EXTRAS tables (additive; secretary / channel report /
    #      reply responder / profile sync / verified group links) ----
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS secretary (
            account_id    INTEGER PRIMARY KEY,
            enabled       INTEGER DEFAULT 0,
            mode          TEXT DEFAULT 'marker',   -- 'marker' or 'text'
            text          TEXT DEFAULT '',
            interval_sec  INTEGER DEFAULT 600,
            state         TEXT DEFAULT '',          -- last get_chats_updates state
            replied_total INTEGER DEFAULT 0,
            updated_at    TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS secretary_replied (
            account_id INTEGER,
            user_guid  TEXT,
            replied_at TEXT,
            PRIMARY KEY (account_id, user_guid)
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS channel_report (
            account_id    INTEGER PRIMARY KEY,
            enabled       INTEGER DEFAULT 0,
            channel_guid  TEXT DEFAULT '',
            channel_title TEXT DEFAULT '',
            interval_sec  INTEGER DEFAULT 600,
            updated_at    TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS reply_responder (
            account_id    INTEGER PRIMARY KEY,
            enabled       INTEGER DEFAULT 0,
            text          TEXT DEFAULT '',
            delay_sec     REAL DEFAULT 2.0,
            replied_total INTEGER DEFAULT 0,
            updated_at    TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS reply_done (
            account_id INTEGER,
            message_id TEXT,
            done_at    TEXT,
            PRIMARY KEY (account_id, message_id)
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS profile_sync (
            id         INTEGER PRIMARY KEY CHECK (id = 1),
            first_name TEXT DEFAULT '',
            last_name  TEXT DEFAULT '',
            bio        TEXT DEFAULT '',
            updated_at TEXT
        )
        """
    )
    c.execute("INSERT OR IGNORE INTO profile_sync (id, first_name, last_name, bio) "
              "VALUES (1, '', '', '')")
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS verified_group_links (
            link     TEXT PRIMARY KEY,
            added_by TEXT,
            added_at TEXT
        )
        """
    )

    # ----------------------------------------------------------------------- #
    # YoudonoaAx UPDATE tables (additive only).
    #   Item 2: leeched_numbers (anti-repeat ledger for the discovery engine)
    #   Item 3: linkdooni_* (channels / fleet / discovered groups / seen links)
    # ----------------------------------------------------------------------- #
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS leeched_numbers (
            phone      TEXT PRIMARY KEY,
            on_rubika  INTEGER DEFAULT 0,
            checked_at TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS linkdooni_config (
            id            INTEGER PRIMARY KEY CHECK (id = 1),
            enabled       INTEGER DEFAULT 0,
            send_interval INTEGER DEFAULT 1800,
            daily_groups  INTEGER DEFAULT 30,
            updated_at    TEXT
        )
        """
    )
    c.execute("INSERT OR IGNORE INTO linkdooni_config "
              "(id, enabled, send_interval, daily_groups) VALUES (1, 0, ?, ?)",
              (config.LINKDOONI_SEND_INTERVAL, config.LINKDOONI_DAILY_GROUPS))
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS linkdooni_channels (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            ref      TEXT UNIQUE,
            added_at TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS linkdooni_accounts (
            account_id   INTEGER PRIMARY KEY,
            sent_total   INTEGER DEFAULT 0,
            joined_total INTEGER DEFAULT 0,
            updated_at   TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS linkdooni_groups (
            group_guid    TEXT PRIMARY KEY,
            link          TEXT,
            name          TEXT DEFAULT '',
            account_id    INTEGER,
            joined        INTEGER DEFAULT 0,
            discovered_at TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS linkdooni_seen_links (
            link    TEXT PRIMARY KEY,
            seen_at TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS linkdooni_texts (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT
        )
        """
    )

    # ---- migration: add accounts.worker_id (account -> worker affinity) ----
    cols = [r["name"] for r in c.execute("PRAGMA table_info(accounts)").fetchall()]
    if "worker_id" not in cols:
        c.execute("ALTER TABLE accounts ADD COLUMN worker_id INTEGER")

    conn.commit()
    conn.close()


# ---------- accounts ----------

def add_account(phone: str, name: str, user_id: str, session: str) -> int:
    conn = _conn()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO accounts (phone, name, user_id, session, added_at, status)
        VALUES (?, ?, ?, ?, ?, 'active')
        ON CONFLICT(phone) DO UPDATE SET
            name=excluded.name,
            user_id=excluded.user_id,
            session=excluded.session,
            status='active'
        """,
        (phone, name, user_id, session, _now()),
    )
    conn.commit()
    row = c.execute("SELECT id FROM accounts WHERE phone = ?", (phone,)).fetchone()
    conn.close()
    return row["id"]


def list_accounts() -> list:
    conn = _conn()
    rows = conn.execute("SELECT * FROM accounts ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_account(account_id: int):
    conn = _conn()
    row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_account(account_id: int):
    conn = _conn()
    conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
    conn.execute("DELETE FROM automation WHERE account_id = ?", (account_id,))
    conn.execute("DELETE FROM automation_texts WHERE account_id = ?", (account_id,))
    conn.execute("DELETE FROM automation_links WHERE account_id = ?", (account_id,))
    # automation EXTRAS cleanup (best-effort; tables always exist after init())
    for tbl in ("secretary", "secretary_replied", "channel_report",
                "reply_responder", "reply_done"):
        try:
            conn.execute(f"DELETE FROM {tbl} WHERE account_id = ?", (account_id,))
        except Exception:
            pass
    conn.commit()
    conn.close()


def set_status(account_id: int, status: str):
    conn = _conn()
    conn.execute("UPDATE accounts SET status = ? WHERE id = ?", (status, account_id))
    conn.commit()
    conn.close()


# ---------- settings ----------

def get_settings() -> dict:
    conn = _conn()
    row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    conn.close()
    if not row:
        return {"send_delay": config.DEFAULT_DELAY, "marker": config.FORWARD_MARKER}
    return dict(row)


def get_delay() -> float:
    return config.clamp_delay(get_settings().get("send_delay"))


def set_delay(value: float):
    conn = _conn()
    conn.execute("UPDATE settings SET send_delay = ? WHERE id = 1",
                 (config.clamp_delay(value),))
    conn.commit()
    conn.close()


def get_marker() -> str:
    return (get_settings().get("marker") or config.FORWARD_MARKER).strip()


def set_marker(marker: str):
    conn = _conn()
    conn.execute("UPDATE settings SET marker = ? WHERE id = 1", (marker.strip(),))
    conn.commit()
    conn.close()



# --------------------------------------------------------------------------- #
# Admins (extra Telegram ids allowed to use the panel, added by the owner).
# OWNER_ID is always allowed and is NOT stored here.
# --------------------------------------------------------------------------- #
def add_admin(user_id: int, name: str = ""):
    conn = _conn()
    conn.execute(
        "INSERT OR REPLACE INTO admins (user_id, name, added_at) VALUES (?, ?, ?)",
        (int(user_id), name or "", _now()),
    )
    conn.commit()
    conn.close()


def remove_admin(user_id: int):
    conn = _conn()
    conn.execute("DELETE FROM admins WHERE user_id = ?", (int(user_id),))
    conn.commit()
    conn.close()


def list_admins() -> list:
    conn = _conn()
    rows = conn.execute("SELECT * FROM admins ORDER BY added_at").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_admin_ids() -> list:
    return [int(a["user_id"]) for a in list_admins()]


# --------------------------------------------------------------------------- #
# Workers
# --------------------------------------------------------------------------- #
def add_worker(tag: str, ip: str, ssh_port: int, ssh_user: str,
               ssh_pass_enc: str, api_port: int, api_token_enc: str,
               is_master: int = 0) -> int:
    conn = _conn()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO workers (tag, ip, ssh_port, ssh_user, ssh_pass_enc,
                             api_port, api_token_enc, is_master, enabled,
                             status, ping_ms, file_ok, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 'unknown', -1, 0, ?)
        """,
        (tag, ip, int(ssh_port or 22), ssh_user, ssh_pass_enc,
         int(api_port), api_token_enc, int(is_master), _now()),
    )
    conn.commit()
    wid = c.lastrowid
    conn.close()
    return wid


def list_workers() -> list:
    conn = _conn()
    rows = conn.execute("SELECT * FROM workers ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_enabled_workers() -> list:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM workers WHERE enabled = 1 ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_worker(worker_id: int):
    conn = _conn()
    row = conn.execute("SELECT * FROM workers WHERE id = ?", (int(worker_id),)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_worker_by_tag(tag: str):
    conn = _conn()
    row = conn.execute("SELECT * FROM workers WHERE tag = ?", (tag,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_master_worker():
    conn = _conn()
    row = conn.execute("SELECT * FROM workers WHERE is_master = 1 LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def delete_worker(worker_id: int):
    conn = _conn()
    conn.execute("DELETE FROM workers WHERE id = ?", (int(worker_id),))
    conn.execute("DELETE FROM worker_daily WHERE worker_id = ?", (int(worker_id),))
    # detach accounts that were bound to this worker
    conn.execute("UPDATE accounts SET worker_id = NULL WHERE worker_id = ?",
                 (int(worker_id),))
    conn.commit()
    conn.close()


def set_worker_enabled(worker_id: int, enabled: bool):
    conn = _conn()
    conn.execute("UPDATE workers SET enabled = ? WHERE id = ?",
                 (1 if enabled else 0, int(worker_id)))
    conn.commit()
    conn.close()


def update_worker_health(worker_id: int, status: str, ping_ms: int, file_ok: bool):
    conn = _conn()
    conn.execute(
        "UPDATE workers SET status = ?, ping_ms = ?, file_ok = ?, last_checked = ? "
        "WHERE id = ?",
        (status, int(ping_ms), 1 if file_ok else 0, _now(), int(worker_id)),
    )
    conn.commit()
    conn.close()


def count_accounts_on_worker(worker_id: int) -> int:
    conn = _conn()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM accounts WHERE worker_id = ?", (int(worker_id),)
    ).fetchone()
    conn.close()
    return int(row["n"]) if row else 0


def set_account_worker(account_id: int, worker_id):
    conn = _conn()
    conn.execute("UPDATE accounts SET worker_id = ? WHERE id = ?",
                 (worker_id, int(account_id)))
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------- #
# Per-worker daily send counter (no cap; informational + routing hint).
# --------------------------------------------------------------------------- #
def _today() -> str:
    return config.now_dt().strftime("%Y-%m-%d")


def incr_worker_sent(worker_id: int, n: int = 1):
    conn = _conn()
    day = _today()
    conn.execute(
        "INSERT INTO worker_daily (worker_id, day, sent) VALUES (?, ?, ?) "
        "ON CONFLICT(worker_id, day) DO UPDATE SET sent = sent + ?",
        (int(worker_id), day, int(n), int(n)),
    )
    conn.commit()
    conn.close()


def worker_sent_today(worker_id: int) -> int:
    conn = _conn()
    row = conn.execute(
        "SELECT sent FROM worker_daily WHERE worker_id = ? AND day = ?",
        (int(worker_id), _today()),
    ).fetchone()
    conn.close()
    return int(row["sent"]) if row else 0


# --------------------------------------------------------------------------- #
# Automation (rotating texts to an account's groups). One row per account.
# --------------------------------------------------------------------------- #
def _ensure_automation_row(c, account_id: int):
    c.execute(
        "INSERT OR IGNORE INTO automation (account_id, enabled, interval_sec, "
        "sent_total, updated_at) VALUES (?, 0, 30, 0, ?)",
        (int(account_id), _now()),
    )


def get_automation(account_id: int) -> dict:
    conn = _conn()
    c = conn.cursor()
    _ensure_automation_row(c, account_id)
    conn.commit()
    row = c.execute("SELECT * FROM automation WHERE account_id = ?",
                    (int(account_id),)).fetchone()
    conn.close()
    return dict(row) if row else {"account_id": account_id, "enabled": 0,
                                  "interval_sec": 30, "sent_total": 0}


def set_automation_enabled(account_id: int, enabled: bool):
    conn = _conn()
    c = conn.cursor()
    _ensure_automation_row(c, account_id)
    c.execute("UPDATE automation SET enabled = ?, updated_at = ? WHERE account_id = ?",
              (1 if enabled else 0, _now(), int(account_id)))
    conn.commit()
    conn.close()


def set_automation_interval(account_id: int, interval_sec: int):
    conn = _conn()
    c = conn.cursor()
    _ensure_automation_row(c, account_id)
    c.execute("UPDATE automation SET interval_sec = ?, updated_at = ? WHERE account_id = ?",
              (config.clamp_interval(interval_sec), _now(), int(account_id)))
    conn.commit()
    conn.close()


def incr_automation_sent(account_id: int, n: int = 1):
    conn = _conn()
    c = conn.cursor()
    _ensure_automation_row(c, account_id)
    c.execute("UPDATE automation SET sent_total = sent_total + ? WHERE account_id = ?",
              (int(n), int(account_id)))
    conn.commit()
    conn.close()


def list_enabled_automations() -> list:
    conn = _conn()
    rows = conn.execute("SELECT * FROM automation WHERE enabled = 1").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_automation_text(account_id: int, text: str):
    conn = _conn()
    conn.execute("INSERT INTO automation_texts (account_id, text) VALUES (?, ?)",
                 (int(account_id), text))
    conn.commit()
    conn.close()


def list_automation_texts(account_id: int) -> list:
    conn = _conn()
    rows = conn.execute(
        "SELECT text FROM automation_texts WHERE account_id = ? ORDER BY id",
        (int(account_id),)).fetchall()
    conn.close()
    return [r["text"] for r in rows]


def clear_automation_texts(account_id: int):
    conn = _conn()
    conn.execute("DELETE FROM automation_texts WHERE account_id = ?", (int(account_id),))
    conn.commit()
    conn.close()


def add_automation_link(account_id: int, link: str):
    conn = _conn()
    conn.execute("INSERT INTO automation_links (account_id, link) VALUES (?, ?)",
                 (int(account_id), link))
    conn.commit()
    conn.close()


def list_automation_links(account_id: int) -> list:
    conn = _conn()
    rows = conn.execute(
        "SELECT link FROM automation_links WHERE account_id = ? ORDER BY id",
        (int(account_id),)).fetchall()
    conn.close()
    return [r["link"] for r in rows]


def clear_automation_links(account_id: int):
    conn = _conn()
    conn.execute("DELETE FROM automation_links WHERE account_id = ?", (int(account_id),))
    conn.commit()
    conn.close()



# --------------------------------------------------------------------------- #
# Automation EXTRAS accessors (additive). One row per account where noted.
# --------------------------------------------------------------------------- #

# ---------- Feature 1: PV secretary ----------
def _ensure_secretary_row(c, account_id: int):
    c.execute(
        "INSERT OR IGNORE INTO secretary (account_id, enabled, mode, text, "
        "interval_sec, state, replied_total, updated_at) "
        "VALUES (?, 0, 'marker', '', ?, '', 0, ?)",
        (int(account_id), config.SECRETARY_INTERVAL, _now()),
    )


def get_secretary(account_id: int) -> dict:
    conn = _conn()
    c = conn.cursor()
    _ensure_secretary_row(c, account_id)
    conn.commit()
    row = c.execute("SELECT * FROM secretary WHERE account_id = ?",
                    (int(account_id),)).fetchone()
    conn.close()
    return dict(row) if row else {"account_id": account_id, "enabled": 0,
                                  "mode": "marker", "text": "",
                                  "interval_sec": config.SECRETARY_INTERVAL,
                                  "state": "", "replied_total": 0}


def set_secretary_enabled(account_id: int, enabled: bool):
    conn = _conn()
    c = conn.cursor()
    _ensure_secretary_row(c, account_id)
    c.execute("UPDATE secretary SET enabled = ?, updated_at = ? WHERE account_id = ?",
              (1 if enabled else 0, _now(), int(account_id)))
    conn.commit()
    conn.close()


def set_secretary_mode(account_id: int, mode: str):
    mode = "text" if str(mode).lower() == "text" else "marker"
    conn = _conn()
    c = conn.cursor()
    _ensure_secretary_row(c, account_id)
    c.execute("UPDATE secretary SET mode = ?, updated_at = ? WHERE account_id = ?",
              (mode, _now(), int(account_id)))
    conn.commit()
    conn.close()


def set_secretary_text(account_id: int, text: str):
    conn = _conn()
    c = conn.cursor()
    _ensure_secretary_row(c, account_id)
    c.execute("UPDATE secretary SET text = ?, updated_at = ? WHERE account_id = ?",
              (text or "", _now(), int(account_id)))
    conn.commit()
    conn.close()


def set_secretary_interval(account_id: int, interval_sec):
    conn = _conn()
    c = conn.cursor()
    _ensure_secretary_row(c, account_id)
    c.execute("UPDATE secretary SET interval_sec = ?, updated_at = ? WHERE account_id = ?",
              (config.clamp_secretary_interval(interval_sec), _now(), int(account_id)))
    conn.commit()
    conn.close()


def set_secretary_state(account_id: int, state: str):
    conn = _conn()
    c = conn.cursor()
    _ensure_secretary_row(c, account_id)
    c.execute("UPDATE secretary SET state = ? WHERE account_id = ?",
              (str(state or ""), int(account_id)))
    conn.commit()
    conn.close()


def incr_secretary_replied(account_id: int, n: int = 1):
    conn = _conn()
    c = conn.cursor()
    _ensure_secretary_row(c, account_id)
    c.execute("UPDATE secretary SET replied_total = replied_total + ? WHERE account_id = ?",
              (int(n), int(account_id)))
    conn.commit()
    conn.close()


def list_enabled_secretaries() -> list:
    conn = _conn()
    rows = conn.execute("SELECT * FROM secretary WHERE enabled = 1").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def secretary_already_replied(account_id: int, user_guid: str) -> bool:
    conn = _conn()
    row = conn.execute(
        "SELECT 1 FROM secretary_replied WHERE account_id = ? AND user_guid = ?",
        (int(account_id), str(user_guid))).fetchone()
    conn.close()
    return bool(row)


def mark_secretary_replied(account_id: int, user_guid: str):
    conn = _conn()
    conn.execute(
        "INSERT OR IGNORE INTO secretary_replied (account_id, user_guid, replied_at) "
        "VALUES (?, ?, ?)", (int(account_id), str(user_guid), _now()))
    conn.commit()
    conn.close()


def clear_secretary_replied(account_id: int):
    conn = _conn()
    conn.execute("DELETE FROM secretary_replied WHERE account_id = ?", (int(account_id),))
    conn.commit()
    conn.close()


# ---------- Feature 2: channel report ----------
def _ensure_channel_report_row(c, account_id: int):
    c.execute(
        "INSERT OR IGNORE INTO channel_report (account_id, enabled, channel_guid, "
        "channel_title, interval_sec, updated_at) VALUES (?, 0, '', '', ?, ?)",
        (int(account_id), config.CHANNEL_REPORT_INTERVAL, _now()),
    )


def get_channel_report(account_id: int) -> dict:
    conn = _conn()
    c = conn.cursor()
    _ensure_channel_report_row(c, account_id)
    conn.commit()
    row = c.execute("SELECT * FROM channel_report WHERE account_id = ?",
                    (int(account_id),)).fetchone()
    conn.close()
    return dict(row) if row else {"account_id": account_id, "enabled": 0,
                                  "channel_guid": "", "channel_title": "",
                                  "interval_sec": config.CHANNEL_REPORT_INTERVAL}


def set_channel_report_enabled(account_id: int, enabled: bool):
    conn = _conn()
    c = conn.cursor()
    _ensure_channel_report_row(c, account_id)
    c.execute("UPDATE channel_report SET enabled = ?, updated_at = ? WHERE account_id = ?",
              (1 if enabled else 0, _now(), int(account_id)))
    conn.commit()
    conn.close()


def set_channel_report_target(account_id: int, channel_guid: str, channel_title: str = ""):
    conn = _conn()
    c = conn.cursor()
    _ensure_channel_report_row(c, account_id)
    c.execute("UPDATE channel_report SET channel_guid = ?, channel_title = ?, "
              "updated_at = ? WHERE account_id = ?",
              (str(channel_guid or ""), str(channel_title or ""), _now(), int(account_id)))
    conn.commit()
    conn.close()


def set_channel_report_interval(account_id: int, interval_sec):
    conn = _conn()
    c = conn.cursor()
    _ensure_channel_report_row(c, account_id)
    c.execute("UPDATE channel_report SET interval_sec = ?, updated_at = ? WHERE account_id = ?",
              (config.clamp_channel_report_interval(interval_sec), _now(), int(account_id)))
    conn.commit()
    conn.close()


def list_enabled_channel_reports() -> list:
    conn = _conn()
    rows = conn.execute("SELECT * FROM channel_report WHERE enabled = 1").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- Feature 3: profile sync (global, single row) ----------
def get_profile_sync() -> dict:
    conn = _conn()
    row = conn.execute("SELECT * FROM profile_sync WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else {"first_name": "", "last_name": "", "bio": ""}


def set_profile_sync(first_name: str, last_name: str, bio: str):
    conn = _conn()
    conn.execute(
        "INSERT INTO profile_sync (id, first_name, last_name, bio, updated_at) "
        "VALUES (1, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET first_name=excluded.first_name, "
        "last_name=excluded.last_name, bio=excluded.bio, updated_at=excluded.updated_at",
        (first_name or "", last_name or "", bio or "", _now()),
    )
    conn.commit()
    conn.close()


# ---------- Feature 5: reply responder ----------
def _ensure_reply_row(c, account_id: int):
    c.execute(
        "INSERT OR IGNORE INTO reply_responder (account_id, enabled, text, "
        "delay_sec, replied_total, updated_at) VALUES (?, 0, '', ?, 0, ?)",
        (int(account_id), config.REPLY_DELAY, _now()),
    )


def get_reply_responder(account_id: int) -> dict:
    conn = _conn()
    c = conn.cursor()
    _ensure_reply_row(c, account_id)
    conn.commit()
    row = c.execute("SELECT * FROM reply_responder WHERE account_id = ?",
                    (int(account_id),)).fetchone()
    conn.close()
    return dict(row) if row else {"account_id": account_id, "enabled": 0,
                                  "text": "", "delay_sec": config.REPLY_DELAY,
                                  "replied_total": 0}


def set_reply_enabled(account_id: int, enabled: bool):
    conn = _conn()
    c = conn.cursor()
    _ensure_reply_row(c, account_id)
    c.execute("UPDATE reply_responder SET enabled = ?, updated_at = ? WHERE account_id = ?",
              (1 if enabled else 0, _now(), int(account_id)))
    conn.commit()
    conn.close()


def set_reply_text(account_id: int, text: str):
    conn = _conn()
    c = conn.cursor()
    _ensure_reply_row(c, account_id)
    c.execute("UPDATE reply_responder SET text = ?, updated_at = ? WHERE account_id = ?",
              (text or "", _now(), int(account_id)))
    conn.commit()
    conn.close()


def set_reply_delay(account_id: int, delay_sec):
    conn = _conn()
    c = conn.cursor()
    _ensure_reply_row(c, account_id)
    c.execute("UPDATE reply_responder SET delay_sec = ?, updated_at = ? WHERE account_id = ?",
              (config.clamp_reply_delay(delay_sec), _now(), int(account_id)))
    conn.commit()
    conn.close()


def incr_reply_replied(account_id: int, n: int = 1):
    conn = _conn()
    c = conn.cursor()
    _ensure_reply_row(c, account_id)
    c.execute("UPDATE reply_responder SET replied_total = replied_total + ? WHERE account_id = ?",
              (int(n), int(account_id)))
    conn.commit()
    conn.close()


def list_enabled_reply_responders() -> list:
    conn = _conn()
    rows = conn.execute("SELECT * FROM reply_responder WHERE enabled = 1").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def reply_already_done(account_id: int, message_id: str) -> bool:
    conn = _conn()
    row = conn.execute(
        "SELECT 1 FROM reply_done WHERE account_id = ? AND message_id = ?",
        (int(account_id), str(message_id))).fetchone()
    conn.close()
    return bool(row)


def mark_reply_done(account_id: int, message_id: str):
    conn = _conn()
    conn.execute(
        "INSERT OR IGNORE INTO reply_done (account_id, message_id, done_at) "
        "VALUES (?, ?, ?)", (int(account_id), str(message_id), _now()))
    conn.commit()
    conn.close()


# ---------- Feature 4: verified (successfully joined) group links, shared ----
def add_verified_group_link(link: str, added_by: str = ""):
    conn = _conn()
    conn.execute(
        "INSERT OR IGNORE INTO verified_group_links (link, added_by, added_at) "
        "VALUES (?, ?, ?)", (str(link), str(added_by or ""), _now()))
    conn.commit()
    conn.close()


def list_verified_group_links() -> list:
    conn = _conn()
    rows = conn.execute(
        "SELECT link FROM verified_group_links ORDER BY added_at").fetchall()
    conn.close()
    return [r["link"] for r in rows]


def clear_verified_group_links():
    conn = _conn()
    conn.execute("DELETE FROM verified_group_links")
    conn.commit()
    conn.close()


def count_verified_group_links() -> int:
    conn = _conn()
    row = conn.execute("SELECT COUNT(*) AS n FROM verified_group_links").fetchone()
    conn.close()
    return int(row["n"]) if row else 0



# --------------------------------------------------------------------------- #
# Cleanup engine (موتور پاکسازی): groups where an account got banned/muted
# (couldn't send after repeated tries) are recorded here as "candidates". The
# owner reviews them in a confirm/cancel panel and decides to leave or keep.
# --------------------------------------------------------------------------- #
def _ensure_cleanup_table():
    conn = _conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cleanup_candidates (
            account_id  INTEGER,
            group_guid  TEXT,
            group_name  TEXT,
            reason      TEXT,
            detected_at TEXT,
            PRIMARY KEY (account_id, group_guid)
        )
        """
    )
    conn.commit()
    conn.close()


def add_cleanup_candidate(account_id: int, group_guid: str, group_name: str = "",
                          reason: str = "banned/muted"):
    """Record a group the account can no longer post to (idempotent). Returns
    True if it was NEW (so the caller logs it only once)."""
    _ensure_cleanup_table()
    conn = _conn()
    existing = conn.execute(
        "SELECT 1 FROM cleanup_candidates WHERE account_id = ? AND group_guid = ?",
        (int(account_id), str(group_guid))).fetchone()
    conn.execute(
        "INSERT OR IGNORE INTO cleanup_candidates (account_id, group_guid, "
        "group_name, reason, detected_at) VALUES (?, ?, ?, ?, ?)",
        (int(account_id), str(group_guid), group_name or "", reason or "", _now()))
    conn.commit()
    conn.close()
    return existing is None


def list_cleanup_candidates(account_id: int) -> list:
    _ensure_cleanup_table()
    conn = _conn()
    rows = conn.execute(
        "SELECT group_guid, group_name, reason, detected_at FROM cleanup_candidates "
        "WHERE account_id = ? ORDER BY detected_at", (int(account_id),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_cleanup_candidates(account_id: int) -> int:
    _ensure_cleanup_table()
    conn = _conn()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM cleanup_candidates WHERE account_id = ?",
        (int(account_id),)).fetchone()
    conn.close()
    return int(row["n"]) if row else 0


def remove_cleanup_candidate(account_id: int, group_guid: str):
    _ensure_cleanup_table()
    conn = _conn()
    conn.execute(
        "DELETE FROM cleanup_candidates WHERE account_id = ? AND group_guid = ?",
        (int(account_id), str(group_guid)))
    conn.commit()
    conn.close()


def clear_cleanup_candidates(account_id: int):
    _ensure_cleanup_table()
    conn = _conn()
    conn.execute("DELETE FROM cleanup_candidates WHERE account_id = ?",
                 (int(account_id),))
    conn.commit()
    conn.close()



# --------------------------------------------------------------------------- #
# Generator engine (موتور مولد): single-row config + last result.
# Builds a channel/group with one account, joins the others, waits for the
# owner to make them admins, then seeds members. All additive.
# --------------------------------------------------------------------------- #
def _ensure_generator_table():
    conn = _conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS generator (
            id            INTEGER PRIMARY KEY CHECK (id = 1),
            kind          TEXT DEFAULT 'channel',   -- 'channel' or 'group'
            title         TEXT DEFAULT '',
            creator_id    INTEGER,                  -- account_id of the creator
            member_target INTEGER DEFAULT 300,      -- per-account member cap
            admin_wait    INTEGER DEFAULT 600,      -- seconds to wait for admin
            updated_at    TEXT
        )
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO generator (id, kind, title, member_target, admin_wait) "
        "VALUES (1, 'channel', '', ?, ?)",
        (config.CHANNEL_MEMBER_TARGET, 600),
    )
    conn.commit()
    conn.close()


def get_generator() -> dict:
    _ensure_generator_table()
    conn = _conn()
    row = conn.execute("SELECT * FROM generator WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else {"kind": "channel", "title": "", "creator_id": None,
                                  "member_target": config.CHANNEL_MEMBER_TARGET,
                                  "admin_wait": 600}


def set_generator(**fields):
    """Update any subset of generator config fields."""
    if not fields:
        return
    _ensure_generator_table()
    allowed = {"kind", "title", "creator_id", "member_target", "admin_wait"}
    sets = []
    vals = []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return
    sets.append("updated_at = ?")
    vals.append(_now())
    conn = _conn()
    conn.execute(f"UPDATE generator SET {', '.join(sets)} WHERE id = 1", vals)
    conn.commit()
    conn.close()



# --------------------------------------------------------------------------- #
# Channel-broadcast engine (پخش کانالی / موتور مولد جدید): selected accounts
# EACH create their OWN channel (shared title), forward the marked post into
# it, then seed their OWN contacts. Config is a single row + a set of selected
# account ids. (Rubika doesn't let channel admins add members, so the old
# shared-channel/admin model is replaced by this per-account model.)
# --------------------------------------------------------------------------- #
def _ensure_broadcaster_tables():
    conn = _conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS broadcaster (
            id            INTEGER PRIMARY KEY CHECK (id = 1),
            title         TEXT DEFAULT '',
            username_seed TEXT DEFAULT 'ch',
            member_target INTEGER DEFAULT 300,
            gap_seconds   INTEGER DEFAULT 8,
            updated_at    TEXT
        )
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO broadcaster (id, title, username_seed, member_target, "
        "gap_seconds) VALUES (1, '', 'ch', ?, 8)",
        (config.CHANNEL_MEMBER_TARGET,),
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS broadcaster_accounts (
            account_id INTEGER PRIMARY KEY
        )
        """
    )
    conn.commit()
    conn.close()


def get_broadcaster() -> dict:
    _ensure_broadcaster_tables()
    conn = _conn()
    row = conn.execute("SELECT * FROM broadcaster WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else {"title": "", "username_seed": "ch",
                                  "member_target": config.CHANNEL_MEMBER_TARGET,
                                  "gap_seconds": 8}


def set_broadcaster(**fields):
    if not fields:
        return
    _ensure_broadcaster_tables()
    allowed = {"title", "username_seed", "member_target", "gap_seconds"}
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return
    sets.append("updated_at = ?")
    vals.append(_now())
    conn = _conn()
    conn.execute(f"UPDATE broadcaster SET {', '.join(sets)} WHERE id = 1", vals)
    conn.commit()
    conn.close()


def toggle_broadcaster_account(account_id: int) -> bool:
    """Add/remove an account from the broadcast selection. Returns new state
    (True = now selected)."""
    _ensure_broadcaster_tables()
    conn = _conn()
    row = conn.execute("SELECT 1 FROM broadcaster_accounts WHERE account_id = ?",
                       (int(account_id),)).fetchone()
    if row:
        conn.execute("DELETE FROM broadcaster_accounts WHERE account_id = ?",
                     (int(account_id),))
        new_state = False
    else:
        conn.execute("INSERT OR IGNORE INTO broadcaster_accounts (account_id) VALUES (?)",
                     (int(account_id),))
        new_state = True
    conn.commit()
    conn.close()
    return new_state


def list_broadcaster_account_ids() -> list:
    _ensure_broadcaster_tables()
    conn = _conn()
    rows = conn.execute("SELECT account_id FROM broadcaster_accounts").fetchall()
    conn.close()
    return [int(r["account_id"]) for r in rows]


def is_broadcaster_account(account_id: int) -> bool:
    return int(account_id) in set(list_broadcaster_account_ids())



# =========================================================================== #
# update_end ADDITIONS — generic app settings (panel-editable) + paused-send
# persistence (so a send can resume after a restart). Lazy-created tables, the
# same pattern as cleanup_candidates above; init() is left untouched.
# =========================================================================== #
import json as _json


def _ensure_app_settings():
    conn = _conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def get_setting(key: str, default=None):
    _ensure_app_settings()
    conn = _conn()
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (str(key),)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value):
    _ensure_app_settings()
    conn = _conn()
    conn.execute(
        "INSERT INTO app_settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(key), str(value)),
    )
    conn.commit()
    conn.close()


def get_int_setting(key: str, default: int) -> int:
    v = get_setting(key, None)
    try:
        return int(v)
    except (TypeError, ValueError):
        return int(default)


def get_float_setting(key: str, default: float) -> float:
    v = get_setting(key, None)
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


# ---- panel-editable runtime settings (with config defaults) ----
def get_max_errors() -> int:
    return max(1, get_int_setting("max_errors", config.MAX_ERRORS))


def set_max_errors(value):
    try:
        value = max(1, int(float(value)))
    except (TypeError, ValueError):
        value = config.MAX_ERRORS
    set_setting("max_errors", value)


def get_resume_wait() -> int:
    return max(5, get_int_setting("resume_wait", config.RESUME_WAIT))


def set_resume_wait(value):
    try:
        value = max(5, int(float(value)))
    except (TypeError, ValueError):
        value = config.RESUME_WAIT
    set_setting("resume_wait", value)


def get_contact_delay() -> float:
    return config.clamp_contact_delay(get_float_setting("contact_delay", config.CONTACT_ADD_DELAY))


def set_contact_delay(value):
    set_setting("contact_delay", config.clamp_contact_delay(value))


# --------------------------------------------------------------------------- #
# Paused sends — remember exactly where a send stopped so it can resume the
# SAME remaining list later (after re-login / worker transfer), and survive a
# restart. One row per account.
# --------------------------------------------------------------------------- #
def _ensure_paused_sends():
    conn = _conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS paused_sends (
            account_id INTEGER PRIMARY KEY,
            owner_id   INTEGER,
            phone      TEXT,
            payload    TEXT,
            created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def save_paused_send(account_id: int, owner_id: int, phone: str, payload: dict):
    _ensure_paused_sends()
    conn = _conn()
    conn.execute(
        "INSERT INTO paused_sends (account_id, owner_id, phone, payload, created_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(account_id) DO UPDATE SET owner_id=excluded.owner_id, "
        "phone=excluded.phone, payload=excluded.payload, created_at=excluded.created_at",
        (int(account_id), int(owner_id), str(phone), _json.dumps(payload), _now()),
    )
    conn.commit()
    conn.close()


def get_paused_send(account_id: int):
    _ensure_paused_sends()
    conn = _conn()
    row = conn.execute("SELECT * FROM paused_sends WHERE account_id = ?",
                       (int(account_id),)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d["payload"] = _json.loads(d.get("payload") or "{}")
    except Exception:
        d["payload"] = {}
    return d


def list_paused_sends() -> list:
    _ensure_paused_sends()
    conn = _conn()
    rows = conn.execute("SELECT * FROM paused_sends ORDER BY created_at").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["payload"] = _json.loads(d.get("payload") or "{}")
        except Exception:
            d["payload"] = {}
        out.append(d)
    return out


def delete_paused_send(account_id: int):
    _ensure_paused_sends()
    conn = _conn()
    conn.execute("DELETE FROM paused_sends WHERE account_id = ?", (int(account_id),))
    conn.commit()
    conn.close()



# --------------------------------------------------------------------------- #
# YoudonoaAx UPDATE helpers (additive only).
# --------------------------------------------------------------------------- #
# ---- Item 2: leeched-number ledger (anti-repeat for the discovery engine) ----
def was_leeched(phone: str) -> bool:
    conn = _conn()
    row = conn.execute("SELECT 1 FROM leeched_numbers WHERE phone = ?",
                       (phone,)).fetchone()
    conn.close()
    return bool(row)


def mark_leeched(phone: str, on_rubika: bool):
    conn = _conn()
    conn.execute(
        "INSERT INTO leeched_numbers (phone, on_rubika, checked_at) VALUES (?, ?, ?) "
        "ON CONFLICT(phone) DO UPDATE SET on_rubika=excluded.on_rubika, "
        "checked_at=excluded.checked_at",
        (phone, 1 if on_rubika else 0, _now()))
    conn.commit()
    conn.close()


def leeched_count() -> int:
    conn = _conn()
    row = conn.execute("SELECT COUNT(*) AS n FROM leeched_numbers").fetchone()
    conn.close()
    return int(row["n"]) if row else 0


# ---- Item 3: linkdooni engine ----
def get_linkdooni_config() -> dict:
    conn = _conn()
    row = conn.execute("SELECT * FROM linkdooni_config WHERE id = 1").fetchone()
    conn.close()
    if not row:
        return {"enabled": 0, "send_interval": config.LINKDOONI_SEND_INTERVAL,
                "daily_groups": config.LINKDOONI_DAILY_GROUPS}
    return dict(row)


def set_linkdooni_enabled(enabled: bool):
    conn = _conn()
    conn.execute("UPDATE linkdooni_config SET enabled = ?, updated_at = ? WHERE id = 1",
                 (1 if enabled else 0, _now()))
    conn.commit()
    conn.close()


def set_linkdooni_interval(value):
    conn = _conn()
    conn.execute("UPDATE linkdooni_config SET send_interval = ?, updated_at = ? "
                 "WHERE id = 1", (config.clamp_linkdooni_interval(value), _now()))
    conn.commit()
    conn.close()


def set_linkdooni_daily_groups(value):
    try:
        value = max(1, int(float(value)))
    except (TypeError, ValueError):
        value = config.LINKDOONI_DAILY_GROUPS
    conn = _conn()
    conn.execute("UPDATE linkdooni_config SET daily_groups = ?, updated_at = ? "
                 "WHERE id = 1", (value, _now()))
    conn.commit()
    conn.close()


def add_linkdooni_channel(ref: str) -> bool:
    ref = (ref or "").strip()
    if not ref:
        return False
    conn = _conn()
    try:
        conn.execute("INSERT OR IGNORE INTO linkdooni_channels (ref, added_at) "
                     "VALUES (?, ?)", (ref, _now()))
        conn.commit()
        changed = conn.total_changes > 0
    finally:
        conn.close()
    return changed


def list_linkdooni_channels() -> list:
    conn = _conn()
    rows = conn.execute("SELECT * FROM linkdooni_channels ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clear_linkdooni_channels():
    conn = _conn()
    conn.execute("DELETE FROM linkdooni_channels")
    conn.commit()
    conn.close()


def toggle_linkdooni_account(account_id: int) -> bool:
    """Add/remove an account from the linkdooni fleet. Returns True if now selected."""
    conn = _conn()
    row = conn.execute("SELECT 1 FROM linkdooni_accounts WHERE account_id = ?",
                       (account_id,)).fetchone()
    if row:
        conn.execute("DELETE FROM linkdooni_accounts WHERE account_id = ?",
                     (account_id,))
        selected = False
    else:
        conn.execute("INSERT INTO linkdooni_accounts (account_id, updated_at) "
                     "VALUES (?, ?)", (account_id, _now()))
        selected = True
    conn.commit()
    conn.close()
    return selected


def list_linkdooni_account_ids() -> list:
    conn = _conn()
    rows = conn.execute("SELECT account_id FROM linkdooni_accounts "
                        "ORDER BY account_id").fetchall()
    conn.close()
    return [int(r["account_id"]) for r in rows]


def get_linkdooni_account(account_id: int) -> dict:
    conn = _conn()
    row = conn.execute("SELECT * FROM linkdooni_accounts WHERE account_id = ?",
                       (account_id,)).fetchone()
    conn.close()
    return dict(row) if row else {}


def incr_linkdooni_sent(account_id: int, n: int = 1):
    conn = _conn()
    conn.execute("INSERT INTO linkdooni_accounts (account_id, sent_total, updated_at) "
                 "VALUES (?, ?, ?) ON CONFLICT(account_id) DO UPDATE SET "
                 "sent_total = sent_total + ?, updated_at = excluded.updated_at",
                 (account_id, n, _now(), n))
    conn.commit()
    conn.close()


def incr_linkdooni_joined(account_id: int, n: int = 1):
    conn = _conn()
    conn.execute("INSERT INTO linkdooni_accounts (account_id, joined_total, updated_at) "
                 "VALUES (?, ?, ?) ON CONFLICT(account_id) DO UPDATE SET "
                 "joined_total = joined_total + ?, updated_at = excluded.updated_at",
                 (account_id, n, _now(), n))
    conn.commit()
    conn.close()


def linkdooni_seen_link(link: str) -> bool:
    """Record a discovered group link; return True if it is NEW (not seen before)."""
    link = (link or "").strip()
    if not link:
        return False
    conn = _conn()
    try:
        conn.execute("INSERT OR IGNORE INTO linkdooni_seen_links (link, seen_at) "
                     "VALUES (?, ?)", (link, _now()))
        conn.commit()
        is_new = conn.total_changes > 0
    finally:
        conn.close()
    return is_new


def add_linkdooni_group(group_guid: str, link: str, account_id: int, name: str = ""):
    conn = _conn()
    conn.execute(
        "INSERT INTO linkdooni_groups (group_guid, link, name, account_id, joined, "
        "discovered_at) VALUES (?, ?, ?, ?, 0, ?) "
        "ON CONFLICT(group_guid) DO UPDATE SET link=excluded.link, "
        "account_id=excluded.account_id, name=excluded.name",
        (group_guid, link, name, account_id, _now()))
    conn.commit()
    conn.close()


def mark_linkdooni_group_joined(group_guid: str, joined: bool = True):
    conn = _conn()
    conn.execute("UPDATE linkdooni_groups SET joined = ? WHERE group_guid = ?",
                 (1 if joined else 0, group_guid))
    conn.commit()
    conn.close()


def reassign_linkdooni_group(group_guid: str, account_id: int):
    conn = _conn()
    conn.execute("UPDATE linkdooni_groups SET account_id = ?, joined = 0 "
                 "WHERE group_guid = ?", (account_id, group_guid))
    conn.commit()
    conn.close()


def list_linkdooni_groups(account_id: int = None, joined_only: bool = False) -> list:
    conn = _conn()
    q = "SELECT * FROM linkdooni_groups"
    where = []
    args = []
    if account_id is not None:
        where.append("account_id = ?")
        args.append(account_id)
    if joined_only:
        where.append("joined = 1")
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY discovered_at"
    rows = conn.execute(q, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def linkdooni_groups_today_count() -> int:
    """How many groups were discovered today (used for the per-day cap)."""
    today = _now()[:10]
    conn = _conn()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM linkdooni_groups WHERE substr(discovered_at,1,10) = ?",
        (today,)).fetchone()
    conn.close()
    return int(row["n"]) if row else 0



def add_linkdooni_text(text: str):
    text = (text or "").strip()
    if not text:
        return
    conn = _conn()
    conn.execute("INSERT INTO linkdooni_texts (text) VALUES (?)", (text,))
    conn.commit()
    conn.close()


def list_linkdooni_texts() -> list:
    conn = _conn()
    rows = conn.execute("SELECT text FROM linkdooni_texts ORDER BY id").fetchall()
    conn.close()
    return [r["text"] for r in rows]


def clear_linkdooni_texts():
    conn = _conn()
    conn.execute("DELETE FROM linkdooni_texts")
    conn.commit()
    conn.close()
