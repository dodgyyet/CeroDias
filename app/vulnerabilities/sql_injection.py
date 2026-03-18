"""SQL Injection vulnerability challenges"""
import random
from app.models.vulnerability import Vulnerability


class SQLInjection(Vulnerability):
    """SQL Injection vulnerability implementation"""

    def __init__(self):
        super().__init__('sql_injection')
        self.config = {
            'table_names': ['users', 'products', 'orders', 'employees', 'accounts'],
            'column_names': ['password', 'api_key', 'secret', 'token', 'email'],
            'easy_payloads': [
                "' OR '1'='1",
                "' OR 1=1--",
                "admin' --",
                "' OR 'a'='a",
            ],
            'medium_payloads': [
                "' UNION SELECT username, password FROM users--",
                "' UNION SELECT id, api_key FROM employees--",
                "1' UNION SELECT NULL, password FROM users WHERE '1'='1",
            ],
        }

    def generate_vulnerable_code(self, params):
        """Generate vulnerable code snippet"""
        table = params.get('table_name', random.choice(self.config['table_names']))
        column = params.get('column_name', random.choice(self.config['column_names']))
        difficulty = params.get('difficulty', 'Easy')

        if difficulty == 'Easy':
            code = self._generate_easy_code(table, column)
        else:
            code = self._generate_medium_code(table, column)

        return code

    @staticmethod
    def _generate_easy_code(table, column):
        """Generate easy difficulty vulnerable code"""
        return f'''def authenticate(username):
    query = f"SELECT * FROM {table} WHERE username = '{{username}}'"
    # Execute query against database
    result = db.execute(query)
    return result[0] if result else None

# Frontend login form:
# <input name="username" type="text">
# Sends username parameter to authenticate() function'''

    @staticmethod
    def _generate_medium_code(table, column):
        """Generate medium difficulty vulnerable code"""
        return f'''def search_users(search_term):
    # Note: single quotes are escaped, but concatenation is still vulnerable
    query = f"SELECT id, name, {column} FROM {table} WHERE name LIKE '%{{search_term}}%'"
    result = db.execute(query)
    return result

# The escaping of single quotes is bypassed by using UNION SELECT
# Try: ' UNION SELECT id, name, {column} FROM {table}--'''

    def validate_flag(self, submitted_flag, correct_flag):
        """Check if submitted flag is correct"""
        # Flag class handles variants, just compare strings
        return submitted_flag.strip() == correct_flag.strip()

    def get_randomization_config(self):
        """Return randomization options"""
        return {
            'table_names': self.config['table_names'],
            'column_names': self.config['column_names'],
        }

    def get_exploit_hint(self):
        """Return hint for exploiting this vulnerability"""
        return (
            "SQL Injection happens when user input is directly concatenated into SQL queries. "
            "Try breaking out of the string context using quotes and boolean operators."
        )

    @staticmethod
    def get_difficulty_info(difficulty):
        """Get info about difficulty level"""
        if difficulty == 'Easy':
            return {
                'description': 'Simple injection with direct string concatenation',
                'example_payload': "' OR '1'='1",
                'base_points': 100,
            }
        else:
            return {
                'description': 'Injection with quote escaping, requires UNION SELECT',
                'example_payload': "' UNION SELECT NULL, NULL--",
                'base_points': 150,
            }
