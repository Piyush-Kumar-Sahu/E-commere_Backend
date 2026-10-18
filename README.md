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
- Supabase PostgreSQL instance (or PostgreSQL 14+)

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

Configure your Supabase `DATABASE_URL` (with SSL) and SMTP settings in `.env`.

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
python manage.py test apps.core
```

## Production Deployment & Render Configuration

### 1. Allowed Hosts & Debug Safeguards

- **ALLOWED_HOSTS**: The production domain `e-commere-backend.onrender.com` is configured in `DEFAULT_ALLOWED_HOSTS`, alongside local development addresses (`localhost`, `127.0.0.1`, `0.0.0.0`, `[::1]`, and `testserver`). Any dynamic host set in `RENDER_EXTERNAL_HOSTNAME` is automatically appended. Wildcard hosts (`*`) are strictly blocked.
- **Production `DEBUG=False`**: The application automatically detects production environments via Render system variables (`RENDER=true`, `RENDER_EXTERNAL_HOSTNAME`) and `ENVIRONMENT=production`, strictly enforcing `DEBUG=False`. In local development, `DEBUG` defaults to `True`.
- **CSRF Protection**: `https://e-commere-backend.onrender.com` is automatically registered under `CSRF_TRUSTED_ORIGINS` to ensure authenticated administrative operations function correctly on Render.

### 2. Render Free-Tier Sleep Behavior & Compliance

- **15-Minute Inactivity Sleep**: Render's free web service tier spins down (puts to sleep) services after 15 minutes without incoming HTTP traffic.
- **Cold-Start Latency**: When a sleeping service receives an incoming request, Render spins up the container. This cold start typically introduces a 30–50 second delay on the initial request.
- **Strict Compliance Notice**: Do **not** employ automated external keep-alive pingers (such as UptimeRobot, cron-job.org, or Pingdom) or internal self-pinging loops to artificially prevent free-tier instances from sleeping. Doing so violates Render's Terms of Service and Acceptable Use Policy and can result in account suspension.

### 3. Safe, Configurable Health Check Endpoint

A passive, standards-compliant health-check endpoint is available at multiple paths:
- **Paths**: `/health/`, `/healthz/`, `/api/v1/health/`
- **Render Dashboard Configuration**: In the Render Dashboard (Web Service > Settings > Health Check Path), set the path to `/health/` or `/api/v1/health/`. Render uses this during deployments to verify that the service is running before routing production traffic.
- **Configurable Database Probing**:
  - `GET /api/v1/health/` (default): Checks overall service status and verifies PostgreSQL database connectivity with `SELECT 1`.
  - `GET /api/v1/health/?check_db=false`: Lightweight liveness check that skips database queries to avoid exhausting database connection pools during frequent load balancer checks.
  - Setting `HEALTH_CHECK_INCLUDE_DB=False` in environment variables disables database checks by default.

### 4. Options for Keeping the Backend Responsive

To eliminate or manage the cold-start delay:

1. **Eligible Paid Hosting Plan (Recommended for Continuous Availability)**:
   - Upgrade the Render Web Service to a paid instance (e.g., the **Starter** plan at $7/month or higher).
   - Paid instances **never spin down or sleep**, have dedicated CPU and memory, provide zero cold-start latency, and support persistent background workers.
2. **Graceful Frontend Cold-Start Handling (Free Tier)**:
   - Configure the frontend application (Vite/React) to detect initial connection delays or 502/504 gateway states and display a user-friendly status banner:
     *"The server is waking up from sleep mode (Render free tier). Please allow ~30–45 seconds for initial connection..."*
   - Implement an automated retry mechanism with exponential backoff on initial API calls.
