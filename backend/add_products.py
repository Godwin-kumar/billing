from database import get_connection


products = [
    ("Chicken Biriyani", "Biriyani", 180),
    ("Veg Biriyani", "Biriyani", 140),
    ("Chicken Fried Rice", "Rice", 160),
    ("Veg Fried Rice", "Rice", 120),
    ("Chicken 65", "Starters", 150),
    ("Parotta", "Bread", 20),
    ("Dosa", "Tiffin", 50),
    ("Idli", "Tiffin", 40),
    ("Fresh Lime Juice", "Drinks", 50),
    ("Tea", "Drinks", 20)
]


connection = get_connection()

cursor = connection.cursor()


query = """
INSERT INTO products
(name, category, price)
VALUES (%s, %s, %s)
"""


for product in products:

    cursor.execute(query, product)


connection.commit()


print("Products added successfully!")


cursor.close()

connection.close()