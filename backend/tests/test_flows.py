"""End-to-end API tests against a real Postgres + Redis, using the simulated
Paystack provider. Run from the backend folder:

    TEST_DATABASE_URL=postgresql+psycopg://postgres@localhost/streixpei_test python -m unittest -v
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import re
import unittest
from datetime import timedelta

os.environ.setdefault("TEST_DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:5432/streixpei_test")
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ["ENVIRONMENT"] = "test"
os.environ["PAYMENTS_PROVIDER"] = "fake"
os.environ["MAIL_ENABLED"] = "false"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["ADMIN_EMAIL"] = "admin@streixpei.com"
os.environ["ADMIN_PASSWORD"] = "AdminPass123"
os.environ["FRONTEND_URL"] = "http://app.test"

import httpx  # noqa: E402
from sqlalchemy import select, text, update  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.money import FeeSchedule, naira_to_kobo  # noqa: E402
from app.core.redis import redis  # noqa: E402
from app.core.timeutil import next_payday, utcnow  # noqa: E402
from app.main import app  # noqa: E402
from app.models import OutboxEmail, PayrollItem, StaffMember, Subscription, Workgroup  # noqa: E402
from app.services import billing, mailer, payroll  # noqa: E402
from app.services.auth import ensure_admin  # noqa: E402
from app.services.paystack import FakePaystack, get_provider  # noqa: E402

PASSWORD = "Secret123"


class MoneyTests(unittest.TestCase):
    def test_naira_parsing(self):
        self.assertEqual(naira_to_kobo("1,250.50"), 125050)
        self.assertEqual(naira_to_kobo(100), 10000)
        self.assertEqual(naira_to_kobo("₦250,000"), 25_000_000)

    def test_transfer_fee_bands_and_stamp_duty(self):
        fees = FeeSchedule()
        self.assertEqual(fees.transfer_fee(5_000_00), 10_00)
        self.assertEqual(fees.transfer_fee(5_001_00), 25_00)
        self.assertEqual(fees.transfer_fee(9_999_00), 25_00)
        self.assertEqual(fees.transfer_fee(10_000_00), 75_00)  # 25 + 50 stamp duty
        self.assertEqual(fees.transfer_fee(50_001_00), 100_00)
        self.assertEqual(fees.commission(200_000_00), 1_000_00)  # 0.5%

    def test_gross_up_always_nets_target(self):
        fees = FeeSchedule()
        for net in [100_00, 2_400_00, 2_463_00, 2_500_00, 10_000_00, 131_000_00, 200_000_00, 5_000_000_00]:
            for channel in ("checkout", "dva"):
                gross = fees.gross_up(net, channel)
                fee = fees.collection_fee(gross, channel)
                self.assertGreaterEqual(gross - fee, net, (net, channel))
                self.assertLess((gross - 1) - fees.collection_fee(gross - 1, channel), net, (net, channel))
        self.assertEqual(fees.checkout_fee(1_000_000_00), 2_000_00)  # cap

    def test_fee_schedule_roundtrip(self):
        fees = FeeSchedule.from_dict({"commission_bps": 75, "transfer_bands": [{"up_to_kobo": None, "fee_kobo": 30_00}]})
        self.assertEqual(fees.commission_bps, 75)
        self.assertEqual(fees.transfer_fee(1_000_00), 30_00)


class ApiTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
            await conn.run_sync(Base.metadata.create_all)
        await redis.flushdb()
        async with SessionLocal() as session:
            await billing.seed_plans(session)
            await session.commit()
            await ensure_admin(session)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://api.test/api/v1")
        self.provider = get_provider()
        assert isinstance(self.provider, FakePaystack)

    async def asyncTearDown(self):
        await self.client.aclose()
        await engine.dispose()
        await redis.connection_pool.disconnect()

    # ------------------------------------------------------------ helpers
    async def last_email(self, to: str, template: str) -> OutboxEmail:
        async with SessionLocal() as session:
            row = (
                await session.execute(
                    select(OutboxEmail).where(OutboxEmail.to_email == to, OutboxEmail.template == template).order_by(OutboxEmail.created_at.desc())
                )
            ).scalars().first()
        self.assertIsNotNone(row, f"no {template} email to {to}")
        return row

    async def signup(self, email="ada@acme.ng", first="Ada", last="Okafor") -> dict:
        r = await self.client.post("/auth/register", json={"first_name": first, "last_name": last, "email": email, "phone": "08031234567",
                                                           "password": PASSWORD})
        self.assertEqual(r.status_code, 201, r.text)
        mail = await self.last_email(email, "verify_email")
        token = re.search(r"verify-email\?token=([^\"&\s<]+)", mail.html).group(1)
        r = await self.client.post("/auth/verify-email", json={"token": token})
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.client.headers["Authorization"] = f"Bearer {data['access_token']}"
        return data

    async def workgroup(self, headcount=5, **extra) -> dict:
        r = await self.client.post("/workgroups", json={"name": "Acme Logistics Ltd", "address": "12 Marina, Lagos", "headcount": headcount, **extra})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    async def register_staff(self, wg: dict, code: str, first: str, last: str, account: str, bank="058", email=None) -> httpx.Response:
        invite = wg["invite_code"]
        await self.provider.set_account_name(account, f"{first} {last}")
        r = await self.client.post(f"/join/{invite}/verify-id", json={"staff_code": code}, headers={"Authorization": ""})
        self.assertEqual(r.status_code, 200, r.text)
        return await self.client.post(
            f"/join/{invite}/register",
            json={"staff_code": code, "first_name": first, "last_name": last, "email": email or f"{first.lower()}@staff.ng",
                  "phone": "08030000000", "bank_code": bank, "account_number": account},
            headers={"Authorization": ""},
        )

    async def fund_and_complete(self, url: str, body: dict) -> dict:
        r = await self.client.post(url, json=body)
        self.assertEqual(r.status_code, 201, r.text)
        payment = r.json()
        r = await self.client.post(f"/dev/checkout/{payment['reference']}/complete")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "success")
        return r.json()

    async def integrity_ok(self):
        r = await self.client.post("/auth/login", json={"email": "admin@streixpei.com", "password": "AdminPass123"})
        token = r.json()["access_token"]
        r = await self.client.get("/admin/integrity", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"], r.json())


class AuthTests(ApiTestCase):
    async def test_register_verify_login_refresh_logout(self):
        await self.signup()
        r = await self.client.get("/auth/me")
        self.assertEqual(r.json()["email"], "ada@acme.ng")
        self.assertTrue(r.json()["verified"])

        self.client.headers.pop("Authorization")
        r = await self.client.post("/auth/login", json={"email": "ADA@acme.ng", "password": "wrongpass1"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["error"]["code"], "invalid_credentials")

        r = await self.client.post("/auth/login", json={"email": "ada@acme.ng", "password": PASSWORD, "remember_me": True})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("spx_rt", r.cookies)
        old_cookie = r.cookies["spx_rt"]

        r = await self.client.post("/auth/refresh")
        self.assertEqual(r.status_code, 200, r.text)
        access = r.json()["access_token"]
        # Rotated token is still accepted inside the grace window (two tabs)…
        r2 = await self.client.post("/auth/refresh", cookies={"spx_rt": old_cookie})
        self.assertEqual(r2.status_code, 200)

        r = await self.client.post("/auth/logout", headers={"Authorization": f"Bearer {access}"})
        self.assertEqual(r.status_code, 204)
        r = await self.client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
        self.assertEqual(r.status_code, 401)

    async def test_unverified_login_and_duplicate_email(self):
        r = await self.client.post("/auth/register", json={"first_name": "Bo", "last_name": "Ye", "email": "bo@x.ng", "password": PASSWORD})
        self.assertEqual(r.status_code, 201)
        r = await self.client.post("/auth/register", json={"first_name": "Bo", "last_name": "Ye", "email": "bo@x.ng", "password": PASSWORD})
        self.assertEqual(r.status_code, 409)
        r = await self.client.post("/auth/login", json={"email": "bo@x.ng", "password": PASSWORD})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["error"]["code"], "email_not_verified")
        r = await self.client.post("/auth/register", json={"first_name": "Bo", "last_name": "Ye", "email": "c@x.ng", "password": "short"})
        self.assertEqual(r.status_code, 422)
        self.assertIn("8 characters", r.json()["error"]["message"])

    async def test_password_reset_revokes_sessions(self):
        data = await self.signup()
        old_access = data["access_token"]
        r = await self.client.post("/auth/forgot-password", json={"email": "ada@acme.ng"})
        self.assertEqual(r.status_code, 200)
        mail = await self.last_email("ada@acme.ng", "password_reset")
        otp = re.search(r"code is (\d{6})", mail.text_body).group(1)
        r = await self.client.post("/auth/reset-password", json={"email": "ada@acme.ng", "otp": "000000", "password": "NewSecret456"})
        self.assertEqual(r.status_code, 400)
        r = await self.client.post("/auth/reset-password", json={"email": "ada@acme.ng", "otp": otp, "password": "NewSecret456"})
        self.assertEqual(r.status_code, 200, r.text)
        r = await self.client.get("/auth/me", headers={"Authorization": f"Bearer {old_access}"})
        self.assertEqual(r.status_code, 401)
        r = await self.client.post("/auth/login", json={"email": "ada@acme.ng", "password": "NewSecret456"})
        self.assertEqual(r.status_code, 200)


class StaffIdTests(ApiTestCase):
    async def test_generate_upload_and_capacity(self):
        await self.signup()
        wg = await self.workgroup(headcount=6)
        self.assertEqual(wg["subscription"]["status"], "trialing")
        self.assertEqual(wg["subscription"]["plan"]["code"], "small")
        wid = wg["id"]

        r = await self.client.post(f"/workgroups/{wid}/staff-ids/generate", json={"count": 3})
        self.assertEqual(r.status_code, 201, r.text)
        codes = r.json()["codes"]
        self.assertEqual(len(set(codes)), 3)
        for code in codes:
            self.assertRegex(code, r"^ALL-[0-9A-Z]{4}-[0-9A-Z]{4}$")

        csv_body = "Staff ID,Full name,Role,Salary\nEMP-001,Chidi Eze,Driver,\"150,000\"\nEMP-002,Amaka Obi,Driver,150000\nEMP-001,Dup,,\n,No id,,\nBAD=ID,x,,\n"
        r = await self.client.post(f"/workgroups/{wid}/staff-ids/upload", files={"file": ("ids.csv", csv_body.encode(), "text/csv")})
        self.assertEqual(r.status_code, 200, r.text)
        report = r.json()["report"]
        self.assertEqual(report["added_count"], 2)
        self.assertEqual(report["duplicates_in_file"], ["EMP-001"])
        self.assertEqual(len(report["invalid"]), 2)
        self.assertEqual(r.json()["summary"]["remaining"], 1)

        # Re-uploading the same IDs is idempotent (case-insensitive).
        r = await self.client.post(f"/workgroups/{wid}/staff-ids/paste", json={"text": "emp-001\nEMP-002"})
        self.assertEqual(r.json()["report"]["already_exists"], ["emp-001", "EMP-002"])

        # Over capacity → clear error with numbers.
        r = await self.client.post(f"/workgroups/{wid}/staff-ids/generate", json={"count": 2})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"]["code"], "seats_exceeded")
        self.assertEqual(r.json()["error"]["details"]["remaining"], 1)

        # Role created from the file and salary carried over.
        r = await self.client.get(f"/workgroups/{wid}/staff", params={"q": "chidi"})
        member = r.json()["items"][0]
        self.assertEqual(member["role_name"], "Driver")
        self.assertEqual(member["salary_kobo"], 150_000_00)

        r = await self.client.get(f"/workgroups/{wid}/staff-ids/export", params={"format": "xlsx"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content[:2] == b"PK")
        r = await self.client.get(f"/workgroups/{wid}/staff-ids/export")
        self.assertIn("EMP-001", r.text)

        xlsx = io.BytesIO()
        from openpyxl import Workbook

        wb = Workbook()
        wb.active.append(["Employee No", "Name"])
        wb.active.append([1001, "Tolu Ade"])
        wb.save(xlsx)
        r = await self.client.post(f"/workgroups/{wid}/staff-ids/upload", files={"file": ("ids.xlsx", xlsx.getvalue(), "application/octet-stream")})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["report"]["added"], ["1001"])

    async def test_other_manager_cannot_see_workgroup(self):
        await self.signup()
        wg = await self.workgroup()
        await self.signup(email="eve@evil.ng", first="Eve", last="Mallory")
        r = await self.client.get(f"/workgroups/{wg['id']}/staff")
        self.assertEqual(r.status_code, 404)
        r = await self.client.post(f"/workgroups/{wg['id']}/staff-ids/generate", json={"count": 1})
        self.assertEqual(r.status_code, 404)


class JoinTests(ApiTestCase):
    async def test_staff_onboarding_flow(self):
        await self.signup()
        wg = await self.workgroup(headcount=3)
        wid, invite = wg["id"], wg["invite_code"]
        await self.client.post(f"/workgroups/{wid}/staff-ids/paste", json={"text": "EMP-001,EMP-002"})

        anon = {"Authorization": ""}
        r = await self.client.get(f"/join/{invite}", headers=anon)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["accepting"])
        self.assertEqual(r.json()["workgroup"]["name"], "Acme Logistics Ltd")

        r = await self.client.post(f"/join/{invite}/verify-id", json={"staff_code": "EMP-999"}, headers=anon)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"]["code"], "staff_id_not_found")

        r = await self.client.post(f"/join/{invite}/resolve-account", json={"staff_code": "emp-001", "bank_code": "058",
                                                                          "account_number": "0001234567"}, headers=anon)
        self.assertEqual(r.status_code, 422)
        await self.provider.set_account_name("0123456789", "Chidi Eze")
        r = await self.client.post(f"/join/{invite}/resolve-account", json={"staff_code": "emp-001", "bank_code": "058",
                                                                          "account_number": "0123456789"}, headers=anon)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["account_name"], "CHIDI EZE")

        r = await self.register_staff(wg, "emp-001", "Chidi", "Eze", "0123456789")
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["staff_code"], "EMP-001")
        await self.last_email("chidi@staff.ng", "staff_welcome")

        r = await self.client.post(f"/join/{invite}/verify-id", json={"staff_code": "EMP-001"}, headers=anon)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"]["code"], "staff_id_taken")

        # Name mismatch is accepted but flagged for the manager.
        await self.provider.set_account_name("0222222222", "Somebody Else")
        r = await self.client.post(f"/join/{invite}/register", json={"staff_code": "EMP-002", "first_name": "Amaka", "last_name": "Obi",
                                                                   "email": "amaka@staff.ng", "bank_code": "058", "account_number": "0222222222"},
                                   headers=anon)
        self.assertEqual(r.status_code, 201)
        r = await self.client.get(f"/workgroups/{wid}/staff", params={"attention": "true"})
        self.assertEqual([m["name"] for m in r.json()["items"]], ["Amaka Obi"])

        # Paused link and rotated link.
        await self.client.post(f"/workgroups/{wid}/invite/toggle", json={"active": False})
        r = await self.client.post(f"/join/{invite}/verify-id", json={"staff_code": "EMP-002"}, headers=anon)
        self.assertEqual(r.status_code, 403)
        r = await self.client.post(f"/workgroups/{wid}/invite/rotate")
        self.assertNotEqual(r.json()["invite_code"], invite)
        r = await self.client.get(f"/join/{invite}", headers=anon)
        self.assertEqual(r.status_code, 404)

    async def test_registration_blocked_when_subscription_expired(self):
        await self.signup()
        wg = await self.workgroup(headcount=2)
        await self.client.post(f"/workgroups/{wg['id']}/staff-ids/generate", json={"count": 1})
        async with SessionLocal() as session:
            await session.execute(update(Subscription).values(status="expired"))
            await session.commit()
        r = await self.client.get(f"/join/{wg['invite_code']}", headers={"Authorization": ""})
        self.assertFalse(r.json()["accepting"])


class PayrollTests(ApiTestCase):
    async def _ready_workgroup(self) -> dict:
        await self.signup()
        wg = await self.workgroup(headcount=4)
        wid = wg["id"]
        r = await self.client.post(f"/workgroups/{wid}/roles", json={"name": "Drivers", "salary_kobo": 120_000_00})
        role = r.json()
        await self.client.post(f"/workgroups/{wid}/staff-ids/paste", json={"text": "S1,S2,S3"})
        for code, first, last, account in [("S1", "Chidi", "Eze", "0123456789"), ("S2", "Amaka", "Obi", "0223456789"),
                                           ("S3", "Bayo", "Ade", "0323456713")]:
            r = await self.register_staff(wg, code, first, last, account)
            self.assertEqual(r.status_code, 201, r.text)
        staff = (await self.client.get(f"/workgroups/{wid}/staff")).json()["items"]
        ids = {m["staff_code"]: m["id"] for m in staff}
        r = await self.client.post(f"/workgroups/{wid}/staff/bulk", json={"staff_ids": list(ids.values()), "role_id": role["id"]})
        self.assertEqual(r.json()["updated"], 3)
        r = await self.client.patch(f"/workgroups/{wid}/staff/{ids['S1']}", json={"salary_kobo": 250_000_00})
        self.assertEqual(r.json()["salary_kobo"], 250_000_00)
        wg["staff_ids"] = ids
        return wg

    async def test_manual_payroll_fund_disburse_partial_failure(self):
        wg = await self._ready_workgroup()
        wid = wg["id"]
        fees = FeeSchedule()
        r = await self.client.get(f"/workgroups/{wid}/payroll/preview")
        preview = r.json()
        self.assertEqual(len(preview["items"]), 3)
        salaries = 250_000_00 + 120_000_00 * 2
        expected_fees = fees.transfer_fee(250_000_00) + 2 * fees.transfer_fee(120_000_00)
        expected_commission = fees.commission(250_000_00) + 2 * fees.commission(120_000_00)
        self.assertEqual(preview["salaries_kobo"], salaries)
        self.assertEqual(preview["transfer_fees_kobo"], expected_fees)
        self.assertEqual(preview["commission_kobo"], expected_commission)
        self.assertEqual(preview["commission_kobo"], 2_450_00)  # 0.5% of ₦490,000

        r = await self.client.post(f"/workgroups/{wid}/payroll/runs", json={"note": "October"})
        self.assertEqual(r.status_code, 201, r.text)
        run = r.json()
        self.assertEqual(run["status"], "draft")
        r = await self.client.post(f"/workgroups/{wid}/payroll/runs/{run['id']}/submit")
        run = r.json()
        self.assertEqual(run["status"], "awaiting_funding")
        self.assertEqual(run["funding"]["shortfall_kobo"], run["total_kobo"])
        checkout = run["funding"]["checkout"]
        self.assertGreater(checkout["gross_kobo"], checkout["net_kobo"])

        r = await self.client.post(f"/workgroups/{wid}/payroll/runs/{run['id']}/disburse", json={"password": PASSWORD})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"]["code"], "insufficient_funds")

        await self.fund_and_complete(f"/workgroups/{wid}/payroll/runs/{run['id']}/fund", {"channel": "checkout"})
        r = await self.client.get(f"/workgroups/{wid}/payroll/runs/{run['id']}")
        self.assertEqual(r.json()["status"], "ready")
        await self.last_email("ada@acme.ng", "payroll_funded")
        await self.last_email("ada@acme.ng", "funding_received")

        r = await self.client.post(f"/workgroups/{wid}/payroll/runs/{run['id']}/disburse", json={"password": "nope"})
        self.assertEqual(r.status_code, 401)
        r = await self.client.post(f"/workgroups/{wid}/payroll/runs/{run['id']}/disburse", json={"password": PASSWORD})
        self.assertEqual(r.status_code, 200, r.text)
        done = r.json()
        self.assertEqual(done["status"], "partially_failed")  # account ending 13 fails in the simulator
        self.assertEqual(done["progress"], {"success": 2, "failed": 1, "processing": 0, "pending": 0, "total": 3})
        failed = next(i for i in done["items"] if i["status"] == "failed")
        self.assertTrue(failed["refunded"])
        self.assertEqual(done["refunded_kobo"], failed["amount_kobo"] + failed["fee_kobo"] + failed["commission_kobo"])
        self.assertEqual(done["paid_kobo"], 250_000_00 + 120_000_00)
        await self.last_email("chidi@staff.ng", "payslip")
        await self.last_email("ada@acme.ng", "payroll_completed")

        # Disbursing again is refused.
        r = await self.client.post(f"/workgroups/{wid}/payroll/runs/{run['id']}/disburse", json={"password": PASSWORD})
        self.assertEqual(r.status_code, 409)

        # Wallet ledger: funding credit, three debits, one refund; balance matches.
        r = await self.client.get(f"/workgroups/{wid}/wallet/entries")
        types = sorted(e["type"] for e in r.json()["items"])
        self.assertEqual(types, ["commission", "funding", "payroll", "refund", "transfer_fees"])
        await self.integrity_ok()

        # Retry creates a new draft with only the failed staff.
        r = await self.client.post(f"/workgroups/{wid}/payroll/runs/{run['id']}/retry")
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["staff_count"], 1)
        self.assertEqual(r.json()["trigger"], "retry")

        # Webhooks: signed reversal refunds a paid transfer exactly once.
        success_ref = next(i["reference"] for i in done["items"] if i["status"] == "success")
        payload = json.dumps({"event": "transfer.reversed", "data": {"id": 99, "reference": success_ref, "status": "reversed"}}).encode()
        sig = hmac.new(FakePaystack.WEBHOOK_SECRET.encode(), payload, hashlib.sha512).hexdigest()
        r = await self.client.post("/webhooks/paystack", content=payload, headers={"x-paystack-signature": "bad"})
        self.assertEqual(r.status_code, 401)
        for _ in range(2):
            r = await self.client.post("/webhooks/paystack", content=payload, headers={"x-paystack-signature": sig, "content-type": "application/json"})
            self.assertEqual(r.status_code, 200)
        r = await self.client.get(f"/workgroups/{wid}/payroll/runs/{run['id']}")
        self.assertEqual(sum(1 for i in r.json()["items"] if i["status"] == "reversed"), 1)
        r = await self.client.get(f"/workgroups/{wid}/wallet/entries", params={"type": "refund"})
        self.assertEqual(r.json()["total"], 2)
        await self.integrity_ok()

    async def test_wallet_covers_payroll_and_remove_item(self):
        wg = await self._ready_workgroup()
        wid = wg["id"]
        await self.fund_and_complete(f"/workgroups/{wid}/wallet/fund", {"amount_kobo": 1_000_000_00, "channel": "transfer"})
        r = await self.client.get(f"/workgroups/{wid}/wallet")
        self.assertEqual(r.json()["balance_kobo"], 1_000_000_00)
        r = await self.client.post(f"/workgroups/{wid}/payroll/runs", json={})
        run = r.json()
        item = next(i for i in run["items"] if i["staff_code"] == "S3")
        r = await self.client.delete(f"/workgroups/{wid}/payroll/runs/{run['id']}/items/{item['id']}")
        self.assertEqual(r.json()["staff_count"], 2)
        r = await self.client.post(f"/workgroups/{wid}/payroll/runs/{run['id']}/submit")
        self.assertEqual(r.json()["status"], "ready")
        r = await self.client.post(f"/workgroups/{wid}/payroll/runs/{run['id']}/disburse", json={"password": PASSWORD})
        self.assertEqual(r.json()["status"], "completed")
        balance = (await self.client.get(f"/workgroups/{wid}/wallet")).json()["balance_kobo"]
        self.assertEqual(balance, 1_000_000_00 - r.json()["total_kobo"])
        r = await self.client.get(f"/workgroups/{wid}/analytics")
        self.assertEqual(r.json()["totals"]["lifetime_paid_kobo"], 370_000_00)
        r = await self.client.get(f"/workgroups/{wid}/payroll/runs/{run['id']}/export")
        self.assertIn("Chidi Eze", r.text)
        await self.integrity_ok()

    async def test_automatic_payday(self):
        wg = await self._ready_workgroup()
        wid = wg["id"]
        r = await self.client.patch(f"/workgroups/{wid}", json={"payment_mode": "automatic", "payday_day": 28})
        self.assertEqual(r.json()["payment_mode"], "automatic")
        async with SessionLocal() as session:
            await session.execute(update(Workgroup).values(next_payday_at=utcnow() - timedelta(minutes=1)))
            await session.commit()
            stats = await payroll.run_due_paydays(session)
        self.assertEqual(stats["created"], 1)
        self.assertEqual(stats["awaiting"], 1)
        await self.last_email("ada@acme.ng", "payroll_shortfall")
        runs = (await self.client.get(f"/workgroups/{wid}/payroll/runs")).json()["items"]
        self.assertEqual(runs[0]["trigger"], "automatic")
        self.assertEqual(runs[0]["status"], "awaiting_funding")

        # Funding the wallet makes it ready; the automatic job disburses it.
        r = await self.client.post(f"/workgroups/{wid}/wallet/dva")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["account_number"].startswith("99"))
        r = await self.client.post(f"/dev/workgroups/{wid}/dva-transfer", json={"amount_kobo": 600_000_00})
        self.assertEqual(r.status_code, 200, r.text)
        async with SessionLocal() as session:
            disbursed = await payroll.disburse_ready_automatic(session)
            self.assertEqual(disbursed, 1)
            again = await payroll.run_due_paydays(session)
            self.assertEqual(again["created"], 0)
        runs = (await self.client.get(f"/workgroups/{wid}/payroll/runs")).json()["items"]
        self.assertEqual(runs[0]["status"], "partially_failed")
        async with SessionLocal() as session:
            wgrow = await session.get(Workgroup, wg["id"] and __import__("uuid").UUID(wid))
            self.assertGreater(wgrow.next_payday_at, utcnow())
        await self.integrity_ok()

    async def test_reconciler_settles_stuck_transfers(self):
        wg = await self._ready_workgroup()
        wid = wg["id"]
        await self.fund_and_complete(f"/workgroups/{wid}/wallet/fund", {"amount_kobo": 1_000_000_00, "channel": "checkout"})
        run = (await self.client.post(f"/workgroups/{wid}/payroll/runs", json={})).json()
        # Simulate a crash after the wallet debit: mark items queued without sending.
        async with SessionLocal() as session:
            from app.services import wallet as wallet_service
            import uuid as _uuid

            await payroll.submit(session, await session.get(Workgroup, _uuid.UUID(wid)), await payroll.get_run(session, _uuid.UUID(wid), _uuid.UUID(run["id"])), None)
            await session.commit()
            original = payroll.send_queued

            async def no_send(session, run_id):
                return None

            payroll.send_queued = no_send
            try:
                await payroll.disburse(session, _uuid.UUID(wid), _uuid.UUID(run["id"]), None)
            finally:
                payroll.send_queued = original
            await session.execute(update(PayrollItem).values(updated_at=utcnow() - timedelta(minutes=5)))
            await session.commit()
            await payroll.reconcile_transfers(session)
        r = await self.client.get(f"/workgroups/{wid}/payroll/runs/{run['id']}")
        self.assertEqual(r.json()["status"], "partially_failed")
        self.assertEqual(r.json()["progress"]["success"], 2)
        await self.integrity_ok()


class BillingTests(ApiTestCase):
    async def test_subscribe_with_wallet_and_prorated_seats(self):
        await self.signup()
        wg = await self.workgroup(headcount=10)
        wid = wg["id"]
        quote = (await self.client.get("/pricing/quote", params={"seats": 10})).json()
        self.assertEqual(quote["monthly_kobo"], 5_000_00 + 10 * 500_00)
        annual = (await self.client.get("/pricing/quote", params={"seats": 10, "cycle": "annual"})).json()
        self.assertEqual(annual["amount_kobo"], quote["monthly_kobo"] * 10)

        r = await self.client.post(f"/workgroups/{wid}/billing/subscribe", json={"seats": 10, "pay_with": "wallet"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"]["code"], "insufficient_funds")
        await self.fund_and_complete(f"/workgroups/{wid}/wallet/fund", {"amount_kobo": 100_000_00, "channel": "checkout"})
        r = await self.client.post(f"/workgroups/{wid}/billing/subscribe", json={"seats": 10, "pay_with": "wallet"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["paid"])
        billing_info = (await self.client.get(f"/workgroups/{wid}/billing")).json()
        self.assertEqual(billing_info["subscription"]["status"], "active")
        await self.last_email("ada@acme.ng", "invoice_paid")

        r = await self.client.post(f"/workgroups/{wid}/billing/seats", json={"seats": 30})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertFalse(r.json()["applied"])
        invoice = r.json()["invoice"]
        self.assertEqual(invoice["kind"], "seats")
        self.assertGreater(invoice["amount_kobo"], 0)
        r = await self.client.post(f"/workgroups/{wid}/billing/invoices/{invoice['id']}/pay", json={"pay_with": "checkout"})
        payment = r.json()["payment"]
        await self.client.post(f"/dev/checkout/{payment['reference']}/complete")
        billing_info = (await self.client.get(f"/workgroups/{wid}/billing")).json()
        self.assertEqual(billing_info["subscription"]["seats"], 30)
        self.assertEqual(billing_info["subscription"]["plan"]["code"], "medium")

        # Automatic renewal from the wallet.
        await self.fund_and_complete(f"/workgroups/{wid}/wallet/fund", {"amount_kobo": 100_000_00, "channel": "checkout"})
        async with SessionLocal() as session:
            sub = (await session.execute(select(Subscription))).scalar_one()
            sub.current_period_end = utcnow() - timedelta(minutes=1)
            await session.commit()
            stats = await billing.process_subscriptions(session)
        self.assertEqual(stats["renewed"], 1)
        billing_info = (await self.client.get(f"/workgroups/{wid}/billing")).json()
        self.assertEqual(billing_info["subscription"]["status"], "active")
        self.assertGreater(billing_info["subscription"]["days_left"], 25)
        self.assertEqual(billing_info["invoices"][0]["kind"], "renewal")
        self.assertEqual(billing_info["invoices"][0]["status"], "paid")
        await self.integrity_ok()

    async def test_trial_expiry_job(self):
        await self.signup()
        wg = await self.workgroup(headcount=3)
        async with SessionLocal() as session:
            await session.execute(update(Subscription).values(trial_ends_at=utcnow() - timedelta(hours=1)))
            await session.commit()
            stats = await billing.process_subscriptions(session)
        self.assertEqual(stats["expired"], 1)
        r = await self.client.post(f"/workgroups/{wg['id']}/payroll/runs", json={})
        self.assertEqual(r.status_code, 402)


class AssistantTests(ApiTestCase):
    async def test_basic_mode_actions(self):
        await self.signup()
        wg = await self.workgroup(headcount=5)
        wid = wg["id"]
        r = await self.client.post("/ai/chat", json={"message": "what's my wallet balance?", "workgroup_id": wid})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("₦0", r.json()["reply"])
        self.assertEqual(r.json()["mode"], "basic")

        r = await self.client.post("/ai/chat", json={"message": "generate 2 staff ids", "workgroup_id": wid,
                                                     "conversation_id": r.json()["conversation_id"]})
        actions = r.json()["actions"]
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["tool"], "generate_staff_ids")
        r = await self.client.post(f"/ai/actions/{actions[0]['id']}", json={"confirm": True})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["action"]["status"], "executed")
        summary = (await self.client.get(f"/workgroups/{wid}/staff-ids/summary")).json()
        self.assertEqual(summary["in_use"], 2)
        r = await self.client.post(f"/ai/actions/{actions[0]['id']}", json={"confirm": True})
        self.assertEqual(r.status_code, 409)

        code = (await self.client.get(f"/workgroups/{wid}/staff")).json()["items"][0]["staff_code"]
        conversation_id = (await self.client.get("/ai/conversation", params={"workgroup_id": wid})).json()["conversation_id"]
        r = await self.client.post("/ai/chat", json={"message": f"set salary of {code} to 150k", "workgroup_id": wid, "conversation_id": conversation_id})
        action = r.json()["actions"][0]
        self.assertIn("₦150,000", action["summary"])
        await self.client.post(f"/ai/actions/{action['id']}", json={"confirm": True})
        r = await self.client.get(f"/workgroups/{wid}/staff", params={"q": code})
        self.assertEqual(r.json()["items"][0]["salary_kobo"], 150_000_00)

        r = await self.client.get("/ai/conversation", params={"workgroup_id": wid})
        self.assertGreaterEqual(len(r.json()["messages"]), 4)

    async def test_claude_tool_loop(self):
        from app.core.config import settings
        from app.services.ai import agent

        await self.signup()
        wg = await self.workgroup(headcount=5)
        calls = []

        async def fake_claude(system, messages):
            calls.append(messages)
            if len(calls) == 1:
                return {"stop_reason": "tool_use", "content": [
                    {"type": "text", "text": "Let me check."},
                    {"type": "tool_use", "id": "t1", "name": "get_wallet", "input": {}},
                    {"type": "tool_use", "id": "t2", "name": "generate_staff_ids", "input": {"count": 3}},
                ]}
            assert messages[-1]["content"][0]["type"] == "tool_result"
            return {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Your balance is ₦0. Confirm the card to create 3 IDs."}]}

        original_call, original_key = agent._call_claude, settings.ANTHROPIC_API_KEY
        agent._call_claude = fake_claude
        object.__setattr__(settings, "ANTHROPIC_API_KEY", "test-key")
        try:
            r = await self.client.post("/ai/chat", json={"message": "balance and make 3 ids", "workgroup_id": wg["id"]})
        finally:
            agent._call_claude = original_call
            object.__setattr__(settings, "ANTHROPIC_API_KEY", original_key)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["mode"], "ai")
        self.assertEqual(len(body["actions"]), 1)
        self.assertIn("Generate 3", body["actions"][0]["summary"])
        self.assertIn("Confirm the card", body["reply"])
        self.assertEqual(len(calls), 2)


class WithdrawalTests(ApiTestCase):
    async def _wallet(self, wid: str) -> int:
        return (await self.client.get(f"/workgroups/{wid}/wallet")).json()["balance_kobo"]

    async def test_withdraw_success_failure_and_maximum(self):
        await self.signup()
        wg = await self.workgroup()
        wid = wg["id"]
        base = f"/workgroups/{wid}/wallet/withdrawals"
        await self.fund_and_complete(f"/workgroups/{wid}/wallet/fund", {"amount_kobo": 100_000_00, "channel": "checkout"})
        self.assertEqual(await self._wallet(wid), 100_000_00)

        q = (await self.client.get(base + "/quote", params={"amount_kobo": 50_000_00})).json()
        self.assertEqual(q["fee_kobo"], FeeSchedule().transfer_fee(50_000_00))
        self.assertTrue(q["enough"])
        await self.provider.set_account_name("0123456789", "Ada Okafor")
        r = await self.client.post(base + "/resolve", json={"bank_code": "058", "account_number": "0123456789"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["account_name"], "ADA OKAFOR")
        r = await self.client.post(base + "/resolve", json={"bank_code": "058", "account_number": "0001234567"})
        self.assertEqual(r.status_code, 422)

        body = {"amount_kobo": 50_000_00, "bank_code": "058", "account_number": "0123456789"}
        r = await self.client.post(base, json={**body, "password": "wrong-password1"})
        self.assertEqual(r.status_code, 401)
        r = await self.client.post(base, json={**body, "password": PASSWORD})
        self.assertEqual(r.status_code, 201, r.text)
        w = r.json()
        self.assertEqual(w["status"], "success")
        self.assertEqual(w["account_name"], "ADA OKAFOR")
        fee = w["fee_kobo"]
        self.assertEqual(await self._wallet(wid), 100_000_00 - 50_000_00 - fee)
        mail = await self.last_email("ada@acme.ng", "withdrawal_update")
        self.assertIn("Withdrawal complete", mail.subject)

        # Account deletion is blocked while money is in a wallet.
        r = await self.client.post("/users/me/delete", json={"password": PASSWORD})
        self.assertEqual(r.status_code, 409, r.text)
        self.assertEqual(r.json()["error"]["code"], "wallet_not_empty")

        # A failed transfer refunds the amount and the fee.
        before = await self._wallet(wid)
        r = await self.client.post(base, json={"amount_kobo": 10_000_00, "bank_code": "058", "account_number": "0123456713", "password": PASSWORD})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["status"], "failed")
        self.assertTrue(r.json()["refunded"])
        self.assertEqual(await self._wallet(wid), before)

        # More than the balance is refused without touching the wallet.
        r = await self.client.post(base, json={"amount_kobo": before, "bank_code": "058", "account_number": "0123456789", "password": PASSWORD})
        self.assertEqual(r.status_code, 409, r.text)
        self.assertEqual(r.json()["error"]["code"], "insufficient_funds")

        # The quoted maximum empties the wallet exactly.
        q = (await self.client.get(base + "/quote", params={"amount_kobo": 0})).json()
        r = await self.client.post(base, json={"amount_kobo": q["max_amount_kobo"], "bank_code": "058", "account_number": "0123456789", "password": PASSWORD})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(await self._wallet(wid), 0)
        listing = (await self.client.get(base)).json()
        self.assertEqual(listing["total"], 3)
        self.assertEqual([i["status"] for i in listing["items"]], ["success", "failed", "success"])
        await self.integrity_ok()

        # With an empty wallet the workgroup can be deleted.
        r = await self.client.post(f"/workgroups/{wid}/archive", json={"password": PASSWORD})
        self.assertEqual(r.status_code, 200, r.text)

    async def test_withdrawal_reversal_webhook_and_reconciler(self):
        await self.signup()
        wg = await self.workgroup()
        wid = wg["id"]
        base = f"/workgroups/{wid}/wallet/withdrawals"
        await self.fund_and_complete(f"/workgroups/{wid}/wallet/fund", {"amount_kobo": 80_000_00, "channel": "checkout"})
        r = await self.client.post(base, json={"amount_kobo": 20_000_00, "bank_code": "058", "account_number": "0123456789", "password": PASSWORD})
        w = r.json()
        after = await self._wallet(wid)

        payload = json.dumps({"event": "transfer.reversed", "data": {"id": 7, "reference": w["reference"], "status": "reversed"}}).encode()
        sig = hmac.new(FakePaystack.WEBHOOK_SECRET.encode(), payload, hashlib.sha512).hexdigest()
        for _ in range(2):
            r = await self.client.post("/webhooks/paystack", content=payload, headers={"x-paystack-signature": sig, "content-type": "application/json"})
            self.assertEqual(r.status_code, 200)
        self.assertEqual(await self._wallet(wid), after + w["total_kobo"])
        listing = (await self.client.get(base)).json()
        self.assertEqual(listing["items"][0]["status"], "reversed")

        # A withdrawal left "queued" by a crash is sent by the reconciler, once.
        from app.models import Withdrawal
        from app.services import withdrawals

        r = await self.client.post(base, json={"amount_kobo": 5_000_00, "bank_code": "058", "account_number": "0123456789", "password": PASSWORD})
        stuck_id = r.json()["id"]
        async with SessionLocal() as session:
            await session.execute(
                update(Withdrawal).where(Withdrawal.id == stuck_id).values(status="queued", transfer_code=None, updated_at=utcnow() - timedelta(minutes=5))
            )
            await session.commit()
        await redis.delete(self.provider._key("trf", r.json()["reference"]))
        async with SessionLocal() as session:
            self.assertEqual(await withdrawals.reconcile(session), 1)
        listing = (await self.client.get(base)).json()
        self.assertEqual(next(i for i in listing["items"] if i["id"] == stuck_id)["status"], "success")
        await self.integrity_ok()


class AdminTests(ApiTestCase):
    async def test_admin_overview_and_settings(self):
        await self.signup()
        r = await self.client.get("/admin/overview")
        self.assertEqual(r.status_code, 403)
        self.client.headers.pop("Authorization")
        r = await self.client.post("/auth/login", json={"email": "admin@streixpei.com", "password": "AdminPass123"})
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        r = await self.client.get("/admin/overview")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["counts"]["managers"], 1)
        r = await self.client.patch("/admin/settings", json={"commission_bps": 75, "trial_days": 7})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["fees"]["commission_bps"], 75)
        r = await self.client.get("/meta")
        self.assertEqual(r.json()["commission_label"], "0.75%")
        r = await self.client.patch("/admin/plans/small", json={"per_staff_kobo": 600_00})
        self.assertEqual(r.json()["per_staff_kobo"], 600_00)
        users = (await self.client.get("/admin/users")).json()["items"]
        manager = next(u for u in users if u["role"] == "manager")
        r = await self.client.patch(f"/admin/users/{manager['id']}", json={"status": "suspended"})
        self.assertEqual(r.json()["status"], "suspended")


class EmailTests(ApiTestCase):
    async def test_templates_render_and_outbox_delivers(self):
        await self.signup()
        async with SessionLocal() as session:
            sent = await mailer.deliver_pending(session)
        self.assertGreaterEqual(sent, 2)
        mail = await self.last_email("ada@acme.ng", "welcome")
        self.assertEqual(mail.status, "sent")
        self.assertIn("STREIXPEI", mail.html)
        self.assertIn("Streixcorp", mail.text_body)
        for template, ctx in [
            ("payslip", {"staff_name": "Ada", "company": "Acme", "period": "October 2026", "amount": 150_000_00, "staff_code": "X",
                         "account_name": "ADA", "bank_name": "GTBank", "account_masked": "••••1234", "reference": "r", "paid_at": "now"}),
            ("payroll_shortfall", {"name": "A", "company": "Acme", "period": "Oct", "total": 1, "balance": 0, "shortfall": 1, "staff_count": 1,
                                   "automatic": True, "dva_account_number": "991", "dva_bank_name": "Wema", "dva_account_name": "X",
                                   "transfer_amount": 1, "link": "x"}),
            ("subscription_notice", {"name": "A", "company": "Acme", "headline": "Trial ended", "body": "your trial ended.", "link": "x"}),
        ]:
            subject, html, text_body = mailer.render(template, ctx)
            self.assertTrue(subject)
            self.assertNotIn("{{", html)
            self.assertTrue(text_body.strip())



class SmokeTests(ApiTestCase):
    """Touches every remaining endpoint and background job once."""

    async def test_everything_else(self):
        await self.signup()
        wg = await self.workgroup(headcount=4)
        wid = wg["id"]
        await self.client.post(f"/workgroups/{wid}/staff-ids/paste", json={"text": "A1,A2"})
        r = await self.register_staff(wg, "A1", "Chidi", "Eze", "0123456789")
        self.assertEqual(r.status_code, 201)
        staff = (await self.client.get(f"/workgroups/{wid}/staff")).json()["items"]
        member = next(m for m in staff if m["staff_code"] == "A1")
        pending = next(m for m in staff if m["staff_code"] == "A2")
        await self.client.patch(f"/workgroups/{wid}/staff/{member['id']}", json={"salary_kobo": 80_000_00})

        for path in [
            "/workgroups", f"/workgroups/{wid}", f"/workgroups/{wid}/overview", f"/workgroups/{wid}/activity", f"/workgroups/{wid}/analytics",
            f"/workgroups/{wid}/staff/{member['id']}", f"/workgroups/{wid}/roles", f"/workgroups/{wid}/staff-ids/summary",
            f"/workgroups/{wid}/staff/export", f"/workgroups/{wid}/staff/export?format=xlsx", f"/workgroups/{wid}/wallet",
            f"/workgroups/{wid}/wallet/quote?amount_kobo=5000000", f"/workgroups/{wid}/wallet/entries", f"/workgroups/{wid}/wallet/entries/export",
            f"/workgroups/{wid}/payments", f"/workgroups/{wid}/payroll/runs", f"/workgroups/{wid}/billing", "/plans", "/banks", "/meta",
            "/notifications", "/notifications/unread-count", "/ai/conversation", f"/join/{wg['invite_code']}",
        ]:
            r = await self.client.get(path)
            self.assertEqual(r.status_code, 200, f"{path}: {r.text[:300]}")

        r = await self.client.post(f"/workgroups/{wid}/invite/email", json={"emails": ["a@x.ng", "b@x.ng"], "message": "Please register"})
        self.assertEqual(r.json()["sent"], 2)
        r = await self.client.post(f"/workgroups/{wid}/staff/{member['id']}/bank", json={"bank_code": "044", "account_number": "0999999999"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["bank_name"], "Access Bank")
        r = await self.client.post(f"/workgroups/{wid}/staff", json={"first_name": "Tolu", "last_name": "Ade", "bank_code": "057",
                                                                   "account_number": "0888888888", "salary_kobo": 90_000_00})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["status"], "registered")
        r = await self.client.post(f"/workgroups/{wid}/staff/{member['id']}/reset")
        self.assertEqual(r.json()["status"], "pending")
        r = await self.client.delete(f"/workgroups/{wid}/staff/{pending['id']}")
        self.assertEqual(r.json()["outcome"], "deleted")
        r = await self.client.post(f"/workgroups/{wid}/staff-ids/delete-unclaimed", json={})
        self.assertEqual(r.json()["deleted"], 1)
        role = (await self.client.post(f"/workgroups/{wid}/roles", json={"name": "Ops", "salary_kobo": 50_000_00})).json()
        r = await self.client.patch(f"/workgroups/{wid}/roles/{role['id']}", json={"salary_kobo": 55_000_00})
        self.assertEqual(r.json()["salary_kobo"], 55_000_00)
        r = await self.client.delete(f"/workgroups/{wid}/roles/{role['id']}")
        self.assertEqual(r.status_code, 204)

        notes = (await self.client.get("/notifications")).json()
        self.assertGreater(notes["total"], 0)
        r = await self.client.post(f"/notifications/{notes['items'][0]['id']}/read")
        self.assertTrue(r.json()["read"])
        await self.client.post("/notifications/read-all")

        r = await self.client.patch("/users/me", json={"first_name": "Adaeze", "preferences": {"dark_mode": True, "evil": 1}})
        self.assertEqual(r.json()["first_name"], "Adaeze")
        self.assertEqual(r.json()["preferences"], {"dark_mode": True})
        r = await self.client.post("/users/me/password", json={"current_password": PASSWORD, "new_password": "Another789"})
        self.assertEqual(r.status_code, 200)

        # Background jobs run cleanly.
        async with SessionLocal() as session:
            await session.execute(update(Workgroup).values(next_payday_at=utcnow() + timedelta(days=2)))
            await session.commit()
            self.assertEqual(await payroll.send_payday_reminders(session), 1)
            self.assertEqual(await payroll.send_payday_reminders(session), 0)
            await payroll.reconcile_transfers(session)
            from app.services import auth as auth_service, payments as payment_service

            await payment_service.reconcile_pending(session)
            await auth_service.purge_deleted_users(session)
            sub = (await session.execute(select(Subscription))).scalar_one()
            sub.status, sub.current_period_start = "active", utcnow() - timedelta(days=31)
            sub.current_period_end = utcnow() - timedelta(minutes=5)
            await session.commit()
            stats = await billing.process_subscriptions(session)
            self.assertEqual(stats["past_due"], 1)  # wallet empty → past due
            self.assertEqual(await mailer.deliver_pending(session) > 0, True)

        # Admin listings
        self.client.headers.pop("Authorization")
        r = await self.client.post("/auth/login", json={"email": "admin@streixpei.com", "password": "AdminPass123"})
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        for path in ["/admin/overview", "/admin/users", "/admin/workgroups", "/admin/payroll-runs", "/admin/plans", "/admin/settings",
                     "/admin/revenue/export", "/admin/integrity"]:
            r = await self.client.get(path)
            self.assertEqual(r.status_code, 200, f"{path}: {r.text[:300]}")
        r = await self.client.post("/admin/emails/retry")
        self.assertEqual(r.status_code, 200)

    async def test_account_deletion_and_restore(self):
        await self.signup()
        r = await self.client.post("/users/me/delete", json={"password": PASSWORD})
        self.assertEqual(r.status_code, 200)
        r = await self.client.get("/auth/me")
        self.assertEqual(r.status_code, 401)
        self.client.headers.pop("Authorization")
        r = await self.client.post("/auth/login", json={"email": "ada@acme.ng", "password": PASSWORD})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["user"]["status"], "active")

    async def test_dva_webhook_credits_wallet(self):
        await self.signup()
        wg = await self.workgroup(headcount=2)
        dva = (await self.client.post(f"/workgroups/{wg['id']}/wallet/dva")).json()
        async with SessionLocal() as session:
            customer = (await session.execute(select(Workgroup.paystack_customer_code))).scalar_one()
        payload = json.dumps({"event": "charge.success", "data": {"id": 555, "reference": "T123456789", "amount": 50_000_00, "currency": "NGN",
                                                                  "channel": "dedicated_nuban", "status": "success", "fees": 300_00,
                                                                  "customer": {"customer_code": customer}}}).encode()
        sig = hmac.new(FakePaystack.WEBHOOK_SECRET.encode(), payload, hashlib.sha512).hexdigest()
        r = await self.client.post("/webhooks/paystack", content=payload, headers={"x-paystack-signature": sig})
        self.assertEqual(r.status_code, 200)
        wallet = (await self.client.get(f"/workgroups/{wg['id']}/wallet")).json()
        self.assertEqual(wallet["balance_kobo"], 49_700_00)
        self.assertEqual(wallet["dva"]["account_number"], dva["account_number"])
        await self.integrity_ok()


if __name__ == "__main__":
    unittest.main()
