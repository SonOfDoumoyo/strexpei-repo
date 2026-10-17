# STREIXPEI

Payroll for Nigerian businesses, by Streixcorp. A finance manager creates a workgroup, gives every staff member an ID, and shares one link or QR code. Staff register their own bank details without creating an account. The manager funds the wallet once, and Streixpei pays everyone through Paystack, either when the manager says or automatically on payday.

```
backend/    FastAPI API, Postgres, Redis, background jobs, email templates
frontend/   React 19 + Vite + Tailwind web app
```

## How it works

1. **Create a workgroup.** The manager names the business, sets how many staff they pay, and picks a payday.
2. **Staff IDs.** The manager either uploads the IDs they already use (CSV, Excel or pasted) or lets Streixpei generate them. Generated IDs look like `ACM-7K3M-Q9TD` and are unique across the whole platform. Each ID is stored once per workgroup, and it is the only way to register. The IDs can be exported as CSV or Excel.
3. **Onboarding link + QR code.** Staff open the link and enter their staff ID. If the ID is not on the list, it is refused. They then add their name, email and bank account. The account is resolved with the bank, and a mismatch between the name and the account holder is flagged to the manager. When they press done, they are on the payroll. No sign-up is involved.
4. **Fund the wallet.** There are three ways:
   - by card or bank through Paystack checkout
   - by "pay with transfer"
   - by a permanent account number for the workgroup (a Paystack dedicated virtual account)

   Paystack's collection fee is shown up front and added on top, so the wallet receives exactly the intended amount.
5. **Pay.** Payroll is a reviewed run: draft → funded → disbursed.
   - The total is salaries + Paystack transfer fees + the Streixpei service fee (0.5%).
   - Disbursing needs the manager's password.
   - Transfers go out in Paystack bulk batches.
   - Each staff member gets an email payslip.
   - Failed or reversed transfers are refunded to the wallet: salary, fee and service fee.
   - Automatic workgroups run on payday by themselves. If the wallet is short, the manager is emailed the exact shortfall.
6. **Withdraw.** The manager can send wallet money back to any verified bank account. This needs their password and costs only Paystack's transfer fee.

## How Streixpei makes money

- **Subscription per workgroup, priced by staff count.** The plan is chosen automatically from the number of staff seats.

  | Plan   | Staff  | Base / month | Per staff / month |
  |--------|--------|--------------|-------------------|
  | Small  | 1–25   | ₦5,000       | ₦500              |
  | Medium | 26–150 | ₦15,000      | ₦400              |
  | Large  | 151+   | ₦50,000      | ₦300              |

  - Annual billing is charged at 10 months.
  - New workgroups get a 14-day free trial.
  - Seat upgrades are prorated.
  - Renewal is paid from the wallet. If the wallet can't cover it, there is a 3-day grace period.
- **Service fee: 0.5% of every salary actually disbursed.** Refunded transfers refund the fee too.
- **Paystack's charges are passed through,** so your margin is never eaten by them:
  - Collections: 1.5% + ₦100 (the ₦100 is waived under ₦2,500), capped at ₦2,000.
  - Dedicated account deposits: 1%, capped at ₦300.
  - Transfers: ₦10 / ₦25 / ₦50 depending on the amount, plus ₦50 stamp duty from ₦10,000.

Every price, fee and plan can be edited from the admin console (**Pricing & fees**) without a deploy. The admin Revenue page shows subscriptions and service fees by month. It also checks that every wallet balance equals its ledger.

## SPI, the assistant

SPI answers questions and takes actions in the open workgroup. It can:

- prepare payroll
- set salaries and roles
- generate staff IDs
- create funding links
- change the payday
- open or rotate the onboarding link
- disburse

Anything that changes data appears as a confirmation card first. Disbursing also asks for the password. SPI uses Claude through the Anthropic API when `ANTHROPIC_API_KEY` is set. Without a key it falls back to a basic command mode. Monthly request quotas follow the plan.

## Run it locally

Requirements: Python 3.12+, Node 20+, PostgreSQL 14+ and Redis 6+. Docker can provide all of these instead.

### With Docker

```bash
cp backend/.env.example backend/.env
# For a quick local try-out set PAYMENTS_PROVIDER=fake, MAIL_ENABLED=false,
# a JWT_SECRET_KEY, and ADMIN_EMAIL / ADMIN_PASSWORD.
docker compose up --build
```

- Web app: http://localhost:5173
- API docs: http://localhost:8000/docs

### Without Docker

```bash
# API
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill it in
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Web app (new terminal)
cd frontend
cp .env.example .env            # VITE_API_BASE_URL=http://localhost:8000/api/v1
npm install
npm run dev
```

With `PAYMENTS_PROVIDER=fake`, no real money moves:

- Checkout opens a local test page where you complete or cancel the payment.
- Account numbers ending in `13` fail transfers. Use them to see refunds.
- Account numbers starting with `000` can't be resolved.
- The fake provider is refused in production.

### Tests

```bash
cd backend
createdb streixpei_test
TEST_DATABASE_URL=postgresql+psycopg://postgres@localhost/streixpei_test python -m unittest -v tests.test_flows
```

The tests run against real Postgres and Redis (Redis database 15). They cover:

- sign-up and sessions
- staff IDs and seat limits
- the join form
- manual and automatic payroll, including partial failures, reversals and crash recovery
- billing
- withdrawals
- SPI
- the admin console
- email rendering
- tenant isolation

## Going live

1. **Database and Redis.** Create a managed Postgres and Redis and set `DATABASE_URL` and `REDIS_URL`.
2. **Required environment.** Set:
   - `ENVIRONMENT=production`
   - a random `JWT_SECRET_KEY` (48+ characters)
   - `FRONTEND_URL`, `API_URL` and `CORS_ORIGINS`
   - `ADMIN_EMAIL` and `ADMIN_PASSWORD`

   The API refuses to start with unsafe production settings.
3. **Email.** Gmail works with an [App Password](https://myaccount.google.com/apppasswords) for low volume. Use a transactional provider as you grow. Emails go through an outbox table, so nothing is lost if SMTP is down.
4. **Paystack.** In the dashboard:
   - Use your **live** secret key.
   - Set the webhook URL to `https://<api-domain>/api/v1/webhooks/paystack`.
   - Turn off OTP for transfers.
   - Settle collections to the Paystack balance.
   - Ask Paystack support to enable dedicated virtual accounts, then set `PAYSTACK_DVA_ENABLED=true`.
5. **Cookies.** If the web app and API are on different sites, set `COOKIE_SAMESITE=none` (this needs HTTPS). On a shared parent domain, keep `lax`.
6. **Deploy the API.** Use `backend/Dockerfile`. It runs `alembic upgrade head`, then uvicorn with `WEB_CONCURRENCY` workers. Background jobs run inside the API and use Redis locks, so several instances are safe.
7. **Deploy the web app.**
   - On Vercel or Netlify: `vercel.json` and `netlify.toml` are included. Set `VITE_API_BASE_URL`.
   - Or use `frontend/Dockerfile`, which builds and serves with nginx.

## Upgrading from the old code

The database schema is new and is created by `alembic upgrade head`. Start with a fresh database.
