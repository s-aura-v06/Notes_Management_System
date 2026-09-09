import sqlite3


conn = sqlite3.connect("database/database.db")

cursor = conn.cursor()


cursor.execute("""
ALTER TABLE users
ADD COLUMN profile_image TEXT
""")


conn.commit()

conn.close()


print("profile_image column added successfully")