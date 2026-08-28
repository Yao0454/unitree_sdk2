import json
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
unitree_sdk2_cpp = pytest.importorskip("unitree_sdk2_cpp")


def _resolve(path: str):
    value = unitree_sdk2_cpp
    for part in path.removeprefix("unitree_sdk2_cpp.").split("."):
        value = getattr(value, part)
    return value


def test_read_only_client_surface_is_registered_without_construction() -> None:
    report = json.loads(
        (ROOT / "generated/robot_read_only_report.json").read_text(encoding="utf-8")
    )
    assert hasattr(unitree_sdk2_cpp.robot.ClientBase, "set_timeout")
    assert hasattr(unitree_sdk2_cpp.robot.Client, "get_api_version")
    for item in report["classes"]:
        client_type = getattr(_resolve(item["python_module"]), item["python_name"])
        assert hasattr(client_type, "init")
        for method in item["methods"]:
            assert hasattr(client_type, method)


def test_motion_commands_are_not_exposed() -> None:
    assert not hasattr(unitree_sdk2_cpp.robot.g1.LocoClient, "move")
    assert not hasattr(unitree_sdk2_cpp.robot.g1.LocoClient, "stand_up")
    assert not hasattr(unitree_sdk2_cpp.robot.h2.H2ArmActionClient, "execute_action")
    assert not hasattr(unitree_sdk2_cpp.robot.go2.VuiClient, "set_volume")
