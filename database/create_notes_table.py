import sqlite3

conn = sqlite3.connect("database/database.db")

cursor = conn.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS notes(

    note_id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER,

    title TEXT NOT NULL,

    content TEXT NOT NULL,

    tags TEXT,

    is_favorite INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(user_id) REFERENCES users(user_id)

)
""")


conn.commit()

conn.close()


print("Notes table created successfully!")