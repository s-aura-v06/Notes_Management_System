import sqlite3

conn = sqlite3.connect("database/database.db")
cursor = conn.cursor()

try:
    cursor.execute("""
        ALTER TABLE users
        ADD COLUMN reset_token TEXT
    """)
    print("reset_token column added")
except sqlite3.OperationalError:
    print("reset_token already exists")

try:
    cursor.execute("""
        ALTER TABLE users
        ADD COLUMN reset_token_expiry TEXT
    """)
    print("reset_token_expiry column added")
except sqlite3.OperationalError:
    print("reset_token_expiry already exists")

conn.commit()
conn.close()

print("Database update completed!")