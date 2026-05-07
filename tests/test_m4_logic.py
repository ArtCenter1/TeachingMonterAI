import pytest
from modules.m4_generator import ScriptGenerator

def test_formula_validation():
    gen = ScriptGenerator()
    
    # Test valid formulas
    valid_script = {"segments": [{"narration": "The slope is (y2 - y1) / (x2 - x1)."}]}
    assert gen._validate_formulas(valid_script) == []
    
    # Test invalid formulas
    invalid_script = {"segments": [{"narration": "Calculate using y2 - x1."}]}
    errors = gen._validate_formulas(invalid_script)
    assert len(errors) == 1
    assert "y2-x1" in errors[0]
    
    # Test distance formula error
    dist_error = {"segments": [{"narration": "The distance is sqrt((x2-x1)^2 + (y2-x1)^2)."}]}
    errors = gen._validate_formulas(dist_error)
    assert len(errors) == 1
    assert "y2-x1" in errors[0]
