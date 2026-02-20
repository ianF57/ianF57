# Shopify Lite (Full App)

A complete Shopify-style e-commerce MVP built with **Flask + SQLite**.

## Features
- User registration/login/logout
- Product catalog and product details
- Shopping cart (add/remove)
- Checkout flow that creates orders and updates stock
- User order history
- Admin panel to create products
- Seeded demo products and admin account

## Stack
- Flask
- SQLite
- Jinja2 templates
- Plain CSS
- Pytest

## Quick start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open: `http://localhost:5000`

## Demo admin login
- Email: `admin@shopify.local`
- Password: `admin123`

## Tests
```bash
pytest
```
