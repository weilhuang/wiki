"""Original finite declaration checker, NOT an application import analyzer."""
from copy import deepcopy


def fixture():
    return {
        "modules": {
            "checkout": {"allows": ["orders", "inventory"]},
            "orders": {"allows": []}, "inventory": {"allows": []},
            "reports": {"allows": ["orders"]},
        },
        "imports": [["checkout", "orders", "api"],
                    ["checkout", "inventory", "api"], ["reports", "orders", "api"]],
        "tableOwners": {"orders": "orders", "reservations": "inventory"},
        "writes": [["orders", "orders"], ["inventory", "reservations"]],
    }


def inspect(design):
    errors = []
    modules = design["modules"]
    graph = {name: set() for name in modules}
    for caller, callee, exposure in design["imports"]:
        if caller not in modules or callee not in modules:
            errors.append("unknown-module:" + caller + "->" + callee)
            continue
        if caller == callee:
            continue
        graph[caller].add(callee)
        if exposure != "api":
            errors.append("internal-access:" + caller + "->" + callee)
        if callee not in modules[caller]["allows"]:
            errors.append("forbidden-dependency:" + caller + "->" + callee)
    for writer, table in design["writes"]:
        if design["tableOwners"].get(table) != writer:
            errors.append("foreign-write:" + writer + "->" + table)
    active, done = set(), set()

    def visit(name):
        if name in active:
            return True
        if name in done:
            return False
        active.add(name)
        for target in sorted(graph[name]):
            if visit(target):
                return True
        active.remove(name)
        done.add(name)
        return False

    if any(visit(name) for name in sorted(modules)):
        errors.append("module-cycle")
    return sorted(errors)


def changed(design, variant):
    candidate = deepcopy(design)
    if variant == "internal-import":
        candidate["imports"][-1][2] = "internal"
    elif variant == "foreign-write":
        candidate["writes"].append(["reports", "orders"])
    elif variant == "cycle":
        candidate["modules"]["orders"]["allows"] = ["checkout"]
        candidate["imports"].append(["orders", "checkout", "api"])
    elif variant != "good":
        raise ValueError("unknown architecture variant")
    return candidate
