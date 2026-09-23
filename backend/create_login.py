from database import get_connection
from werkzeug.security import generate_password_hash

username = "staff"
password = "staff123"

hashed_password = generate_password_hash(password)

connection = get_connection()
cursor = connection.cursor()

query = """
INSERT INTO admins
(username, password)
VALUES (%s, %s)
"""

cursor.execute(query, (username, hashed_password))

connection.commit()

print("Login created successfully!")
print("Username:", username)
print("Password:", password)

cursor.close()
connection.close()