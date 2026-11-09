"""Departments with real sign-in and a real database: only an administrator sets one, and it takes effect on the next request."""
from backend.tests.test_api import env, seeded, sid  # noqa: F401
from backend.tests.test_database import pg, q  # noqa: F401
from backend.tests.test_database import pytestmark  # noqa: F401
from backend.tests.test_supabase_auth import H, app_, client_for, gt, me  # noqa: F401

A = sid("sample_a.pdf")


def uid_of(admin, email):
    return next(u["user_id"] for u in admin.get("/api/users").json()["users"] if u["email"] == email)


def test_an_administrator_puts_staff_in_a_department_and_it_is_enforced_at_once(app_):
    admin, sam = client_for(app_, "boss@company.com"), client_for(app_, "sam@company.com")
    uid = uid_of(admin, "sam@company.com")
    assert me(sam)["pending"] is True and me(sam)["department"] is None
    assert admin.put(f"/api/users/{uid}/role", json={"role": "staff", "department": "legal"}, headers=H).json()["department"] == "legal"
    m = me(sam)
    assert m["department"] == "legal" and "playbook" in m["features"] and "penalty" not in m["features"] and m["redacted"] is False
    assert sam.get(f"/api/contracts/{A}/playbook").status_code == 200
    assert sam.post(f"/api/contracts/{A}/penalty", json={}, headers=H).status_code == 403
    # moved to Finance: the same cookie now gets the opposite answers on the very next request
    admin.put(f"/api/users/{uid}/role", json={"role": "staff", "department": "finance"}, headers=H)
    assert sam.post(f"/api/contracts/{A}/penalty", json={}, headers=H).status_code == 200
    assert sam.get(f"/api/contracts/{A}/playbook").status_code == 403


def test_sales_staff_are_served_redacted_contracts_by_the_real_server(app_):
    admin, sam = client_for(app_, "boss@company.com"), client_for(app_, "sam@company.com")
    admin.put(f"/api/users/{uid_of(admin, 'sam@company.com')}/role", json={"role": "staff", "department": "sales"}, headers=H)
    c = sam.get(f"/api/contracts/{A}").json()
    assert c["contract"]["price"]["value"] is None and "price" in c["restricted_fields"] and me(sam)["redacted"] is True
    assert admin.get(f"/api/contracts/{A}").json()["contract"]["price"]["value"] == 2450000


def test_a_department_only_goes_with_the_staff_role_and_must_be_a_real_one(app_):
    admin = client_for(app_, "boss@company.com")
    client_for(app_, "sam@company.com")
    uid = uid_of(admin, "sam@company.com")
    for body in ({"role": "reviewer", "department": "legal"}, {"role": "buyer", "department": "sales"}, {"role": None, "department": "legal"},
                 {"role": "staff", "department": "marketing"}):
        assert admin.put(f"/api/users/{uid}/role", json=body, headers=H).status_code == 422, body
    assert q("select department from app_users where user_id = %s", (uid,))[0][0] is None


def test_changing_the_role_away_from_staff_clears_the_department(app_):
    admin = client_for(app_, "boss@company.com")
    client_for(app_, "sam@company.com")
    uid = uid_of(admin, "sam@company.com")
    admin.put(f"/api/users/{uid}/role", json={"role": "staff", "department": "finance"}, headers=H)
    assert next(u for u in admin.get("/api/users").json()["users"] if u["user_id"] == uid)["department"] == "finance"
    admin.put(f"/api/users/{uid}/role", json={"role": "reviewer"}, headers=H)
    assert next(u for u in admin.get("/api/users").json()["users"] if u["user_id"] == uid)["department"] is None
    assert q("select department from app_users where user_id = %s", (uid,))[0][0] is None


def test_nobody_can_choose_their_own_department(app_):
    admin, sam = client_for(app_, "boss@company.com"), client_for(app_, "sam@company.com")
    uid = uid_of(admin, "sam@company.com")
    admin.put(f"/api/users/{uid}/role", json={"role": "staff", "department": "sales"}, headers=H)
    assert sam.put(f"/api/users/{uid}/role", json={"role": "staff", "department": "finance"}, headers=H).status_code == 403
    assert me(sam)["department"] == "sales"


def test_administrators_and_reviewers_have_no_department(app_):
    admin, rita = client_for(app_, "boss@company.com"), client_for(app_, "rita@company.com")
    q("update app_users set department = 'sales' where email = 'boss@company.com'")        # even a stray value is ignored for an admin
    admin.put(f"/api/users/{uid_of(admin, 'rita@company.com')}/role", json={"role": "reviewer"}, headers=H)
    for c in (admin, rita):
        m = me(c)
        assert m["department"] is None and m["features"] is None
    assert admin.get(f"/api/contracts/{A}").json()["contract"]["price"]["value"] == 2450000
