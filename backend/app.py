from flask import Flask, render_template, request, redirect, url_for, session
from database import get_connection
from decimal import Decimal
from functools import wraps
from werkzeug.security import check_password_hash
from datetime import datetime


app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static",
    static_url_path="/static"
)

app.secret_key = "restaurant_secret_key_123"


# ==================================================
# RESTAURANT DETAILS
# ==================================================

RESTAURANT_NAME = "ABC Restaurant"
RESTAURANT_ADDRESS = "123 Main Road, Nagercoil"
RESTAURANT_PHONE = "9876543210"


# ==================================================
# COUPONS
# ==================================================

COUPONS = {
    "WELCOME10": 10
}


# ==================================================
# LOGIN PROTECTION
# ==================================================

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("admin_login"))

        return function(*args, **kwargs)

    return wrapper


# ==================================================
# HOME
# ==================================================

@app.route("/")
def home():

    # Public billing page removed.
    # Website opens directly to Admin Login.

    return redirect(url_for("admin_login"))


# ==================================================
# ADMIN LOGIN
# ==================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if "user_id" in session:
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, username, password
            FROM admins
            WHERE username = %s
        """, (username,))

        user = cursor.fetchone()

        cursor.close()
        connection.close()

        if user:

            password_correct = check_password_hash(
                user["password"],
                password
            )

            if password_correct:

                session["user_id"] = user["id"]
                session["username"] = user["username"]

                return redirect(
                    url_for("admin_dashboard")
                )

        return render_template(
            "admin/login.html",
            error="Invalid username or password"
        )

    return render_template(
        "admin/login.html"
    )


# ==================================================
# ADMIN LOGOUT
# ==================================================

@app.route("/admin/logout")
def admin_logout():

    session.clear()

    return redirect(
        url_for("admin_login")
    )


# ==================================================
# ADMIN DASHBOARD
# ==================================================

@app.route("/admin")
@login_required
def admin_dashboard():

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT COUNT(*) AS total_products
        FROM products
    """)

    total_products = cursor.fetchone()["total_products"]

    cursor.execute("""
        SELECT COUNT(*) AS available_products
        FROM products
        WHERE is_available = TRUE
    """)

    available_products = cursor.fetchone()["available_products"]

    cursor.execute("""
        SELECT COUNT(*) AS total_bills
        FROM bills
    """)

    total_bills = cursor.fetchone()["total_bills"]

    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) AS total_sales
        FROM bills
    """)

    total_sales = cursor.fetchone()["total_sales"]

    cursor.close()
    connection.close()

    return render_template(
        "admin/dashboard.html",
        username=session["username"],
        total_products=total_products,
        available_products=available_products,
        total_bills=total_bills,
        total_sales=total_sales
    )


# ==================================================
# ADMIN BILLING PAGE
# ==================================================

@app.route("/admin/billing")
@login_required
def admin_billing():

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, name, category, price
        FROM products
        WHERE is_available = TRUE
        ORDER BY id
    """)

    products = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin/billing.html",
        products=products,
        restaurant_name=RESTAURANT_NAME
    )


# ==================================================
# GENERATE BILL
# ==================================================

