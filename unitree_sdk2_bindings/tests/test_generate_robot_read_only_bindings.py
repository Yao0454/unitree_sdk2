import copy
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "generator"))

from generate_robot_read_only_bindings import generate  # noqa: E402


def _load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_checked_in_read_only_binding_is_current() -> None:
    source, report = generate(
        _load("generated/robot_inventory.json"),
        _load("generated/robot_binding_report.json"),
        _load("generator/robot_read_only_policy.json"),
    )
    assert source == (ROOT / "src/generated/robot_read_only.cpp").read_text(
        encoding="utf-8"
    )
    assert report == _load("generated/robot_read_only_report.json")
    assert report["summary"] == {
        "client_classes": 21,
        "hardware_side_effect_methods_exposed": 0,
        "motion_methods_exposed": 0,
        "read_only_methods": 45,
        "value_classes": 2,
    }
    assert {
        item["qualified_name"] for item in report["value_classes"]
    } == {
        "unitree::robot::b2::ServiceState",
        "unitree::robot::go2::ServiceState",
    }
    assert ".Move(" not in source
    assert '"move"' not in source


def test_policy_rejects_a_motion_method_even_if_named_explicitly() -> None:
    policy = copy.deepcopy(_load("generator/robot_read_only_policy.json"))
    policy["classes"]["unitree::robot::g1::LocoClient"].append(
        "Move(float, float, float)"
    )
    with pytest.raises(ValueError, match="no longer classified as safe read-only"):
        generate(
            _load("generated/robot_inventory.json"),
            _load("generated/robot_binding_report.json"),
            policy,
        )
