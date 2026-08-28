import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


SDK_ROOT = Path(__file__).parents[2]
SCANNER = SDK_ROOT / "unitree_sdk2_bindings" / "generator" / "scan_headers.py"
sys.path.insert(0, str(SDK_ROOT / "unitree_sdk2_bindings" / "generator"))
from scan_headers import (  # noqa: E402
    _headers_from_arguments,
    decode_clang_ast_stream,
    discover_declarations,
)


def test_declaration_discovery_ignores_struct_return_types() -> None:
    candidates = discover_declarations(SDK_ROOT / "include/unitree/common/os.hpp")
    names = {candidate.name for candidate in candidates}
    assert "OsHelper" in names
    assert "UT_SCHED_POLICY" in names
    assert "passwd" not in names


def test_clang_10_dump_prefixes_are_accepted() -> None:
    output = 'Dumping demo::A:\n{"kind": "A"}\nDumping demo::B:\n{"kind": "B"}\n'
    assert decode_clang_ast_stream(output) == [{"kind": "A"}, {"kind": "B"}]


def test_header_discovery_ignores_macos_appledouble_files(tmp_path: Path) -> None:
    include = tmp_path / "include"
    include.mkdir()
    (include / "message.hpp").write_text("struct Message {};\n", encoding="utf-8")
    (include / "._message.hpp").write_bytes(b"\x00\x05\x16\x07")
    assert _headers_from_arguments(tmp_path, ["include"]) == [
        include / "message.hpp"
    ]


@pytest.mark.skipif(shutil.which("clang++") is None, reason="clang++ is required")
def test_scanner_extracts_idl_overloads_and_types(tmp_path: Path) -> None:
    output = tmp_path / "inventory.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCANNER),
            "--sdk-root",
            str(SDK_ROOT),
            "--output",
            str(output),
            "include/unitree/idl/go2/MotorState_.hpp",
            "include/unitree/idl/go2/IMUState_.hpp",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    inventory = json.loads(output.read_text(encoding="utf-8"))
    classes = {item["name"]: item for item in inventory["classes"]}
    assert set(classes) == {"IMUState_", "MotorState_"}
    assert classes["MotorState_"]["namespace"] == "unitree_go::msg::dds_"

    motor_methods = classes["MotorState_"]["methods"]
    q_overloads = [method for method in motor_methods if method["name"] == "q"]
    assert len(q_overloads) == 3
    assert {method["return_type"] for method in q_overloads} == {
        "float",
        "float &",
        "void",
    }

    imu_fields = {field["name"]: field for field in classes["IMUState_"]["fields"]}
    assert imu_fields["quaternion_"]["type"] == "std::array<float, 4>"
    assert inventory["diagnostics"] == []
