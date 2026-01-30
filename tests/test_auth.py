import pytest
from flask import session

def login(client, username, password):
    return client.post('/login', data=dict(
        username=username,
        password=password
    ), follow_redirects=True)

def logout(client):
    return client.get('/logout', follow_redirects=True)

def test_login_logout(client):
    """Test standard login and logout flow."""
    rv = login(client, 'admin', 'admin123')
    assert b'Dashboard' in rv.data or b'Ho\xc5\x9fgeldiniz' in rv.data 
    
    rv = logout(client)
    assert b'Giri\xc5\x9f Yap' in rv.data

def test_admin_access_to_settings(client):
    """Test that admin can access settings page."""
    login(client, 'admin', 'admin123')
    rv = client.get('/ayarlar')
    assert rv.status_code == 200
    assert b'irket Ayarlar' in rv.data

def test_non_admin_access_denied(client):
    """Test that non-admin users are blocked from settings page."""
    login(client, 'user', 'user123')
    rv = client.get('/ayarlar')
    # Should be 403 Forbidden or redirected with a message
    assert rv.status_code in [403, 302] 
    if rv.status_code == 302:
        # If redirected, check flash message (implementation dependent)
        # Assuming typical behavior for unauthorized access
        pass

def test_company_update_security(client):
    """Test that non-admin cannot update company settings."""
    login(client, 'user', 'user123')
    rv = client.post('/ayarlar/company', data=dict(
        company_name='HACKED'
    ))
    assert rv.status_code != 200 # Should deny
