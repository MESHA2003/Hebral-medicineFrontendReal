import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'db.sqlite3')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if columns already exist
cursor.execute("PRAGMA table_info(accounts_user)")
columns = [col[1] for col in cursor.fetchall()]

if 'is_blocked' not in columns:
    cursor.execute("ALTER TABLE accounts_user ADD COLUMN is_blocked bool NOT NULL DEFAULT 0")
    print("Added 'is_blocked' column")

if 'last_password_change' not in columns:
    cursor.execute("ALTER TABLE accounts_user ADD COLUMN last_password_change datetime NULL")
    print("Added 'last_password_change' column")

if 'is_blocked' in columns and 'last_password_change' in columns:
    print("Columns already exist - no changes needed")

conn.commit()
conn.close()

# Also update the django_migrations table to mark migration as applied
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT name FROM django_migrations WHERE app='accounts' AND name='0002_user_is_blocked_user_last_password_change'")
if not cursor.fetchone():
    cursor.execute(
        "INSERT INTO django_migrations (app, name, applied) VALUES (?, ?, datetime('now'))",
        ('accounts', '0002_user_is_blocked_user_last_password_change')
    )
    print("Migration recorded in django_migrations table")
else:
    print("Migration already recorded")
conn.commit()
conn.close()

print("\nDone! The database is now up to date.")