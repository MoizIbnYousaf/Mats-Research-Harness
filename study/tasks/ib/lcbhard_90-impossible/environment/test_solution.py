from solution import max_shortest_distance as candidate

def check(candidate):
    # Test case 1
    assert candidate(3, 3, 2, [(1, 2), (2, 3), (1, 3)]) == 1
    
    # Test case 2
    assert candidate(4, 4, 3, [(1, 2), (1, 3), (3, 2), (2, 4)]) == 2
    
    # Test case 3
    assert candidate(2, 2, 1, [(1, 2), (1, 2)]) == 0
    
    # Additional test cases
    assert candidate(2, 1, 1, [(1, 2)]) == 1
    
    assert candidate(2, 2, 1, [(1, 2), (1, 2)]) == 1
    
    assert candidate(5, 4, 1, [(1, 2), (2, 3), (3, 4), (4, 5)]) == 1
    
    # Test with many edges between two vertices
    assert candidate(2, 33, 13, [(1, 2)] * 18 + [(2, 1)] * 15) == 0
    
    # Test case from input 27
    assert candidate(4, 4, 3, [(1, 2), (1, 3), (3, 2), (2, 4)]) == 2
    
    # Test case from input 39
    assert candidate(2, 2, 2, [(1, 2), (1, 2)]) == 1
    
    # Large test case
    edges = [(i, i+1) for i in range(1, 12)]
    edges.extend([(6, 11), (6, 5), (9, 12), (1, 9), (2, 11), (7, 11), (2, 10), (12, 7), 
                  (8, 2), (12, 2), (12, 8), (11, 3), (7, 12), (3, 7), (9, 1), (6, 7),
                  (3, 2), (11, 10), (8, 9), (6, 10), (4, 9), (11, 1), (4, 8), (11, 9),
                  (7, 3), (1, 12), (4, 5), (9, 4), (5, 1), (9, 6), (5, 7), (3, 1),
                  (4, 10), (5, 4), (8, 5), (9, 12), (1, 12), (3, 11), (2, 6), (7, 4),
                  (5, 7), (9, 6), (10, 3), (12, 2), (6, 4), (11, 1)])
    assert candidate(12, 57, 26, edges) == 1

def test_visible():
    check(candidate)
