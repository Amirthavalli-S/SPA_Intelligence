"""Who may do what (RBAC), decided in the database.

Roles: staff (read everything), reviewer (staff + change data), buyer (ask about their own contract only).
Admins (ADMIN_EMAILS) can also manage users. Nobody can grant themselves anything: a role is a row an admin set, or
(for buyers) the existence of a buyer assignment for the person's CONFIRMED email.
"""
from __future__ import annotations

import os
import threading
import time

from app import buyers, db, departments

ROLES = ("staff", "reviewer", "buyer")
DEPARTMENTS = departments.DEPARTMENTS
_cache: dict[str, tuple[float, str | None, str | None]] = {}
_lock = threading.Lock()
TTL = 10.0                                   # seconds: a role change reaches a signed-in user within this window at most


class UserError(ValueError):
    pass


def admin_emails() -> set[str]:
    return {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").replace(";", ",").split(",") if e.strip()}


def is_admin(email: str) -> bool:
    return (email or "").strip().lower() in admin_emails()


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def touch(user_id: str, email: str, name: str = "") -> None:
    """Record a sign-in. Creates the row (role null) the first time; never changes an existing role."""
    with db.connection() as cx:
        cx.execute(
            "insert into app_users (user_id, email, name, last_login_at) values (%s,%s,%s, now()) "
            "on conflict (user_id) do update set email = excluded.email, last_login_at = now(), "
            "name = case when excluded.name <> '' then excluded.name else app_users.name end",
            (user_id, email.strip(), name[:80]))


def _lookup(user_id: str, email: str) -> tuple[str | None, str | None]:
    """(role, department). An explicit role wins; otherwise a buyer assignment for the email makes a buyer. Cached for TTL seconds."""
    key = f"{user_id}|{email.lower()}"
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < TTL:
            return hit[1], hit[2]
    role, dept = None, None
    with db.connection() as cx:
        row = cx.execute("select role, department from app_users where user_id = %s", (user_id,)).fetchone()
    if row and row[0]:
        role = row[0]
        dept = row[1] if role == "staff" else None             # a department only means something for staff
    elif _has_assignment(email):
        role = "buyer"
    with _lock:
        _cache[key] = (now, role, dept)
    return role, dept


def role_for(user_id: str, email: str) -> str | None:
    """staff | reviewer | buyer | None (pending)."""
    return _lookup(user_id, email)[0]


def department_for(user_id: str, email: str) -> str | None:
    """The department of a STAFF account (set by an administrator), else None."""
    return _lookup(user_id, email)[1]


def _has_assignment(email: str) -> bool:
    try:
        ident = buyers.normalize_identity(email)
    except buyers.BuyerError:
        return False
    with db.connection() as cx:
        return cx.execute("select 1 from buyer_assignments where identity = %s and active limit 1", (ident,)).fetchone() is not None


PRINCIPAL_ROLES = {"staff": "Spa.Staff", "reviewer": "Spa.Reviewer", "buyer": "Spa.Buyer"}


def principal_roles(user_id: str, email: str) -> set[str]:
    out: set[str] = set()
    if is_admin(email):
        out |= {"Spa.Reviewer", "Spa.Admin"}
    r = role_for(user_id, email)
    if r:
        out.add(PRINCIPAL_ROLES[r])
    return out


def list_users() -> list[dict]:
    with db.connection() as cx:
        rows = cx.execute("select user_id, email, name, role, created_at, last_login_at, updated_by, department from app_users "
                          "order by (role is null) desc, lower(email)").fetchall()
        linked = {r[0] for r in cx.execute("select identity from buyer_assignments where active").fetchall()}
    return [{"user_id": r[0], "email": r[1], "name": r[2], "role": r[3], "admin": is_admin(r[1]),
             "via_assignment": r[3] is None and r[1].strip().lower() in linked,     # a buyer by contract link, with no role row
             "created_at": r[4].isoformat(timespec="seconds"),
             "last_login_at": r[5].isoformat(timespec="seconds") if r[5] else None, "updated_by": r[6],
             "department": r[7] if r[3] == "staff" else None} for r in rows]


def set_role(user_id: str, role: str | None, by: str, department: str | None = None) -> dict:
    """Give a person a role. A department can only go with the staff role; any other role clears it."""
    if role is not None and role not in ROLES:
        raise UserError(f"Role must be one of: {', '.join(ROLES)}, or none.")
    if department is not None and department not in DEPARTMENTS:
        raise UserError(f"Department must be one of: {', '.join(DEPARTMENTS)}, or none.")
    if department is not None and role != "staff":
        raise UserError("A department can only be set together with the staff role.")
    with db.connection() as cx:
        row = cx.execute("update app_users set role = %s, department = %s, updated_by = %s where user_id = %s returning user_id, email",
                         (role, department, by[:80], user_id)).fetchone()
    if row is None:
        raise UserError("User not found.")
    clear_cache()
    return {"user_id": row[0], "email": row[1], "role": role, "department": department}
