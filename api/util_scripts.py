# Inspect DB 

import sqlite3

conn = sqlite3.connect("data/conversations.db")
c = conn.cursor()

print("Tables:")
for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    print(row)

print("\nSummaries:")
for row in c.execute("SELECT conversation_id, content FROM summaries"):
    print(row)

print("\nMessages:")
for row in c.execute(
    "SELECT id, role, content FROM messages WHERE conversation_id='summary-test-1'"
):
    print(row)

print("\Profile:")
for row in c.execute(
    "SELECT goals, constraints, preferences FROM profile WHERE conversation_id='summary-test-1'"
):
    print(row)

conn.close()

# Count messages
import sqlite3

conn = sqlite3.connect("data/conversations.db")
c = conn.cursor()

count = c.execute(
    "SELECT COUNT(*) FROM messages WHERE conversation_id='summary-test-1'"
).fetchone()[0]

print("Message count:", count)
conn.close()
