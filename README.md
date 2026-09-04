# 📦 StockFlow API

[![Python Version](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B-336791.svg)](https://www.postgresql.org/)
[![Supabase](https://img.shields.io/badge/Supabase-Auth-3ECF8E.svg)](https://supabase.com/)
[![Package Manager](https://img.shields.io/badge/uv-Package%20Manager-purple.svg)](https://astral.sh/uv)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)

**StockFlow** is a modern, high-performance Inventory and Order Management System REST API built with **FastAPI**, **SQLAlchemy 2.0**, **PostgreSQL**, and **Supabase Authentication**. It provides a robust backend for businesses to manage products, monitor real-time stock, organize suppliers, issue purchase orders, and seamlessly process customer orders.

---

## 📌 Table of Contents

- [Overview & Concise Summary](#-overview--concise-summary)
- [Key Features](#-key-features)
- [Technologies Used](#-technologies-used)
- [System Architecture & Project Flow](#-system-architecture--project-flow)
- [Prerequisites](#-prerequisites)
- [Getting Started & Setup Instructions](#-getting-started--setup-instructions)
  - [1. Clone Repository & Setup Virtual Environment](#1-clone-repository--setup-virtual-environment)
  - [2. Environment Configuration](#2-environment-configuration)
  - [3. Run Database Migrations](#3-run-database-migrations)
  - [4. Launch Application](#4-launch-application)
  - [5. Running with Docker Compose](#5-running-with-docker-compose)
- [API Documentation & Endpoints](#-api-documentation--endpoints)
- [Testing Guide](#-testing-guide)
- [Protecting Your Keys (.gitignore Guide)](#-protecting-your-keys-gitignore-guide)

---

## 💡 Overview & Concise Summary

### What is StockFlow?
**StockFlow** solves the core challenge of real-time inventory control and order processing for commercial operations. In traditional setups, stock levels often desynchronize when customer orders are placed or when shipments arrive from suppliers. StockFlow acts as the single source of truth for stock quantities, reservation status, supplier logistics, and customer orders.

### Who is it for?
The system natively supports two primary user roles:

1. **BUSINESS Role (Store Manager / Admin)**:
   - Manages product categories and inventory catalogs.
   - Monitors physical stock (`on_hand`), reserved stock, and available stock.
   - Receives automatic low-stock alerts when stock drops below threshold levels.
   - Manages suppliers and issues Purchase Orders (POs) for stock replenishment.
   - Processes stock receiving to automatically increment inventory levels upon delivery.
   - Reviews and updates all customer order statuses.

2. **CUSTOMER Role (Buyer)**:
   - Searches and browses active product listings with real-time stock availability.
   - Places orders with instant item reservation.
   - Tracks personal order statuses (pending, confirmed, shipped, delivered, cancelled).
   - Views personal order statistics and spending summaries.

---

## 🌟 Key Features

- **🔐 Robust Bearer Authentication & Session Control**: Powered by Supabase Auth with JWT Bearer tokens in request headers. Includes single session logout and multi-device session revocation.
- **⚡ Dynamic Stock Reservation**: Automatically reserves inventory when customer orders are placed and releases stock if orders are cancelled.
- **🚨 Low Stock Alerting**: Automated identification of products falling below defined reorder thresholds.
- **🏬 Supplier & Purchase Order Management**: Full supply chain workflow (`draft` → `pending` → `confirmed` → `received`), with itemized stock receiving.
- **🔍 Advanced Search & Filtering**: Fast multi-parameter product searching by name, category, and price range.
- **🐳 Containerized & Cloud Ready**: Complete Docker and `docker-compose` setup for standardized deployment.

---

## 🛠️ Technologies Used

| Category | Technology | Usage / Description |
| :--- | :--- | :--- |
| **Language** | Python 3.14+ | Modern Python runtime |
| **Framework** | FastAPI (v0.141+) | High-performance async REST API framework |
| **Package Manager** | uv (v0.12+) | Next-generation ultra-fast Python package manager |
| **Database** | PostgreSQL | Enterprise relational database storage |
| **ORM** | SQLAlchemy 2.0 | Asynchronous-compatible Object Relational Mapper |
| **DB Driver** | Psycopg 3 (`psycopg[binary]`) | Native PostgreSQL database adapter |
| **Migrations** | Alembic (v1.19+) | Database schema evolution & version control |
| **Authentication** | Supabase Auth (`supabase-py`) | Identity management & JWT Bearer token verification |
| **Data Validation** | Pydantic v2 & `pydantic-settings` | Schema enforcement & `.env` configuration management |
| **Security** | Passlib & Cryptography | Password hashing (`bcrypt`) & cryptographic utilities |
| **Containerization** | Docker & Docker Compose | Lightweight container orchestration |
| **Testing** | Pytest, Pytest-Asyncio, HTTPX | Automated unit & integration testing suite |

---

## 🏗️ System Architecture & Project Flow

### System Component Architecture

```
                                  +-----------------------+
                                  |     FastAPI Client    |
                                  | (Swagger UI / Mobile) |
                                  +-----------+-----------+
                                              |
                                     Authorization:
                                    Bearer <JWT_TOKEN>
                                              |
                                              v
+-----------------------------------------------------------------------------------+
|                                  StockFlow API                                    |
|                                                                                   |
|  +---------------------+   +---------------------+   +-------------------------+  |
|  |     Auth Router     |   |   Product Router    |   |    Inventory Router     |  |
|  |  (Signup/Login/Ref) |   |  (Catalog/Search)   |   |   (Stock/Low Alerts)    |  |
|  +----------+----------+   +----------+----------+   +------------+------------+  |
|             |                         |                           |               |
|  +----------v----------+   +----------v----------+   +------------v------------+  |
|  |    Orders Router    |   |   Supplier Router   |   | Purchase Orders Router  |  |
|  | (Place/Cancel/Track)|   | (Vendors Management)|   | (Supply Restock/Receive)|  |
|  +---------------------+   +---------------------+   +-------------------------+  |
|                                                                                   |
+----------------                          -----------------------------------------+
        |                                                 |
        v                                                 v
+---------------+                                 +---------------+
| Supabase Auth |                                 |  PostgreSQL   |
|  (User & JWT) |                                 |  (Database)   |
+---------------+                                 +---------------+
```

### Business vs. Customer Workflow

```
CUSTOMER FLOW:
  1. Signup / Login ──> Receive Bearer Access Token
  2. Browse Available Products (GET /products/available)
  3. Place Customer Order (POST /orders)
        └──> Inventory Quantity Reserved Increases
        └──> Inventory Quantity Available Decreases
  4. Track Order Status (GET /orders/my-orders)
  5. (Optional) Cancel Order (PATCH /orders/{id}/cancel) ──> Releases Reserved Stock

BUSINESS FLOW:
  1. Login as Business Role ──> Access Admin Endpoints
  2. Manage Categories & Products (POST /products, PUT /products/{id})
  3. Monitor Inventory & Low Stock Alerts (GET /inventory/low-stock)
  4. Create Supplier Profile (POST /suppliers)
  5. Issue Purchase Order to Supplier (POST /purchase-orders)
  6. Receive Stock Items (POST /purchase-orders/{id}/items/{item_id}/receive)
        └──> Physical Stock On-Hand Increases
        └──> Stock Available Increases
```

---

## 📋 Prerequisites

Ensure you have the following installed on your machine:
- **Python**: Version `3.14` or higher
- **uv**: Python package manager (`pip install uv` or via standalone installer)
- **PostgreSQL**: Local instance or remote database (e.g., Supabase PostgreSQL)
- **Docker & Docker Compose** *(Optional for containerized run)*

---

## 🚀 Getting Started & Setup Instructions

Follow these step-by-step instructions to get the project running locally.

### 1. Clone Repository & Setup Virtual Environment

```bash
# Clone the repository
git clone https://github.com/your-username/stock_flow.git
cd stock_flow

# Create virtual environment and sync dependencies using uv
uv sync
```

### 2. Environment Configuration

Create a `.env` file in the root directory by copying `.env.example`:

```bash
cp .env.example .env
```

Fill in your configuration details inside `.env`:

```env
# Database Settings
DATABASE_URL=postgresql://postgres:password@localhost:5432/stockflow_db
Test_DATABASE_URL=postgresql://postgres:password@localhost:5432/stockflow_test_db

# Security & App Settings
SECRET_KEY=your_super_secret_jwt_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
DEBUG=True

# Supabase Auth Credentials
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_SERVICE_KEY=your_supabase_service_role_key
SUPABASE_JWT_SECRET=your_supabase_jwt_secret
```

### 3. Run Database Migrations

Apply Alembic migrations to create all database tables:

```bash
# Run migrations using uv
uv run alembic upgrade head
```

### 4. Launch Application

Start the FastAPI development server:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API service will be accessible at: **`http://localhost:8000`**

### 5. Running with Docker Compose

To launch the full application in a containerized environment:

```bash
# Build and start container
docker-compose up --build -d

# View logs
docker-compose logs -f

# Stop containers
docker-compose down
```

---

## 📖 API Documentation & Endpoints

Once the application is running, interact with the API via the built-in documentation:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Summary of Key Endpoints

| Category | Method | Endpoint | Description | Access |
| :--- | :--- | :--- | :--- | :--- |
| **Auth** | `POST` | `/auth/signup` | Register new account | Public |
| **Auth** | `POST` | `/auth/login` | Authenticate & get Bearer tokens | Public |
| **Auth** | `POST` | `/auth/logout` | Revoke current session | Authenticated |
| **Auth** | `POST` | `/auth/logout-all-devices` | Revoke all active sessions | Authenticated |
| **Products** | `GET` | `/products/available` | Browse active catalog | Public / Customer |
| **Products** | `POST` | `/products` | Add new product | Business |
| **Products** | `GET` | `/products/search/by-name` | Fast name lookup | Public / Customer |
| **Products** | `GET` | `/products/search/advanced` | Multi-filter search | Public / Customer |
| **Inventory** | `GET` | `/inventory/product/{id}` | Stock levels overview | Business |
| **Inventory** | `GET` | `/inventory/low-stock` | Low stock alert report | Business |
| **Orders** | `POST` | `/orders` | Place new customer order | Customer |
| **Orders** | `GET` | `/orders/my-orders` | View order history | Customer |
| **Orders** | `PATCH` | `/orders/{id}/cancel` | Cancel order & release stock | Customer / Business |
| **Orders** | `PUT` | `/orders/{id}/status` | Update order progress | Business |
| **Suppliers**| `POST` | `/suppliers` | Register new supplier | Business |
| **Purchase PO**| `POST` | `/purchase-orders` | Issue restocking PO | Business |
| **Purchase PO**| `POST` | `/purchase-orders/{id}/items/{item_id}/receive` | Receive stock into inventory | Business |

---

## 🧪 Testing Guide

StockFlow includes automated tests using `pytest` and `httpx`.

```bash
# Run all tests
uv run pytest

# Run tests with stdout output
uv run pytest -s

# Run a specific test suite
uv run pytest tests/test_auth.py
```

---

## 🔐 Protecting Your Keys (.gitignore Guide)

To keep your sensitive API keys, Supabase credentials, database passwords, and secrets safe, **NEVER commit sensitive files to version control**.

### Recommended `.gitignore` File

Update your `.gitignore` file with the following patterns:

```gitignore
# Environment Configuration Files & Secrets
.env
.env.*
!.env.example
*.pem
*.key
*.cert
*.crt
*.p12
id_rsa
id_rsa.pub
service_account.json
secrets.yaml

# Virtual Environments
.venv/
venv/
env/
ENV/
.uv/

# Python Cache & Bytecode
__pycache__/
*.py[cod]
*$py.class

# Pytest & Coverage Caches
.pytest_cache/
.coverage
htmlcov/
.coverage.*

# IDE & OS Files
.vscode/
.idea/
*.swp
.DS_Store
Thumbs.db

# Database Files
*.sqlite3
*.db

# Docker Local Overrides
docker-compose.override.yml
```

> [!IMPORTANT]
> Always check `git status` before committing to make sure `.env` or any credential files are not tracked by Git. If `.env` was previously committed, remove it from git tracking using: `git rm --cached .env`.

---

## 📄 License

This project is licensed under the MIT License - see the project repository for details.
