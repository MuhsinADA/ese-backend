# ESE Task Manager — Backend API

REST API for the ESE Enterprise Task Management System, built with **Django 4.2**, **Django REST Framework**, and **PostgreSQL**. Provides JWT authentication, task/category CRUD with filtering and pagination, SendGrid email integration, and Cloudinary profile image uploads.

> **Companion repo:** [ese-frontend](https://github.com/MuhsinADA/ese-frontend) (React)

---

## Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [Setup & Installation](#setup--installation)
5. [API Documentation](#api-documentation)
6. [Testing](#testing)
7. [Deployment](#deployment)
8. [Technical Decisions](#technical-decisions)
9. [AI Acknowledgement](#ai-acknowledgement)

---

## Features

**Authentication**
- User registration with email validation
- JWT login (30-min access / 7-day refresh tokens)
- Token refresh with rotation and blacklisting
- Password change (authenticated)
- Password reset via SendGrid email flow
- Profile management (view, update, image upload via Cloudinary)

**Task Management**
- Full CRUD for tasks (create, read, update, delete)
- Status lifecycle: `todo` → `in_progress` → `done` (enforced transitions)
- Priority levels: `low`, `medium`, `high`, `urgent`
- Optional due dates with past-date validation on creation
- Overdue detection (computed property)
- Category association (optional, SET_NULL on delete)
- Filtering by status, priority, category, search term, and overdue flag
- Sorting by any field (prefix `-` for descending)
- Pagination (default 10 per page)
- Task statistics endpoint (counts by status/priority)

**Categories**
- Full CRUD for user-scoped categories
- Unique name constraint per user
- Hex colour code support

**Security**
- All task/category endpoints require valid JWT
- Users can only access their own resources (queryset-level isolation)
- CORS restricted to configured frontend origin
- Rate limiting (30/min anonymous, 120/min authenticated)
- HTTPS enforcement, HSTS, secure cookies in production
- Django's PBKDF2 password hashing

---

## Architecture

```
┌─────────────┐       HTTPS/JSON       ┌──────────────────┐       SQL        ┌────────────┐
│   React      │  ◄──────────────────►  │  Django REST API  │  ◄────────────►  │ PostgreSQL │
│   (Vite)     │                        │  (DRF + JWT)      │                  │            │
│   Tailwind   │                        │  SendGrid         │                  │            │
│              │                        │  Cloudinary       │                  │            │
└─────────────┘                        └──────────────────┘                  └────────────┘
   Render                                 Render                              Render
   Static Site                            Web Service                         Managed DB
```

The frontend communicates exclusively with this REST API. The database is accessed only via Django — never directly by the frontend.

### Project Structure

```
backend/
├── config/                 # Django project settings, URLs, WSGI
│   ├── settings.py         # Environment-based config (django-environ)
│   ├── urls.py             # Root URL config: /api/v1/auth/ + /api/v1/
│   └── wsgi.py
├── apps/
│   ├── accounts/           # Custom User model, auth views, profile, emails
│   │   ├── models.py       # User (AbstractUser + UUID PK, bio, profile_image)
│   │   ├── serializers.py
│   │   ├── views.py        # Register, Login, Logout, Profile, PasswordReset...
│   │   ├── urls.py         # 9 auth endpoints
│   │   ├── emails.py       # SendGrid integration
│   │   ├── cloudinary_utils.py
│   │   └── tests/
│   └── tasks/              # Task + Category domain logic
│       ├── models.py       # Task (status/priority/due_date), Category
│       ├── serializers.py  # Validation, business rules
│       ├── views.py        # ViewSets with filtering/sorting/pagination
│       ├── filters.py      # django-filter FilterSets
│       ├── permissions.py  # IsOwner permission
│       ├── urls.py         # Router-generated endpoints
│       └── tests/
├── conftest.py             # Shared fixtures + factory-boy factories
├── pytest.ini              # Pytest configuration
├── Makefile                # Dev commands: make run, make test, etc.
├── build.sh                # Render build script
├── Procfile                # Gunicorn start command
├── render.yaml             # Render Blueprint (API + PostgreSQL)
├── requirements.txt
└── .env.example
```

---

## Tech Stack

| Layer         | Technology                                      |
|---------------|--------------------------------------------------|
| Framework     | Django 4.2, Django REST Framework 3.16           |
| Auth          | djangorestframework-simplejwt 5.5 (JWT)          |
| Database      | PostgreSQL (psycopg2-binary, dj-database-url)    |
| Email         | SendGrid 6.12                                    |
| Media Storage | Cloudinary 1.44                                  |
| CORS          | django-cors-headers 4.9                          |
| Filtering     | django-filter 25.1                               |
| Config        | django-environ 0.13                              |
| Static Files  | WhiteNoise 6.11                                  |
| Testing       | pytest 8.4, pytest-cov, factory-boy 3.3          |
| Server        | Gunicorn 23.0                                    |

---

## Setup & Installation

### Prerequisites

- **Python 3.9+** (3.11 recommended)
- **PostgreSQL** running locally (or a remote connection string)
- **pip3** and **venv** available

### 1. Clone the Repository

```bash
git clone https://github.com/MuhsinADA/ese-backend.git
cd ese-backend
```

### 2. Create a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate    # macOS / Linux / Codespaces
```

> **Windows:** `venv\Scripts\activate`

### 3. Install Dependencies

```bash
pip3 install -r requirements.txt
```

> If `psycopg2-binary` fails on macOS, install PostgreSQL headers first:
> ```bash
> brew install postgresql
> ```
> On Ubuntu/Codespaces: `sudo apt-get install -y libpq-dev`

### 4. Create the PostgreSQL Database

```bash
psql postgres
```
```sql
CREATE DATABASE ese_tasks;
\q
```

> If you're using Codespaces and PostgreSQL isn't installed, add a PostgreSQL service to your devcontainer or use a remote `DATABASE_URL`.

### 5. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```dotenv
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True
DATABASE_URL=postgres://your_user:your_password@localhost:5432/ese_tasks
```

To generate a secret key:

```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

> **Optional services:** `SENDGRID_API_KEY`, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` — leave empty if you don't need email/image features locally.

### 6. Run Migrations

```bash
python3 manage.py migrate
```

### 7. Start the Dev Server

Using the Makefile (recommended — automatically frees port 8000 if occupied):

```bash
make run
```

Or manually:

```bash
python3 manage.py runserver 8000
```

The API is now available at **http://localhost:8000/api/v1/**.

### Makefile Commands

| Command            | Description                                   |
|--------------------|-----------------------------------------------|
| `make run`         | Kill port 8000 + start Django dev server      |
| `make run PORT=9000` | Use a custom port                           |
| `make test`        | Run pytest with coverage                      |
| `make migrate`     | Apply database migrations                     |
| `make makemigrations` | Create new migrations                      |
| `make shell`       | Open Django interactive shell                 |
| `make kill-port`   | Free port 8000 without starting the server    |
| `make help`        | Show all available commands                   |

### Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: No module named 'django'` | Activate the virtualenv: `source venv/bin/activate` |
| `psycopg2` installation fails | Install PostgreSQL headers (`brew install postgresql` or `apt-get install libpq-dev`) |
| `FATAL: database "ese_tasks" does not exist` | Create it: `psql postgres -c "CREATE DATABASE ese_tasks;"` |
| `FATAL: role "..." does not exist` | Create a role or use your system user: `psql postgres -c "CREATE ROLE your_user WITH LOGIN PASSWORD 'pass';"` |
| Port 8000 already in use | Run `make kill-port` or `lsof -ti:8000 \| xargs kill -9` |
| `DJANGO_SECRET_KEY` error on startup | Ensure `.env` exists and contains `DJANGO_SECRET_KEY=...` |
| CORS errors from the frontend | Check `CORS_ALLOWED_ORIGINS` in `.env` matches your frontend URL (default: `http://localhost:5173`) |
| Migrations fail after model changes | Run `python3 manage.py makemigrations` before `migrate` |

---

## API Documentation

Base URL: `/api/v1/`

### Authentication Endpoints (`/api/v1/auth/`)

| Method | Endpoint                        | Auth | Description                       |
|--------|---------------------------------|------|-----------------------------------|
| POST   | `/auth/register/`               | No   | Register a new user               |
| POST   | `/auth/login/`                  | No   | Login → returns JWT tokens        |
| POST   | `/auth/logout/`                 | Yes  | Blacklist the refresh token       |
| POST   | `/auth/token/refresh/`          | No   | Refresh access token              |
| GET    | `/auth/profile/`                | Yes  | Get current user profile          |
| PATCH  | `/auth/profile/`                | Yes  | Update profile (name, bio)        |
| POST   | `/auth/profile/upload-image/`   | Yes  | Upload profile image (Cloudinary) |
| POST   | `/auth/change-password/`        | Yes  | Change password                   |
| POST   | `/auth/password-reset/`         | No   | Request password reset email      |
| POST   | `/auth/password-reset/confirm/` | No   | Confirm reset with token          |

### Task Endpoints (`/api/v1/tasks/`)

| Method | Endpoint         | Auth | Description                                |
|--------|------------------|------|--------------------------------------------|
| GET    | `/tasks/`        | Yes  | List tasks (filterable, sortable, paginated) |
| POST   | `/tasks/`        | Yes  | Create a task                              |
| GET    | `/tasks/{id}/`   | Yes  | Get task detail                            |
| PATCH  | `/tasks/{id}/`   | Yes  | Update a task                              |
| DELETE | `/tasks/{id}/`   | Yes  | Delete a task                              |
| GET    | `/tasks/stats/`  | Yes  | Task statistics                            |

**Query Parameters for `GET /tasks/`:**

| Parameter   | Example                    | Description                              |
|-------------|----------------------------|------------------------------------------|
| `status`    | `?status=todo,in_progress` | Filter by status (comma-separated)       |
| `priority`  | `?priority=high,urgent`    | Filter by priority                       |
| `category`  | `?category={uuid}`         | Filter by category ID                    |
| `search`    | `?search=keyword`          | Search title and description             |
| `ordering`  | `?ordering=-due_date`      | Sort by field (`-` prefix = descending)  |
| `overdue`   | `?overdue=true`            | Filter overdue tasks only                |
| `page`      | `?page=2`                  | Pagination (10 per page)                 |

### Category Endpoints (`/api/v1/categories/`)

| Method | Endpoint              | Auth | Description          |
|--------|-----------------------|------|----------------------|
| GET    | `/categories/`        | Yes  | List categories      |
| POST   | `/categories/`        | Yes  | Create category      |
| PATCH  | `/categories/{id}/`   | Yes  | Update category      |
| DELETE | `/categories/{id}/`   | Yes  | Delete category      |

---

## Testing

131 tests with 97% coverage, covering authentication, task/category CRUD, permissions, business rules, and model integrity.

### Run Tests

```bash
make test
```

Or directly:

```bash
source venv/bin/activate
pytest --cov --cov-report=term-missing
```

### Test Structure

| Area                | What's Tested                                                     |
|---------------------|-------------------------------------------------------------------|
| **Auth views**      | Registration (valid/invalid), login, token refresh, logout        |
| **Profile**         | Get/update profile, image upload, change password                 |
| **Password reset**  | Request reset, confirm reset with token                           |
| **Task CRUD**       | Create, read, update, delete, list with all filter combinations   |
| **Task validation** | Status transitions, due date rules, overdue detection             |
| **Category CRUD**   | Create, update, delete, unique-per-user constraint                |
| **Permissions**     | Unauthenticated access blocked, cross-user isolation              |
| **Models**          | String representations, defaults, constraints                     |
| **Serializers**     | Field validation, business rule enforcement                       |

### Tools

- **pytest** + **pytest-django** — test runner
- **factory-boy** — test data factories (`UserFactory`, `TaskFactory`, `CategoryFactory`)
- **pytest-cov** — coverage reporting
- **DRF APIClient** — API integration testing

---

## Deployment

Deployed to **Render** as a Web Service with a managed PostgreSQL database.

### Render Blueprint

The `render.yaml` file defines the full infrastructure:
- **ese-task-api** — Python web service (Gunicorn)
- **ese-tasks-db** — Managed PostgreSQL (free tier)

### Environment Variables (Production)

| Variable                 | Value / Source                              |
|--------------------------|---------------------------------------------|
| `DJANGO_SECRET_KEY`      | Auto-generated by Render                    |
| `DJANGO_DEBUG`           | `False`                                     |
| `DATABASE_URL`           | Auto-injected from Render PostgreSQL        |
| `ALLOWED_HOSTS`          | `.onrender.com`                             |
| `CORS_ALLOWED_ORIGINS`   | `https://<frontend>.onrender.com`           |
| `FRONTEND_BASE_URL`      | `https://<frontend>.onrender.com`           |
| `SENDGRID_API_KEY`       | Set manually in Render dashboard            |
| `CLOUDINARY_CLOUD_NAME`  | Set manually in Render dashboard            |
| `CLOUDINARY_API_KEY`     | Set manually in Render dashboard            |
| `CLOUDINARY_API_SECRET`  | Set manually in Render dashboard            |

### CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`):
1. **On push/PR to `main`** → runs pytest with a PostgreSQL 15 service container
2. **On push to `main`** → triggers Render deploy via webhook

The `RENDER_DEPLOY_HOOK_URL` secret must be set in the GitHub repository settings.

---

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| **Django REST Framework** | Industry-standard for building REST APIs in Python; serializers, viewsets, and routers reduce boilerplate |
| **JWT (simplejwt)** | Stateless authentication suitable for SPA ↔ API architecture; access/refresh pattern with rotation and blacklisting |
| **UUID primary keys** | Enterprise convention — prevents sequential ID enumeration and information disclosure |
| **ViewSets + Routers** | Consistent URL generation, less boilerplate, DRF best practice |
| **django-environ** | Clean environment variable management following 12-factor app methodology |
| **dj-database-url** | Parse `DATABASE_URL` connection strings — standard for cloud deployment (Render, Heroku) |
| **django-filter** | Declarative queryset filtering via FilterSets — clean, testable, DRF-integrated |
| **pytest over Django TestCase** | More Pythonic fixtures, better parametrisation, widely adopted in enterprise Python |
| **factory-boy** | Declarative test data factories — maintainable, avoids brittle fixtures |
| **WhiteNoise** | Serve static files without a separate web server — simpler deployment |
| **SendGrid** | Enterprise email delivery service — reliable, easy API, widely used for transactional email |
| **Cloudinary** | Managed media storage — offloads file hosting, provides image transformations via URL |
| **Separate `apps/` directory** | Clean organisation — each Django app is self-contained and potentially reusable |
| **Rate limiting** | DRF throttling protects auth endpoints from brute-force attacks |

---

## AI Acknowledgement

GitHub Copilot was used as a development assistant throughout this project for:
- Code generation and scaffolding
- Debugging and troubleshooting
- Test writing assistance
- Documentation drafting

All generated code was reviewed, understood, and adapted to fit the project's architecture and requirements. The developer maintains full understanding of and responsibility for all submitted work.
