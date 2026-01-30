import pytest
from services import resolve_multiplier

def test_resolve_multiplier_logic():
    """
    Test the logic for resolving overtime multipliers.
    Old default values (1.5, 2.0, 2.5, 3.0) should be overridden by the current setting
    if they differ, but manual/non-standard values should be preserved.
    """
    
    # CASE 1: Saved value is None (standard behavior)
    # Should use the current setting
    assert resolve_multiplier(None, 2.0) == 2.0
    
    # CASE 2: Saved value matches standard old defaults (e.g. 1.5) but setting is different (e.g. 2.0)
    # Should UPDATE to the setting (consistency fix)
    assert resolve_multiplier(1.5, 2.0) == 2.0
    
    # CASE 3: Saved value matches standard old defaults (e.g. 2.0) but setting is different (e.g. 3.0)
    assert resolve_multiplier(2.0, 3.0) == 3.0
    
    # CASE 4: Saved value is exactly the same as setting
    assert resolve_multiplier(2.0, 2.0) == 2.0
    
    # CASE 5: Saved value is a MANUAL override (non-standard value, e.g. 5.5)
    # Should PRESERVE manually entered value
    assert resolve_multiplier(5.5, 2.0) == 5.5
    
    # CASE 6: Weekday standard multiplier update
    # Old was 1.5, Setting changed to 1.25
    assert resolve_multiplier(1.5, 1.25) == 1.25

def test_payroll_calculation_integration(app):
    """
    Integration test for payroll calculation logic could go here.
    (Requires more setup of Puantaj/Personel models)
    """
    pass
