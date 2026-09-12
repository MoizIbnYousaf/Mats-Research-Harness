from solution import round_half_up as candidate

def check(candidate):
    # Sample test cases
    assert candidate(2.4) == 2
    assert candidate(2.6) == 3
    assert candidate(-2.5) == -3
    
    # Additional test cases
    assert candidate(3.5) == 4
    assert candidate(0.5) == 1
    assert candidate(2.5) == 2

def test_visible():
    check(candidate)
