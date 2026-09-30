# StockFlow

## Smart Inventory & Procurement Platform

StockFlow is a web application that helps a business manage products, warehouses, suppliers, purchasing, and stock movement in one place.

In simple words, StockFlow helps a team answer four everyday questions:

1. What products do we have?
2. Where is each product stored?
3. What do we need to buy next?
4. Who approved or changed something?

It is designed for shops, distributors, warehouses, small manufacturers, and any organisation that buys and stores physical products.

---

## Why this website is useful

Many businesses manage stock using spreadsheets, messages, and separate emails. That often leads to:

- Incorrect stock numbers
- Products becoming unavailable without warning
- Purchase orders being created without approval
- Received goods not being added to inventory
- Difficult warehouse transfers
- No clear record of who changed the data

StockFlow provides one shared place for these activities. Everyone with permission sees the same information, while managers can review important actions and approvals.

---

## What StockFlow can do

### Dashboard

The Overview dashboard gives a quick picture of the business:

- Total stock value
- Total units in all warehouses
- Number of products
- Low-stock alerts
- Purchase orders waiting for approval
- Products that may need replenishment

### Products and categories

Users with permission can create, view, update, and delete products and categories.

A product can have a name, SKU, category, unit cost, and reorder point. The application protects important data; for example, a product with existing inventory cannot be removed accidentally.

### Warehouses and inventory

StockFlow tracks the same product separately in every warehouse. For each product and warehouse, it can show the quantity on hand, reserved quantity, available quantity, reorder point, and stock health.

```text
Available stock = Quantity on hand - Reserved quantity
```

This makes it easier to see what is actually available for use or sale.

### Suppliers

Supplier records include the supplier name, email, expected delivery time, and related purchase orders. Supplier lead time helps the team decide when to reorder.

### Purchase orders

Users can create purchase orders for a supplier and destination warehouse. Each order can contain multiple product lines with quantities and unit costs.

The normal order flow is:

```text
Create order → Add products → Submit for approval → Approve or reject → Receive goods
```

The main statuses are `PENDING_APPROVAL`, `APPROVED`, `REJECTED`, and `RECEIVED`.

### Goods receiving

When products arrive, an authorised user records the received quantity. StockFlow updates warehouse inventory, updates the purchase order, records an inventory transaction, and adds an audit entry. It also checks that the received quantity does not exceed the ordered quantity.

### Warehouse transfers

Stock can be moved from one warehouse to another. StockFlow checks that the source has enough available stock, decreases the source quantity, increases the destination quantity, and records both sides of the movement.

### Low-stock alerts

An item is considered low-stock when its available quantity is at or below its reorder point. StockFlow supports dashboard indicators, in-app alerts, alert resolution, and optional email notifications through SMTP.

### Demand forecasting

The Forecast page estimates how much of a product may be needed in the future. The current version uses a clear, trend-adjusted moving-average calculation based on recorded demand.

It provides estimated daily demand, forecast quantity for a selected period, historical data point count, and a suggested order quantity. The design can later be extended with seasonal machine-learning models, sales history, promotions, and supplier lead times.

### History and audit logs

StockFlow records important inventory movements such as receipts, transfers, and demand adjustments. Managers can also review audit logs showing actions such as product changes, purchase-order updates, goods receiving, transfers, and alert resolution.

This makes the system easier to understand, troubleshoot, and trust.

---

## User roles

StockFlow uses role-based permissions so every user gets the right level of access.

| Role | Typical access |
| --- | --- |
| Admin | Full access, user management, approvals, inventory, settings, and audit logs |
| Manager | Inventory operations, approvals, receiving, transfers, products, alerts, and audit logs |
| Procurement | Suppliers, purchase orders, order lines, and operational viewing |
| Viewer | Read-only access to dashboards, inventory, products, suppliers, orders, and forecasts |

The first account created in a new installation becomes the Admin account.

---

## How the website is normally used

### First-time setup

1. Start the backend and frontend, or start Docker Compose.
2. Open `http://localhost:5173`.
3. Open the **Platform** section.
4. Create the first Admin account.
5. Sign in.
6. Use **Seed demo data** if you want sample warehouses, products, suppliers, and inventory.

### Daily stock review

1. Open **Overview**.
2. Check total stock and low-stock alerts.
3. Open **Inventory** to check the affected product and warehouse.
4. Open **Forecast** when future demand needs to be estimated.

### Reordering products

1. Find a low-stock product.
2. Review its forecast and supplier lead time.
3. Create a purchase order.
4. Add the required product lines.
5. Submit the order for approval.
6. A Manager or Admin approves or rejects it.

### Receiving a delivery

1. Open the receiving area.
2. Select the purchase order and product line.
3. Enter the quantity that arrived.
4. Confirm the receipt.
5. Check the updated warehouse stock and transaction history.

### Transferring stock

1. Choose the product, source warehouse, and destination warehouse.
2. Enter the quantity.
3. Complete the transfer.
4. Review the transfer history.

