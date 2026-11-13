# ShopZone — Full-Stack E-Commerce Platform

[![CI](https://github.com/Ishani-Shree/ShopZone/actions/workflows/ci.yml/badge.svg)](https://github.com/Ishani-Shree/ShopZone/actions/workflows/ci.yml)

A production-style e-commerce web app built with **Node.js + Express**, **PostgreSQL**, and **React + Vite**. Features 92 real products across 14 categories, JWT auth, a simulated payment gateway, order management, and real-time location-based currency conversion.

---

## Screenshots

### Product Dashboard
![Dashboard](visuals/Dashboard.png)

### Shopping Cart
![Cart](visuals/Cart_Details.png)

### Secure Checkout — Card & Cash on Delivery
![Payment](visuals/Payment_Opt.png)

### Order Confirmation & Detail
![Order Detail](visuals/Ord_confirm.png)

### Order List with Status Badges
![Orders](visuals/Order-list-detail.png)



---

## Features

- **92 products** across 14 categories (Smartphones, Laptops, Audio, Gaming, Fashion, Books, and more)
- **JWT authentication** — register, login, protected routes, role-based access (user / admin)
- **Shopping cart** — add, remove, live item count badge in navbar
- **Payment simulation** — animated card form (Visa / Mastercard / Rupay / UPI) + Cash on Delivery option
- **Order management** — place, confirm, and cancel orders with stock restoration
- **Order status badges** — Awaiting Payment · Confirmed · Cancelled
- **Real-time currency** — IP geolocation detects country → live exchange rate → `Intl.NumberFormat` display (defaults to ₹ INR)
- **Admin panel** — add / edit / delete products
- **Single start command** — `npm run dev` at root boots both servers via `concurrently` + `nodemon`

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Node.js, Express.js 5, CommonJS |
| Database | PostgreSQL via `pg` connection pool |
| Auth | JWT (1-day expiry) + bcryptjs (salt 10) |
| Frontend | React 18, Vite 5, Tailwind CSS 3 |
| Routing | React Router v6, protected routes |
| HTTP | Axios + request interceptor (Bearer token) |
| CORS | Vite dev proxy `/api` → `localhost:5000` |
| Currency | ipwho.is (geolocation) + open.er-api.com (exchange rates) |
| Images | loremflickr.com (keyword + lock param for determinism) |
| Dev tools | concurrently, nodemon |

---

## Project Structure

```
ecommerce-platform/
├── backend/
│   ├── src/
│   │   ├── config/
│   │   │   ├── db.js              # PostgreSQL pool
│   │   │   ├── schema.sql         # DB schema (5 tables)
│   │   │   └── seed.js            # 92 products seeder
│   │   ├── controllers/
│   │   │   ├── authController.js
│   │   │   ├── productController.js
│   │   │   ├── cartController.js
│   │   │   └── orderController.js
│   │   ├── middleware/
│   │   │   ├── authMiddleware.js  # JWT protect
│   │   │   └── adminMiddleware.js
│   │   ├── routes/
│   │   │   ├── authRoutes.js
│   │   │   ├── productRoutes.js
│   │   │   ├── cartRoutes.js
│   │   │   └── orderRoutes.js
│   │   └── server.js
│   ├── .env
│   └── package.json
├── frontend/
│   ├── src/
│   │   ├── api/index.js           # Axios instance + all API calls
│   │   ├── context/
│   │   │   ├── AuthContext.jsx
│   │   │   ├── CartContext.jsx
│   │   │   └── CurrencyContext.jsx
│   │   ├── pages/
│   │   │   ├── Home.jsx
│   │   │   ├── ProductDetail.jsx
│   │   │   ├── Cart.jsx
│   │   │   ├── PaymentPage.jsx
│   │   │   ├── Orders.jsx
│   │   │   ├── OrderDetail.jsx
│   │   │   ├── Login.jsx
│   │   │   ├── Register.jsx
│   │   │   └── AdminPanel.jsx
│   │   ├── components/
│   │   │   ├── Navbar.jsx
│   │   │   ├── ProductCard.jsx
│   │   │   ├── ProtectedRoute.jsx
│   │   │   └── Toast.jsx
│   │   ├── App.jsx
│   │   └── main.jsx
│   └── package.json
├── visuals/                       # Screenshots
├── package.json                   # Root — concurrently dev script
└── README.md
```

---

## Run locally

### Prerequisites

- Node.js 20+
- Docker (for PostgreSQL 16) — or your own PostgreSQL 14+

### 1 — Clone & install

```bash
git clone https://github.com/Ishani-Shree/ShopZone.git
cd ShopZone
npm install            # root: concurrently
npm run install:all    # backend + frontend
```

### 2 — Start PostgreSQL

```bash
docker compose up -d
```

This starts Postgres 16 in a container named `shopzone-db`, with data kept in
the `shopzone-pgdata` volume and a healthcheck. It is published on host port
**5433**, so it won't clash with a natively installed PostgreSQL on 5432.
`docker compose down` stops it; `docker compose down -v` also deletes the data.

### 3 — Environment variables

```bash
cp backend/.env.example backend/.env
```

The defaults in `.env.example` match the Docker database. Set `JWT_SECRET` to
any long random string, e.g.
`node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"`.

### 4 — Create the schema and seed products

```bash
cd backend
npm run db:setup
```

`db:setup` creates the database if needed, applies `schema.sql` and inserts 92
products across 14 categories. Use `npm run db:schema` to apply only the
schema; it's idempotent and also upgrades an existing database. Note that
seeding replaces all products.

### 5 — Start both servers

```bash
cd ..        # back to root
npm run dev
```

- Backend (nodemon): `http://localhost:5000`
- Frontend (Vite): `http://localhost:3000` (proxies `/api` to the backend)

### Tests

```bash
docker compose up -d
cd backend
npm test
```

The API tests use Jest + supertest against a real PostgreSQL database
(`shopzone_test` on the Docker container, created automatically), not mocks.
Every test starts from empty tables. The suite never reads `backend/.env`, and
it refuses to run against any database whose name doesn't end in `_test`.

---

## Correctness & performance

### Order placement under retries and concurrency

Checkout runs in a single transaction: create the order, decrement stock, insert
the items, clear the cart. Two mechanisms make it safe under load:

- **Atomic stock decrement:** `UPDATE products SET stock = stock - $1 WHERE id = $2 AND stock >= $1`.
  If no row is updated, the whole order rolls back with `409`. A
  `CHECK (stock >= 0)` constraint backs this up at the database level.
- **Idempotency keys:** an `Idempotency-Key` header is stored on the order
  under `UNIQUE (user_id, idempotency_key)`. A retry finds the existing order and
  returns it instead of creating another. The frontend sends one key per
  checkout attempt.

Measured on the same machine, running the same scenarios against the code
before and after the fix:

| Scenario | Before | After |
|---|---|---|
| 10 concurrent buyers, stock 9 (5 rounds) | 10 orders, stock **-1**, every round | 9 orders, stock **0**, every round |
| One user, 5 concurrent checkouts | 5 orders | 1 order |
| Same `Idempotency-Key` sent 5× concurrently | — (header ignored) | 1 order; the other 4 get it back with `200` |
| Cart quantity `-5` | accepted; order total −500.00, stock 10 → 15 | rejected with `400` |

The test suite has **51 API tests**. On the original code, 22 of them fail.
The concurrency tests passed 10 out of 10 consecutive runs.

### Load test

`npm run bench` (autocannon, 10 connections). Each run makes 20 s of
`GET /api/products?page=1&limit=12` against the 92 seeded products, then
5,000 real checkouts. Each checkout comes from a different user with one item
in their cart and a unique `Idempotency-Key`. All 5,000 buy the **same
product**, the worst case, because every transaction has to wait for the same
row lock. p50/p95 are computed from every individual response time.

Three consecutive runs:

| Endpoint | Run | Requests | Req/s | p50 (ms) | p95 (ms) | Errors |
|---|---|---|---|---|---|---|
| `GET /api/products` | 1 | 51,635 | 2580.5 | 3.83 | 5.34 | 0% |
| | 2 | 52,803 | 2638.8 | 3.80 | 5.34 | 0% |
| | 3 | 55,245 | 2759.5 | 3.63 | 5.51 | 0% |
| `POST /api/orders/checkout` | 1 | 5,000 | 160.9 | 42.93 | 160.64 | 0% |
| | 2 | 5,000 | 171.9 | 41.58 | 142.77 | 0% |
| | 3 | 5,000 | 191.9 | 37.42 | 125.62 | 0% |

After every run, the database check matched exactly: 5,000 orders for 5,000
`201` responses, and stock went from 1,000,000 to 995,000.

**Setup:** Intel Core i7-12700H (14 cores / 20 threads), 15.6 GB RAM,
Windows 11, Node.js v22.15.0, PostgreSQL 16.15 in Docker Desktop (WSL 2).
The load generator, the API (a single Node process) and the database all
ran on the same laptop, so these numbers describe this machine, not a
production deployment.

---

## API Reference

### Auth
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login → returns JWT |

### Products
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/products?page=1&limit=200` | List products |
| GET | `/api/products/search?q=iphone` | Search |
| GET | `/api/products/:id` | Product detail |
| POST | `/api/products` | Create (admin) |
| PUT | `/api/products/:id` | Update (admin) |
| DELETE | `/api/products/:id` | Delete (admin) |

### Cart
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/cart` | Get cart items |
| POST | `/api/cart/add` | Add to cart (`quantity` 1–1000, default 1) |
| PUT | `/api/cart/update/:id` | Change an item's quantity |
| DELETE | `/api/cart/remove/:id` | Remove item |

### Orders
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/orders/checkout` | Create order (`pending_payment`). Optional `Idempotency-Key` header: a retry with the same key returns the original order (`200`, `Idempotent-Replayed: true`) instead of creating another. `201` created · `400` empty cart · `409` insufficient stock |
| POST | `/api/orders/pay` | Confirm payment → `confirmed` |
| POST | `/api/orders/cancel` | Cancel order + restore stock |
| GET | `/api/orders` | List user orders |
| GET | `/api/orders/:id` | Order detail |

---

## Database Schema

```sql
users        — id, name, email, password, role
products     — id, name, description, price, stock, category, image_url
cart_items   — id, user_id, product_id, quantity
orders       — id, user_id, total_price, status, created_at, idempotency_key
order_items  — id, order_id, product_id, quantity, price
```

Constraints that protect correctness:
`UNIQUE (orders.user_id, orders.idempotency_key)` · `CHECK (products.stock >= 0)` ·
`CHECK (cart_items.quantity > 0)` · `CHECK (order_items.quantity > 0)`

**Order statuses:** `pending_payment` · `confirmed` · `cancelled`

---

## Payment Flow

```
Cart → Place Order → Order created (pending_payment)
     → /payment/:id
          ├── Pay with Card  (2.8s simulated processing) → confirmed
          └── Cash on Delivery (1.2s)                   → confirmed

Order Detail / Orders List
     └── Cancel Order → cancelled + stock restored
```



