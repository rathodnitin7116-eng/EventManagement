"""
Create the first administrator account for the Event Management System.

Run from the project root with the project's virtual environment active:
    python create_admin.py

This script does not expose admin registration through the website.
"""
import re
from getpass import getpass

from werkzeug.security import generate_password_hash
from mysql.connector import IntegrityError

from app.database import get_connection


def main():
    print("=== Create Event Management System Administrator ===")
    full_name = input("Administrator full name: ").strip()
    email = input("Administrator email: ").strip().lower()

    if not full_name:
        print("Name cannot be empty.")
        return

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        print("Please enter a valid email address.")
        return

    password = getpass("New admin password (minimum 12 characters): ")
    confirmation = getpass("Confirm password: ")

    if len(password) < 12:
        print("Password must contain at least 12 characters.")
        return
    if password != confirmation:
        print("Passwords do not match.")
        return

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT user_id, role FROM users WHERE email = %s", (email,))
        existing = cursor.fetchone()

        if existing:
            print("An account with this email already exists. No changes were made.")
            print("Use a different email, or manage the existing account deliberately.")
            return

        cursor.execute(
            """
            INSERT INTO users (full_name, email, password_hash, role, account_status)
            VALUES (%s, %s, %s, 'ADMIN', 'ACTIVE')
            """,
            (full_name, email, generate_password_hash(password)),
        )
        connection.commit()
        print(f"Administrator account created successfully (user_id={cursor.lastrowid}).")
        print("You can now log in at /login using this email and password.")
    except IntegrityError:
        connection.rollback()
        print("That email is already registered. No changes were made.")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
