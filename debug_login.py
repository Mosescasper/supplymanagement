"""
debug_login.py — diagnoses "Invalid email or password" by checking each
step separately: does the user row exist, and does the password match.

Usage:
    python debug_login.py
"""

from app import app
from models import User

EMAIL_TO_CHECK = "mm5134065@gmail.com"
PASSWORD_TO_CHECK = "ChangeMe123!"


def run():
    with app.app_context():
        email = EMAIL_TO_CHECK.strip().lower()
        user = User.query.filter_by(email=email).first()

        if user is None:
            print(f"NO USER FOUND with email '{email}'.")
            print("-> The seed script didn't create this row, or the app")
            print("   is pointed at a different database than the script wrote to.")
            all_users = User.query.all()
            print(f"\nTotal users currently in this database: {len(all_users)}")
            for u in all_users:
                print(f"  id={u.id}  email={u.email}  is_admin={getattr(u, 'is_admin', '?')}")
            return

        print(f"User found: id={user.id}, name={user.name}, email={user.email}")
        print(f"is_admin={getattr(user, 'is_admin', '?')}")
        print(f"department_id={getattr(user, 'department_id', '?')}")
        print(f"password_hash starts with: {user.password_hash[:20]}...")

        try:
            matches = user.check_password(PASSWORD_TO_CHECK)
        except Exception as e:
            print(f"\ncheck_password() raised an error: {e!r}")
            return

        print(f"\ncheck_password('{PASSWORD_TO_CHECK}') -> {matches}")

        if matches:
            print("Password matches. Login should work — if it still fails in")
            print("the browser, the problem is in the login_as portal check")
            print("(check_portal_match), not authentication itself.")
        else:
            print("Password does NOT match the stored hash.")
            print("-> Either the seed script hashed a different password than")
            print("   you're typing, or set_password/check_password use")
            print("   mismatched hashing (e.g. one uses bcrypt, the other werkzeug).")


if __name__ == "__main__":
    run()
    