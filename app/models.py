from flask_login import UserMixin
from .database import get_connection

class User(UserMixin):
    def __init__(self, user_id, full_name, email, role, account_status):
        self.id = str(user_id)
        self.full_name = full_name
        self.email = email
        self.role = role
        self.account_status = account_status

    @staticmethod
    def get_by_id(user_id):
        connection = get_connection()
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """SELECT user_id, full_name, email, role, account_status
                   FROM users WHERE user_id = %s""",
                (user_id,),
            )
            row = cursor.fetchone()
            cursor.close()
            if not row or row["account_status"] != "ACTIVE":
                return None
            return User(row["user_id"], row["full_name"], row["email"],
                        row["role"], row["account_status"])
        finally:
            connection.close()
