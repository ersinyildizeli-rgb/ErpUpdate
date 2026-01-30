# System Tests

This project now includes a test suite to ensure system stability and security.

## Prerequisites
Ensure `pytest` is installed:
```bash
pip install pytest
```

## Running Tests
To run all tests:
```bash
python -m pytest tests
```

To run a specific test file:
```bash
python -m pytest tests/test_auth.py
```

## What is Tested?
1.  **Authentication (test_auth.py):**
    *   Verifies login/logout.
    *   **Security:** Checks that 'admin' can access settings (`/ayarlar`).
    *   **Security:** Checks that non-admin users ('personel' role) are BLOCKED from accessing settings.
2.  **Payroll Logic (test_payroll.py):**
    *   Verifies the `resolve_multiplier` logic to ensure company settings override old default values correctly.
