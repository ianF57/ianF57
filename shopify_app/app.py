from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "shopify.db"


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key"),
        DATABASE=str(DATABASE_PATH),
    )

    if test_config:
        app.config.update(test_config)

    def get_db() -> sqlite3.Connection:
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
        return g.db

    def close_db(_: Any = None) -> None:
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def init_db() -> None:
        db = get_db()
        with open(BASE_DIR / "schema.sql", "r", encoding="utf-8") as schema_file:
            db.executescript(schema_file.read())
        db.execute(
            """
            INSERT INTO users (name, email, password_hash, is_admin)
            VALUES (?, ?, ?, 1)
            """,
            ("Admin", "admin@shopify.local", generate_password_hash("admin123")),
        )
        db.executemany(
            """
            INSERT INTO products (name, description, price_cents, stock, image_url)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    "Nebula Headphones",
                    "Noise-canceling over-ear headphones with 30-hour battery life.",
                    12999,
                    40,
                    "https://images.unsplash.com/photo-1505740420928-5e560c06d30e",
                ),
                (
                    "Comet Smartwatch",
                    "Track your fitness, sleep, and notifications in one sleek watch.",
                    19999,
                    25,
                    "https://images.unsplash.com/photo-1523275335684-37898b6baf30",
                ),
                (
                    "Aurora Lamp",
                    "Smart ambient desk lamp with app-based color controls.",
                    7999,
                    60,
                    "https://images.unsplash.com/photo-1507473885765-e6ed057f782c",
                ),
            ],
        )
        db.commit()

    @app.teardown_appcontext
    def teardown_db(exception: Any = None) -> None:
        close_db(exception)

    @app.context_processor
    def inject_user() -> dict[str, Any]:
        user = None
        if session.get("user_id"):
            user = get_db().execute(
                "SELECT * FROM users WHERE id = ?", (session["user_id"],)
            ).fetchone()
        return {"current_user": user}

    @app.template_filter("money")
    def money_filter(value: int) -> str:
        return f"R{value / 100:,.2f}"

    @app.route("/")
    def home() -> str:
        products = get_db().execute(
            "SELECT * FROM products ORDER BY created_at DESC"
        ).fetchall()
        return render_template("home.html", products=products)

    @app.route("/product/<int:product_id>")
    def product_detail(product_id: int) -> str:
        product = get_db().execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if product is None:
            flash("Product not found.", "error")
            return redirect(url_for("home"))
        return render_template("product_detail.html", product=product)

    @app.route("/register", methods=["GET", "POST"])
    def register() -> str:
        if request.method == "POST":
            name = request.form["name"].strip()
            email = request.form["email"].strip().lower()
            password = request.form["password"]
            if not all([name, email, password]):
                flash("All fields are required.", "error")
            else:
                db = get_db()
                try:
                    db.execute(
                        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                        (name, email, generate_password_hash(password)),
                    )
                    db.commit()
                    flash("Account created. Please sign in.", "success")
                    return redirect(url_for("login"))
                except sqlite3.IntegrityError:
                    flash("Email already exists.", "error")
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login() -> str:
        if request.method == "POST":
            email = request.form["email"].strip().lower()
            password = request.form["password"]
            user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"] = user["id"]
                flash("Welcome back!", "success")
                return redirect(url_for("home"))
            flash("Invalid credentials.", "error")
        return render_template("login.html")

    @app.route("/logout")
    def logout() -> str:
        session.clear()
        flash("Signed out.", "success")
        return redirect(url_for("home"))

    def require_login() -> sqlite3.Row | None:
        if not session.get("user_id"):
            flash("Please sign in first.", "error")
            return None
        return get_db().execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

    @app.route("/cart")
    def cart() -> str:
        user = require_login()
        if user is None:
            return redirect(url_for("login"))
        items = get_db().execute(
            """
            SELECT ci.quantity, p.*
            FROM cart_items ci
            JOIN products p ON p.id = ci.product_id
            WHERE ci.user_id = ?
            """,
            (user["id"],),
        ).fetchall()
        total_cents = sum(item["price_cents"] * item["quantity"] for item in items)
        return render_template("cart.html", items=items, total_cents=total_cents)

    @app.post("/cart/add/<int:product_id>")
    def add_to_cart(product_id: int) -> str:
        user = require_login()
        if user is None:
            return redirect(url_for("login"))
        db = get_db()
        product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if product is None or product["stock"] <= 0:
            flash("This product is unavailable.", "error")
            return redirect(url_for("home"))
        existing = db.execute(
            "SELECT * FROM cart_items WHERE user_id = ? AND product_id = ?",
            (user["id"], product_id),
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE cart_items SET quantity = quantity + 1 WHERE id = ?",
                (existing["id"],),
            )
        else:
            db.execute(
                "INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, 1)",
                (user["id"], product_id),
            )
        db.commit()
        flash("Added to cart.", "success")
        return redirect(url_for("cart"))

    @app.post("/cart/remove/<int:product_id>")
    def remove_from_cart(product_id: int) -> str:
        user = require_login()
        if user is None:
            return redirect(url_for("login"))
        db = get_db()
        db.execute(
            "DELETE FROM cart_items WHERE user_id = ? AND product_id = ?",
            (user["id"], product_id),
        )
        db.commit()
        flash("Item removed.", "success")
        return redirect(url_for("cart"))

    @app.post("/checkout")
    def checkout() -> str:
        user = require_login()
        if user is None:
            return redirect(url_for("login"))
        db = get_db()
        items = db.execute(
            """
            SELECT ci.quantity, p.*
            FROM cart_items ci
            JOIN products p ON p.id = ci.product_id
            WHERE ci.user_id = ?
            """,
            (user["id"],),
        ).fetchall()
        if not items:
            flash("Your cart is empty.", "error")
            return redirect(url_for("cart"))

        for item in items:
            if item["stock"] < item["quantity"]:
                flash(f"Not enough stock for {item['name']}.", "error")
                return redirect(url_for("cart"))

        total_cents = sum(item["price_cents"] * item["quantity"] for item in items)
        cursor = db.execute(
            "INSERT INTO orders (user_id, total_cents) VALUES (?, ?)",
            (user["id"], total_cents),
        )
        order_id = cursor.lastrowid

        for item in items:
            db.execute(
                """
                INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents)
                VALUES (?, ?, ?, ?)
                """,
                (order_id, item["id"], item["quantity"], item["price_cents"]),
            )
            db.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ?",
                (item["quantity"], item["id"]),
            )

        db.execute("DELETE FROM cart_items WHERE user_id = ?", (user["id"],))
        db.commit()
        flash("Order placed successfully!", "success")
        return redirect(url_for("orders"))

    @app.route("/orders")
    def orders() -> str:
        user = require_login()
        if user is None:
            return redirect(url_for("login"))
        order_rows = get_db().execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()
        return render_template("orders.html", orders=order_rows)

    @app.route("/admin/products", methods=["GET", "POST"])
    def admin_products() -> str:
        user = require_login()
        if user is None:
            return redirect(url_for("login"))
        if not user["is_admin"]:
            flash("Admin access required.", "error")
            return redirect(url_for("home"))

        db = get_db()
        if request.method == "POST":
            db.execute(
                """
                INSERT INTO products (name, description, price_cents, stock, image_url)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    request.form["name"],
                    request.form["description"],
                    int(float(request.form["price"]) * 100),
                    int(request.form["stock"]),
                    request.form["image_url"],
                ),
            )
            db.commit()
            flash("Product created.", "success")
            return redirect(url_for("admin_products"))

        products = db.execute("SELECT * FROM products ORDER BY created_at DESC").fetchall()
        return render_template("admin_products.html", products=products)

    @app.cli.command("init-db")
    def init_db_command() -> None:
        init_db()
        print("Database initialized.")

    with app.app_context():
        db_file = Path(app.config["DATABASE"])
        if not db_file.exists():
            init_db()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