---

## Technology used

| Technology | Why it is used |
| --- | --- |
| React | Builds the interactive dashboard, forms, tables, and workflow screens |
| Vite | Provides a fast frontend development server and production build |
| FastAPI | Provides the backend REST API, validation, and automatic API documentation |
| Python | Handles business rules, authentication, forecasting, and testing |
| SQLAlchemy | Connects Python application code to database tables |
| SQLite | Makes local development easy without installing a database server |
| PostgreSQL | Provides a reliable production database for multi-user workloads |
| Alembic | Tracks and applies database schema migrations |
| Docker Compose | Runs the database, API, and frontend together in repeatable services |
| Pytest | Tests the backend workflows and security behaviour |

FastAPI interactive documentation is available at `http://localhost:8000/docs` when the backend is running.

---

## Project structure

```text
stockflow/
├── backend/
│   ├── app/main.py                 FastAPI backend and business logic
│   ├── migrations/                 Alembic database migrations
│   ├── tests/                      Automated backend tests
│   ├── requirements.txt            Python dependencies
│   └── Dockerfile                  Backend container configuration
├── frontend/
│   ├── src/                        React screens and styles
│   ├── package.json                Frontend dependencies and scripts
│   └── Dockerfile                  Frontend container configuration
├── output/pdf/                     Shareable project explanation PDF
├── docker-compose.yml              Full local deployment configuration
└── README.md                       This guide
```

---

## Run locally without Docker

### Requirements

- Windows PowerShell
- Python 3.12 or later
- Node.js and npm

### Start the backend

Open one PowerShell window:

```powershell
cd "C:\Users\RAM\Desktop\Mycodex stuff\stockflow\backend"
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

### Start the frontend

Open a second PowerShell window:

```powershell
cd "C:\Users\RAM\Desktop\Mycodex stuff\stockflow\frontend"
npm install
npm run dev
```

Open the URL shown by Vite, normally `http://localhost:5173`.

Keep both PowerShell windows running while using the website.

The backend root URL `http://localhost:8000/` is not the website homepage. It may show `{"detail":"Not Found"}`, which is expected. Use the frontend at port `5173` or the API documentation at `/docs`.

---

## Run with Docker

Docker Desktop must be installed and running before starting the project.

From the project root:

```powershell
cd "C:\Users\RAM\Desktop\Mycodex stuff\stockflow"
docker compose up --build
```

Then open `http://localhost:5173`.

The services are:

- `web` — React frontend served by Nginx on port `5173`
- `api` — FastAPI backend on port `8000`
- `db` — PostgreSQL database inside the Docker network

Stop the services with `docker compose down`.

If Docker reports that it cannot connect to the Docker API, start Docker Desktop, wait until the engine is ready, and run the command again. If the website shows **Failed to fetch**, check the API with `docker compose logs api`.

---

## Database and environment settings

For local development, the API uses SQLite when `DATABASE_URL` is not set. The local database is stored as `stockflow.db` inside the backend directory.

For production, PostgreSQL is recommended. Use the example environment files and set real values through the environment or a secure secret manager.

Important backend settings include:

- `DATABASE_URL` — database connection string
- `STOCKFLOW_AUTH_SECRET` — secret used for authentication tokens
- `STOCKFLOW_CORS_ORIGINS` — allowed frontend origins
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, and `SMTP_PASSWORD` — optional email configuration
- `ALERT_RECIPIENT` — optional alert email address

The frontend uses `VITE_API_URL` to find the backend API.

Never commit passwords, tokens, database credentials, or SMTP credentials to the repository.

---

## Migrations and tests

Run database migrations from the backend directory:

```powershell
alembic upgrade head
```

Run backend tests:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -q
```

Build the frontend to check the production bundle:

```powershell
cd frontend
npm run build
```

The project includes tests for health checks, authentication, demo data, protected operations, purchase orders, receiving, transfers, alerts, and security headers.

---

## Security notes

The project includes password hashing, expiring signed authentication tokens, role-based permission checks, configurable CORS, security headers, quantity validation, audit logs, and environment-based credentials.

Before using the project in a real production environment, configure HTTPS, a strong secret manager, PostgreSQL backups, monitoring, dependency updates, and a proper deployment platform.

---

## Future improvements

The project can be expanded with seasonal machine-learning forecasting, barcode scanning, batch and expiry tracking, ERP integrations, supplier scorecards, multi-currency purchasing, value-based approval limits, scheduled forecasting jobs, mobile receiving, and advanced reports.

---

## License and contribution

This repository is public so people can read, learn from, run, and improve the project. Before using StockFlow in a commercial environment, add the license and contribution rules that match your intended use.

If you improve the project, document the change clearly, run the tests, and open a pull request with a short explanation of what changed and why.

---

## In one sentence

StockFlow gives a business one clear, controlled, and auditable place to manage inventory, warehouses, suppliers, purchasing, receiving, transfers, alerts, and demand planning.
