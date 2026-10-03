from fractions import Fraction
from signals import budget, fixture, measure

events = fixture()
result = measure(events)
assert result["total"] == 110 and result["good"] == 91
assert result["ratio"] == Fraction(91, 110)
cost = budget(result["total"], result["total"] - result["good"])
assert cost["allowed"] == Fraction(11, 10)
assert cost["burn"] == Fraction(190, 11)
print({"total": result["total"], "good": result["good"],
       "ratio": str(result["ratio"]), "burn": str(cost["burn"])})
