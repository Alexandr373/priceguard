import sqlite3
import os

DB_PATH = os.getenv("DB_PATH", "priceguard.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER,
            link TEXT,
            platform TEXT,
            min_price REAL,
            current_price REAL,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS violations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            old_price REAL,
            new_price REAL,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

def add_product(tg_id, link, platform, min_price, name=""):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "INSERT INTO products (tg_id, link, platform, min_price, current_price, name) VALUES (?, ?, ?, ?, ?, ?)",
        (tg_id, link, platform, min_price, min_price, name)
    )
    pid = cur.lastrowid
    conn.commit()
    conn.close()
    return pid

def get_products(tg_id=None):
    conn = sqlite3.connect(DB_PATH)
    if tg_id:
        cur = conn.execute("SELECT * FROM products WHERE tg_id = ?", (tg_id,))
    else:
        cur = conn.execute("SELECT * FROM products")
    rows = cur.fetchall()
    conn.close()
    return rows

def update_price(product_id, new_price):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE products SET current_price = ? WHERE id = ?", (new_price, product_id))
    conn.commit()
    conn.close()

def add_violation(product_id, old_price, new_price):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "INSERT INTO violations (product_id, old_price, new_price) VALUES (?, ?, ?)",
        (product_id, old_price, new_price)
    )
    vid = cur.lastrowid
    conn.commit()
    conn.close()
    return vid

def get_violations(tg_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("""
        SELECT v.id, v.product_id, v.old_price, v.new_price, v.detected_at,
               p.link, p.name, p.min_price
        FROM violations v JOIN products p ON v.product_id = p.id
        WHERE p.tg_id = ? ORDER BY v.detected_at DESC LIMIT 20
    """, (tg_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def delete_product(product_id, tg_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM products WHERE id = ? AND tg_id = ?", (product_id, tg_id))
    conn.execute("DELETE FROM violations WHERE product_id = ?", (product_id,))
    conn.commit()
    conn.close()
