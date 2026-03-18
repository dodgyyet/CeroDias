"""Tests for vulnerability implementations"""
import pytest
from app.vulnerabilities.sql_injection import SQLInjection


class TestSQLInjection:
    """Test SQL Injection vulnerability"""

    def test_sql_injection_creation(self):
        """Test SQLInjection object creation"""
        sqli = SQLInjection()
        assert sqli.type == 'sql_injection'

    def test_generate_vulnerable_code_easy(self):
        """Test easy difficulty code generation"""
        sqli = SQLInjection()
        params = {
            'table_name': 'users',
            'column_name': 'password',
            'difficulty': 'Easy'
        }
        code = sqli.generate_vulnerable_code(params)
        assert 'def authenticate' in code
        assert 'users' in code
        assert 'SELECT' in code

    def test_generate_vulnerable_code_medium(self):
        """Test medium difficulty code generation"""
        sqli = SQLInjection()
        params = {
            'table_name': 'products',
            'column_name': 'api_key',
            'difficulty': 'Medium'
        }
        code = sqli.generate_vulnerable_code(params)
        assert 'def search_users' in code
        assert 'products' in code
        assert 'api_key' in code

    def test_get_randomization_config(self):
        """Test randomization configuration"""
        sqli = SQLInjection()
        config = sqli.get_randomization_config()
        assert 'table_names' in config
        assert 'column_names' in config
        assert len(config['table_names']) > 0
        assert len(config['column_names']) > 0

    def test_get_exploit_hint(self):
        """Test exploit hint generation"""
        sqli = SQLInjection()
        hint = sqli.get_exploit_hint()
        assert isinstance(hint, str)
        assert 'SQL' in hint

    def test_difficulty_info_easy(self):
        """Test easy difficulty info"""
        info = SQLInjection.get_difficulty_info('Easy')
        assert info['base_points'] == 100
        assert 'OR' in info['example_payload']

    def test_difficulty_info_medium(self):
        """Test medium difficulty info"""
        info = SQLInjection.get_difficulty_info('Medium')
        assert info['base_points'] == 150
        assert 'UNION' in info['example_payload']
