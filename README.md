# Modiecommers — Backend API Service

Django REST Framework backend for **Modiecommers**, a luxury fine jewellery and solitaire e-commerce platform.

## Features

- **Authentication & Security**: Custom User model, JWT authentication via SimpleJWT, role-based access control (Customer, Staff, Admin), 6-digit cryptographic OTP email verification and OTP-based password recovery.
- **Jewellery Catalogue**: Categories (Rings, Necklaces, Earrings, Bracelets, Pendants), curated suites, gemstones, metals, certifications (SGL, IGI, BIS Hallmark), price breakdowns, and rich filtering.
- **Cart & Guest Session Management**: Persistent cart for authenticated patrons and guest session tracking via `X-Cart-Session`.
- **Checkout & Orders**: Multi-step checkout with address management, order state machine, payment integration scaffolding, and shipment telemetry.
- **Promotions & Loyalty**: Discount coupons, promotional banner management, and store configuration settings.
- **Reviews & Ratings**: Verified purchaser reviews, star ratings, and administrator moderation.
- **Owner / Administrator Portal**: Dedicated operational endpoints for product cataloguing, inventory management, order fulfilment, and dashboard analytics.

## Tech Stack

- **Framework**: Django 5.2 & Django REST Framework
- **Database**: PostgreSQL (psycopg2-binary)
- **Authentication**: JWT (djangorestframework-simplejwt)
- **Email Service**: SMTP with TLS (Gmail App Password support) and cryptographically secure OTP handling
- **Image Processing**: Pillow

## Quick Start

### 1. Prerequisites

- Python 3.11+
- PostgreSQL server (14+)

### 2. Environment Setup

```bash
# Navigate to the backend directory
cd backend

# Create and activate a virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration

Copy the sample environment file and configure your credentials:

```bash
cp .env.example .env
```

Configure your PostgreSQL database parameters and SMTP settings in `.env`.

### 4. Database Migrations & Initial Data

```bash
# Run database migrations
python manage.py migrate

# (Optional) Seed demo catalogue, categories, and test accounts
python manage.py seed_demo_data
```

### 5. Start the Development Server

```bash
python manage.py runserver 127.0.0.1:8000
```

The API will be available at `http://127.0.0.1:8000/api/v1/`.

## Running Tests

Execute the automated test suite:

```bash
python manage.py test apps.accounts
```
