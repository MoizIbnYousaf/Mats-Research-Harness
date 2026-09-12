from solution import count_stepping_numbers as candidate

def check(candidate):
    assert candidate("4", "9") == 7
    assert candidate("3", "84") == 21
    assert candidate("1", "66") == 20
    assert candidate("45", "66") == 4
    assert candidate("4", "50") == 14
    assert candidate("9", "68") == 13
    assert candidate("12", "89") == 15
    assert candidate("9888878", "9899998") == 6
    assert candidate("303628", "786017178") == 2704
    assert candidate("31384570389283431", "73857241289720257") == 162182
    assert candidate("399209151314805334158", "863865742870965104736") == 2115150
    assert candidate("1203109284118568358408114942744154309516373371543388344493782743693904745519867118487579839270928580", 
                     "6121833782106632749517843393634569515258465712511663330500608285264190592002792370635436513179865625") == 729890404

def test_visible():
    check(candidate)
