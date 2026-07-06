"""
seed_users.py — run this ONCE to create all four departments and one
test login for each portal: Admin, Supply Chain, Pharmacy, Lab.

Usage:
    python seed_users.py

Safe to re-run — it skips any department or user that already exists,
so you can also use it later to top up a missing account without
duplicating anything.
"""

from app import app
from extensions import db
from models import User, Department

# ---- Edit these before running ----
DEFAULT_PASSWORD = "ChangeMe123!"   # same password for every seeded account, change after login

DEPARTMENTS = [
    {"name": "Administration", "is_supply_chain": False},
    {"name": "Supply Chain", "is_supply_chain": True},
    {"name": "Pharmacy", "is_supply_chain": False},
    {"name": "Lab", "is_supply_chain": False},
]

USERS = [
    {
        "name": "Mose",
        "email": "mm5134065@gmail.com",
        "password": DEFAULT_PASSWORD,
        "department": "Administration",
        "role": "admin",
        "is_admin": True,
        "login_as": "Admin",
    },
    {
        "name": "Supply Officer",
        "email": "mm5134065@gmail.com",
        "password": DEFAULT_PASSWORD,
        "department": "Supply Chain",
        "role": "supply_officer",
        "is_admin": False,
        "login_as": "Supply Chain",
    },
    {
        "name": "Pharmacy Staff",
        "email": "mm5134065@gmail.com",
        "password": DEFAULT_PASSWORD,
        "department": "Pharmacy",
        "role": "staff",
        "is_admin": False,
        "login_as": "Pharmacy",
    },
    {
        "name": "Lab Staff",
        "email": "lab@supplylink.test",
        "password": DEFAULT_PASSWORD,
        "department": "Lab",
        "role": "staff",
        "is_admin": False,
        "login_as": "Lab",
    },
]
# ------------------------------------


def run():
    with app.app_context():
        # 1. Departments — create any that don't already exist
        dept_lookup = {}
        for dept_data in DEPARTMENTS:
            dept = Department.query.filter_by(name=dept_data["name"]).first()
            if dept is None:
                dept = Department(name=dept_data["name"], is_supply_chain=dept_data["is_supply_chain"])
                db.session.add(dept)
                db.session.flush()  # assigns dept.id without a full commit
                print(f"Created department '{dept_data['name']}' (id={dept.id}).")
            else:
                print(f"Department '{dept_data['name']}' already exists (id={dept.id}) — skipping.")
            dept_lookup[dept_data["name"]] = dept

        db.session.commit()

        # 2. Users — one per portal
        created = []
        for user_data in USERS:
            email = user_data["email"].strip().lower()
            existing = User.query.filter_by(email=email).first()
            if existing:
                print(f"User {email} already exists (id={existing.id}) — skipping.")
                continue

            department = dept_lookup[user_data["department"]]
            user = User(
                name=user_data["name"],
                email=email,
                department_id=department.id,
                role=user_data["role"],
            )
            user.set_password(user_data["password"])
            db.session.add(user)
            created.append(user_data)

        db.session.commit()

        if created:
            print("\nCreated the following test logins:\n")
            for u in created:
                print(f"  Portal:   {u['login_as']}")
                print(f"  Email:    {u['email']}")
                print(f"  Password: {u['password']}")
                print()
        else:
            print("\nNo new users created — everything already existed.")

        print("Change these passwords after your first login on each portal.")


if __name__ == "__main__":
    run()