@app.route("/generate_bill", methods=["POST"])
@login_required
def generate_bill():

    selected_items = request.form.getlist("item_id")
    quantities = request.form.getlist("quantity")

    bill_items = []

    subtotal = Decimal("0.00")

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)


    # ==================================================
    # GET SELECTED PRODUCTS
    # ==================================================

    for item_id, quantity in zip(
        selected_items,
        quantities
    ):

        try:

            item_id = int(item_id)
            quantity = int(quantity)

        except ValueError:

            continue


        if quantity <= 0:
            continue


        cursor.execute("""
            SELECT id, name, price
            FROM products
            WHERE id = %s
            AND is_available = TRUE
        """, (item_id,))


        product = cursor.fetchone()


        if product is None:
            continue


        price = Decimal(
            str(product["price"])
        )


        amount = price * quantity


        bill_items.append({
            "product_id": product["id"],
            "name": product["name"],
            "price": price,
            "quantity": quantity,
            "amount": amount
        })


        subtotal += amount


    cursor.close()


    # ==================================================
    # COUPON / DISCOUNT
    # ==================================================

    coupon_code = request.form.get(
        "coupon",
        ""
    ).strip().upper()


    discount_percentage = Decimal("0.00")

    discount = Decimal("0.00")


    if coupon_code in COUPONS:

        discount_percentage = Decimal(
            str(COUPONS[coupon_code])
        )


        discount = (
            subtotal
            * discount_percentage
            / Decimal("100")
        )


    # ==================================================
    # FINAL AMOUNT
    # ==================================================

    taxable_amount = subtotal - discount

    # GST removed completely.
    gst = Decimal("0.00")

    # Final total is only subtotal minus discount.
    total = taxable_amount


    # ==================================================
    # CUSTOMER DETAILS
    # ==================================================

    # Customer name and phone are no longer used.
    # Empty values are saved because the existing
    # database table still contains these columns.

    customer_name = ""

    customer_phone = ""


    # ==================================================
    # BILL NUMBER
    # ==================================================

    bill_number = (
        "BILL-"
        + datetime.now().strftime(
            "%Y%m%d%H%M%S%f"
        )
    )


    # ==================================================
    # SAVE BILL
    # ==================================================

    cursor = connection.cursor()


    cursor.execute("""
        INSERT INTO bills
        (
            bill_number,
            customer_name,
            customer_phone,
            subtotal,
            discount,
            gst,
            total
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        bill_number,
        customer_name,
        customer_phone,
        subtotal,
        discount,
        gst,
        total
    ))


    bill_id = cursor.lastrowid


    # ==================================================
    # SAVE BILL ITEMS
    # ==================================================

    for item in bill_items:

        cursor.execute("""
            INSERT INTO bill_items
            (
                bill_id,
                product_id,
                product_name,
                price,
                quantity,
                amount
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            bill_id,
            item["product_id"],
            item["name"],
            item["price"],
            item["quantity"],
            item["amount"]
        ))


    connection.commit()


    cursor.close()
    connection.close()


    # ==================================================
    # SHOW BILL
    # ==================================================

    return render_template(
        "bill.html",

        restaurant_name=RESTAURANT_NAME,

        restaurant_address=RESTAURANT_ADDRESS,

        restaurant_phone=RESTAURANT_PHONE,

        bill_items=bill_items,

        subtotal=subtotal,

        coupon_code=coupon_code,

        discount_percentage=discount_percentage,

        discount=discount,

        taxable_amount=taxable_amount,

        gst=gst,

        total=total,

        customer_name=customer_name,

        customer_phone=customer_phone,

        bill_number=bill_number
    )


# ==================================================
# MANAGE PRODUCTS
# ==================================================

@app.route("/admin/products")
@login_required
def admin_products():

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            id,
            name,
            category,
            price,
            is_available
        FROM products
        ORDER BY id
    """)

    products = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin/products.html",
        products=products
    )


# ==================================================
# ADD PRODUCT
# ==================================================

@app.route(
    "/admin/products/add",
    methods=["POST"]
)
@login_required
def add_product():

    name = request.form.get(
        "name",
        ""
    ).strip()


    category = request.form.get(
        "category",
        ""
    ).strip()


    price = request.form.get(
        "price",
        ""
    ).strip()


    if name and category and price:

        try:

            price = Decimal(price)


            if price >= 0:

                connection = get_connection()

                cursor = connection.cursor()


                cursor.execute("""
                    INSERT INTO products
                    (
                        name,
                        category,
                        price
                    )
                    VALUES (%s, %s, %s)
                """, (
                    name,
                    category,
                    price
                ))


                connection.commit()


                cursor.close()
                connection.close()


        except Exception as error:

            print(
                "Error adding product:",
                error
            )


    return redirect(
        url_for("admin_products")
    )


# ==================================================
# EDIT PRODUCT
# ==================================================

@app.route(
    "/admin/products/edit/<int:product_id>",
    methods=["GET", "POST"]
)
@login_required
def edit_product(product_id):

    connection = get_connection()


    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()


        category = request.form.get(
            "category",
            ""
        ).strip()


        price = request.form.get(
            "price",
            ""
        ).strip()


        try:

            price = Decimal(price)


            if name and category and price >= 0:

                cursor = connection.cursor()


                cursor.execute("""
                    UPDATE products
                    SET
                        name = %s,
                        category = %s,
                        price = %s
                    WHERE id = %s
                """, (
                    name,
                    category,
                    price,
                    product_id
                ))


                connection.commit()


                cursor.close()
                connection.close()


                return redirect(
                    url_for("admin_products")
                )


        except Exception as error:

            print(
                "Error editing product:",
                error
            )


    cursor = connection.cursor(
        dictionary=True
    )


    cursor.execute("""
        SELECT
            id,
            name,
            category,
            price
        FROM products
        WHERE id = %s
    """, (product_id,))


    product = cursor.fetchone()


    cursor.close()
    connection.close()


    if product is None:

        return "Product not found", 404


    return render_template(
        "admin/edit_product.html",
        product=product
    )


# ==================================================
# ENABLE / DISABLE PRODUCT
# ==================================================

@app.route(
    "/admin/products/toggle/<int:product_id>"
)
@login_required
def toggle_product(product_id):

    connection = get_connection()

    cursor = connection.cursor()


    cursor.execute("""
        UPDATE products
        SET is_available = NOT is_available
        WHERE id = %s
    """, (product_id,))


    connection.commit()


    cursor.close()
    connection.close()


    return redirect(
        url_for("admin_products")
    )


# ==================================================
# RUN APPLICATION
# ==================================================

if __name__ == "__main__":

    app.run(debug=True)