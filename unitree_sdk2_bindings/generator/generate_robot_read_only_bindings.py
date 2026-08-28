"""Generate the explicitly read-only Unitree robot client binding surface."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


CLIENT_BASE = "unitree::robot::Client"
CLIENT_BASE_BASE = "unitree::robot::ClientBase"
SUPPORTED_STRATEGIES = {"OUTPUT_WRAPPER"}


def qualified_name(item: dict[str, Any]) -> str:
    namespace = item.get("namespace", "")
    return f"{namespace}::{item['name']}" if namespace else item["name"]


def method_signature(method: dict[str, Any]) -> str:
    parameters = ", ".join(item["type"] for item in method["parameters"])
    suffix = " const" if method.get("is_const") else ""
    return f"{method['name']}({parameters}){suffix}"


def snake_case(name: str) -> str:
    first_pass = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", first_pass).lower()


def header_include(cpp_class: dict[str, Any], sdk_root: Path) -> str:
    header = Path(cpp_class["location"]["file"])
    if not header.is_absolute():
        header = sdk_root / header
    include_root = sdk_root / "include"
    try:
        return str(header.resolve().relative_to(include_root.resolve()))
    except ValueError as error:
        raise ValueError(
            f"header is outside SDK include directory: {header}"
        ) from error


def is_mutable_output(type_name: str) -> bool:
    return "&" in type_name and not type_name.lstrip().startswith("const ")


def value_type(type_name: str) -> str:
    result = type_name.strip()
    result = re.sub(r"\bconst\s+", "", result)
    result = re.sub(r"\s*&&?\s*$", "", result)
    return result.strip()


def qualify_local_types(
    type_name: str,
    namespace: str,
    classes_by_name: dict[str, dict[str, Any]],
) -> str:
    result = type_name
    for candidate in classes_by_name.values():
        if candidate.get("namespace") != namespace:
            continue
        name = candidate["name"]
        result = re.sub(
            rf"(?<![A-Za-z0-9_:]){re.escape(name)}(?![A-Za-z0-9_])",
            qualified_name(candidate),
            result,
        )
    return result


def module_variable(namespace: str) -> str:
    suffix = namespace.removeprefix("unitree::robot").strip(":")
    return "robot" if not suffix else "robot_" + suffix.replace("::", "_")


def render_output_method(
    cpp_class: dict[str, Any],
    method: dict[str, Any],
    classes_by_name: dict[str, dict[str, Any]],
) -> list[str]:
    cpp_name = qualified_name(cpp_class)
    inputs: list[tuple[str, str]] = []
    outputs: list[tuple[str, str]] = []
    call_arguments: list[str] = []
    for index, parameter in enumerate(method["parameters"]):
        name = parameter.get("name") or f"arg{index}"
        parameter_type = qualify_local_types(
            parameter["type"], cpp_class["namespace"], classes_by_name
        )
        if is_mutable_output(parameter["type"]):
            name = name if parameter.get("name") else f"output_{index}"
            outputs.append((value_type(parameter_type), name))
        else:
            inputs.append((parameter_type, name))
        call_arguments.append(name)

    if not outputs:
        raise ValueError(
            f"read-only wrapper has no output: {cpp_name}::{method_signature(method)}"
        )
    if method["return_type"] == "void":
        raise ValueError(
            f"void output wrapper needs a separate policy: {cpp_name}::{method_signature(method)}"
        )

    lambda_parameters = [f"{cpp_name}& self"] + [
        f"{type_name} {name}" for type_name, name in inputs
    ]
    return_type = qualify_local_types(
        method["return_type"], cpp_class["namespace"], classes_by_name
    )
    output_names = [name for _, name in outputs]
    lines = [
        f'  {module_variable(cpp_class["namespace"])}_{cpp_class["name"]}.def(',
        f'      "{snake_case(method["name"])}",',
        f"      []({', '.join(lambda_parameters)}) {{",
    ]
    lines.extend(f"        {type_name} {name}{{}};" for type_name, name in outputs)
    lines.extend(
        [
            f"        {return_type} status{{}};",
            "        {",
            "          py::gil_scoped_release release;",
            f"          status = self.{method['name']}({', '.join(call_arguments)});",
            "        }",
            "        return py::make_tuple(",
            "            status, "
            + ", ".join(f"std::move({name})" for name in output_names)
            + ");",
            "      }",
        ]
    )
    for _, name in inputs:
        lines[-1] += f', py::arg("{snake_case(name)}")'
    output_description = ", ".join(["status", *output_names])
    lines[-1] += f', "Returns ({output_description}).");'
    return lines


def discover_value_classes(
    selected: list[tuple[dict[str, Any], list[dict[str, Any]]]],
    classes_by_name: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for cpp_class, methods in selected:
        for method in methods:
            for parameter in method["parameters"]:
                if not is_mutable_output(parameter["type"]):
                    continue
                for candidate in classes_by_name.values():
                    if candidate.get("namespace") != cpp_class["namespace"]:
                        continue
                    if re.search(
                        rf"\b{re.escape(candidate['name'])}\b", parameter["type"]
                    ):
                        result[qualified_name(candidate)] = candidate
    return [result[name] for name in sorted(result)]


def generate(
    inventory: dict[str, Any], classification: dict[str, Any], policy: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    sdk_root = Path(inventory["sdk_root"])
    classes_by_name = {qualified_name(item): item for item in inventory["classes"]}
    selected: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []

    unmatched_policy = {
        (cpp_name, signature)
        for cpp_name, signatures in policy.get("classes", {}).items()
        for signature in signatures
    }
    for client_report in classification["clients"]:
        cpp_name = client_report["qualified_name"]
        cpp_class = classes_by_name.get(cpp_name)
        if cpp_class is None or cpp_name in {CLIENT_BASE, CLIENT_BASE_BASE}:
            continue
        bases = {base["type"] for base in cpp_class.get("bases", [])}
        if CLIENT_BASE not in bases:
            continue
        approved_signatures = set(policy.get("classes", {}).get(cpp_name, []))
        report_methods = {
            (item["name"], item["signature"]): item
            for item in client_report["methods"]
            if item["safety"] == "READ_ONLY"
            and item["binding_strategy"] in SUPPORTED_STRATEGIES
            and item["signature"] in approved_signatures
        }
        methods = [
            method
            for method in cpp_class["methods"]
            if (method["name"], method_signature(method)) in report_methods
        ]
        for method in methods:
            unmatched_policy.discard((cpp_name, method_signature(method)))
        if methods:
            selected.append((cpp_class, methods))

    if unmatched_policy:
        formatted = ", ".join(
            f"{cpp_name}::{signature}"
            for cpp_name, signature in sorted(unmatched_policy)
        )
        raise ValueError(
            "policy entries are missing or no longer classified as safe read-only: "
            + formatted
        )

    selected.sort(key=lambda item: qualified_name(item[0]))
    value_classes = discover_value_classes(selected, classes_by_name)
    includes = {
        "unitree/robot/client/client.hpp",
        *(header_include(item, sdk_root) for item, _ in selected),
        *(header_include(item, sdk_root) for item in value_classes),
    }
    namespaces = sorted(
        {item["namespace"] for item, _ in selected}
        | {item["namespace"] for item in value_classes}
    )

    lines = [
        "// Generated by generator/generate_robot_read_only_bindings.py. Do not edit manually.",
        '#include "bindings.hpp"',
        "",
        "#include <utility>",
        "#include <pybind11/stl.h>",
        "",
        *(f"#include <{header}>" for header in sorted(includes)),
        "",
        "namespace py = pybind11;",
        "",
        "void BindRobotReadOnly(py::module_& root) {",
        '  py::module_ robot = EnsureSubmodule(root, "robot");',
        "",
        f'  py::class_<{CLIENT_BASE_BASE}>(robot, "ClientBase")',
        '      .def("set_timeout",',
        f"           py::overload_cast<float>(&{CLIENT_BASE_BASE}::SetTimeout),",
        '           py::arg("seconds"))',
        '      .def("set_timeout_microseconds",',
        f"           py::overload_cast<int64_t>(&{CLIENT_BASE_BASE}::SetTimeout),",
        '           py::arg("microseconds"));',
        "",
        f'  py::class_<{CLIENT_BASE}, {CLIENT_BASE_BASE}>(robot, "Client")',
        f'      .def("get_lease_id", &{CLIENT_BASE}::GetLeaseId)',
        '      .def("get_api_version",',
        f"           [](const {CLIENT_BASE}& self) {{",
        "             return std::string(self.GetApiVersion());",
        "           })",
        '      .def("get_server_api_version",',
        f"           []({CLIENT_BASE}& self) {{",
        "             py::gil_scoped_release release;",
        "             return self.GetServerApiVersion();",
        "           });",
        "",
    ]

    for namespace in namespaces:
        if namespace == "unitree::robot":
            continue
        path = namespace.removeprefix("unitree::robot::").split("::")
        parent = "robot"
        prefix: list[str] = []
        for part in path:
            prefix.append(part)
            variable = "robot_" + "_".join(prefix)
            if not any(line.startswith(f"  py::module_ {variable} ") for line in lines):
                lines.append(
                    f'  py::module_ {variable} = EnsureSubmodule({parent}, "{part}");'
                )
            parent = variable
    lines.append("")

    for value_class in value_classes:
        cpp_name = qualified_name(value_class)
        variable = f"{module_variable(value_class['namespace'])}_{value_class['name']}"
        lines.append(
            f"  py::class_<{cpp_name}> {variable}("
            f'{module_variable(value_class["namespace"])}, "{value_class["name"]}");'
        )
        if any(
            constructor["access"] == "public" and not constructor["parameters"]
            for constructor in value_class.get("constructors", [])
        ):
            lines.append(f"  {variable}.def(py::init<>());")
        for field in value_class.get("fields", []):
            if field["access"] == "public":
                lines.append(
                    f'  {variable}.def_readwrite("{snake_case(field["name"])}", '
                    f"&{cpp_name}::{field['name']});"
                )
        lines.append("")

    class_reports: list[dict[str, Any]] = []
    for cpp_class, methods in selected:
        cpp_name = qualified_name(cpp_class)
        variable = f"{module_variable(cpp_class['namespace'])}_{cpp_class['name']}"
        lines.extend(
            [
                f"  py::class_<{cpp_name}, {CLIENT_BASE}> {variable}(",
                f'      {module_variable(cpp_class["namespace"])}, "{cpp_class["name"]}");',
                f"  {variable}.def(py::init<>());",
                f'  {variable}.def("init", []({cpp_name}& self) {{',
                "    py::gil_scoped_release release;",
                "    self.Init();",
                "  });",
            ]
        )
        for method in methods:
            lines.extend(render_output_method(cpp_class, method, classes_by_name))
        lines.append("")
        class_reports.append(
            {
                "qualified_name": cpp_name,
                "python_module": "unitree_sdk2_cpp."
                + cpp_class["namespace"].removeprefix("unitree::").replace("::", "."),
                "python_name": cpp_class["name"],
                "status": "PARTIAL_READ_ONLY",
                "methods": [snake_case(method["name"]) for method in methods],
            }
        )

    lines.extend(["}", ""])
    method_count = sum(len(methods) for _, methods in selected)
    value_class_reports = [
        {
            "qualified_name": qualified_name(item),
            "python_module": "unitree_sdk2_cpp."
            + item["namespace"].removeprefix("unitree::").replace("::", "."),
            "python_name": item["name"],
            "status": "AVAILABLE_VALUE",
        }
        for item in value_classes
    ]
    report = {
        "schema_version": 1,
        "sources": [
            "generated/robot_binding_report.json",
            "generator/robot_read_only_policy.json",
        ],
        "summary": {
            "client_classes": len(selected),
            "read_only_methods": method_count,
            "motion_methods_exposed": 0,
            "hardware_side_effect_methods_exposed": 0,
            "value_classes": len(value_classes),
        },
        "classes": class_reports,
        "value_classes": value_class_reports,
    }
    return "\n".join(lines), report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--classification", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args()

    inventory = json.loads(arguments.inventory.read_text(encoding="utf-8"))
    classification = json.loads(arguments.classification.read_text(encoding="utf-8"))
    policy = json.loads(arguments.policy.read_text(encoding="utf-8"))
    source, report = generate(inventory, classification, policy)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(source, encoding="utf-8")
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"Generated {report['summary']['read_only_methods']} read-only methods "
        f"for {report['summary']['client_classes']} clients"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
