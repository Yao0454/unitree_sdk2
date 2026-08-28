"""Generate PEP 561 preview stubs and an API availability manifest."""

from __future__ import annotations

import argparse
import json
import keyword
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCALAR_TYPES = {
    "bool": "bool",
    "char": "int",
    "signed char": "int",
    "unsigned char": "int",
    "int8_t": "int",
    "uint8_t": "int",
    "int16_t": "int",
    "uint16_t": "int",
    "int32_t": "int",
    "uint32_t": "int",
    "int64_t": "int",
    "uint64_t": "int",
    "short": "int",
    "unsigned short": "int",
    "int": "int",
    "unsigned int": "int",
    "long": "int",
    "unsigned long": "int",
    "long long": "int",
    "unsigned long long": "int",
    "size_t": "int",
    "float": "float",
    "double": "float",
    "void": "None",
}
CLIENT_NAMES = {"Client", "ClientBase", "ClientStub", "LeaseClient"}


def qualified_name(item: dict[str, Any]) -> str:
    namespace = item.get("namespace", "")
    return f"{namespace}::{item['name']}" if namespace else item["name"]


def method_signature(method: dict[str, Any]) -> str:
    parameters = ", ".join(item["type"] for item in method.get("parameters", []))
    suffix = " const" if method.get("is_const") else ""
    return f"{method['name']}({parameters}){suffix}"


def snake_case(name: str) -> str:
    first_pass = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", first_pass).lower()


def parameter_name(name: str, index: int) -> str:
    result = snake_case(name) if name else f"arg{index}"
    return python_identifier(result)


def python_identifier(name: str) -> str:
    return name + "_" if keyword.iskeyword(name) else name


def normalize_cpp_type(type_name: str) -> str:
    result = type_name.strip().lstrip(":")
    result = re.sub(r"\bconst\s+", "", result)
    result = re.sub(r"\s*&&?\s*$", "", result)
    result = re.sub(r"\s+", " ", result)
    result = re.sub(r"\s*<\s*", "<", result)
    result = re.sub(r"\s*>\s*", ">", result)
    result = re.sub(r"\s*,\s*", ",", result)
    return result.strip()


def split_template_arguments(arguments: str) -> list[str]:
    result: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(arguments):
        if char == "<":
            depth += 1
        elif char == ">":
            depth -= 1
        elif char == "," and depth == 0:
            result.append(arguments[start:index].strip())
            start = index + 1
    result.append(arguments[start:].strip())
    return result


def template_parts(type_name: str) -> tuple[str, list[str]] | None:
    start = type_name.find("<")
    if start < 0 or not type_name.endswith(">"):
        return None
    return type_name[:start], split_template_arguments(type_name[start + 1 : -1])


class TypeMapper:
    def __init__(
        self,
        classes: list[dict[str, Any]],
        python_names: dict[str, str] | None = None,
    ) -> None:
        self.classes = {qualified_name(item).lstrip(":"): item for item in classes}
        self.python_names = python_names or {}

    def annotation(
        self, type_name: str, namespace: str, position: str = "return"
    ) -> str:
        original = type_name.strip()
        normalized = normalize_cpp_type(original)
        if normalized in SCALAR_TYPES:
            return SCALAR_TYPES[normalized]
        if normalized in {"std::string", "string"}:
            return "str"
        if normalized in {"common::JsonMap", "unitree::common::JsonMap"}:
            return "dict[str, Any]"
        if "Callback" in normalized or normalized.endswith("ServerRequestHandler"):
            if "ConfigChangeStatusCallback" in normalized:
                return "Callable[[str, str], None]"
            return "Callable[..., Any]"
        if normalized.startswith("std::function<"):
            return "Callable[..., Any]"

        parts = template_parts(normalized)
        if parts:
            template, arguments = parts
            if template in {"std::vector", "std::array"} and arguments:
                value = self.annotation(arguments[0], namespace, "return")
                return f"Sequence[{value}]" if position == "input" else f"list[{value}]"
            if template in {"std::map", "std::unordered_map"} and len(arguments) == 2:
                key = self.annotation(arguments[0], namespace, "return")
                value = self.annotation(arguments[1], namespace, "return")
                mapping = f"dict[{key}, {value}]"
                return f"Mapping[{key}, {value}]" if position == "input" else mapping
            if template in {"std::shared_ptr", "std::unique_ptr"} and arguments:
                return self.annotation(arguments[0], namespace, position)
            if template in {"std::pair"} and len(arguments) == 2:
                first = self.annotation(arguments[0], namespace, "return")
                second = self.annotation(arguments[1], namespace, "return")
                return f"tuple[{first}, {second}]"
            if template in {"std::optional"} and arguments:
                return f"{self.annotation(arguments[0], namespace, position)} | None"

        if "*" in normalized:
            pointee = normalized.replace("*", "").strip()
            known = self._known_class(pointee, namespace)
            return known or "Any"
        known = self._known_class(normalized, namespace)
        if known:
            return known
        if normalized.endswith("Ptr"):
            known = self._known_class(normalized.removesuffix("Ptr"), namespace)
            return known or "Any"
        if normalized.startswith(("Eigen::", "dds::", "unitree_api::")):
            return "Any"
        return "Any"

    def _known_class(self, type_name: str, namespace: str) -> str | None:
        normalized = type_name.lstrip(":")
        candidate = self.classes.get(normalized)
        if candidate:
            if candidate["namespace"] == namespace:
                return self.python_names.get(
                    qualified_name(candidate), candidate["name"]
                )
            if candidate["namespace"] == "unitree::robot" and candidate["name"] in {
                "Client",
                "ClientBase",
            }:
                return candidate["name"]
            return None
        local = f"{namespace}::{normalized}" if namespace else normalized
        candidate = self.classes.get(local)
        if not candidate:
            return None
        return self.python_names.get(qualified_name(candidate), candidate["name"])


def mutable_output(type_name: str) -> bool:
    return "&" in type_name and not type_name.lstrip().startswith("const ")


def method_status(
    cpp_class: str,
    method: dict[str, Any],
    available_policy: dict[str, set[str]],
    available_classes: set[str],
) -> str:
    signature = method_signature(method)
    if cpp_class == "unitree::robot::ClientBase" and signature in {
        "SetTimeout(int64_t)",
        "SetTimeout(float)",
    }:
        return "AVAILABLE"
    if cpp_class == "unitree::robot::Client" and signature in {
        "GetLeaseId()",
        "GetApiVersion() const",
        "GetServerApiVersion()",
    }:
        return "AVAILABLE"
    if cpp_class in available_classes and signature == "Init()":
        return "AVAILABLE"
    if signature in available_policy.get(cpp_class, set()):
        return "AVAILABLE"
    return "SIGNATURE_ONLY"


def method_annotations(
    method: dict[str, Any],
    namespace: str,
    mapper: TypeMapper,
    output_wrapper: bool,
) -> tuple[list[str], str]:
    parameters: list[str] = []
    outputs: list[str] = []
    for index, parameter in enumerate(method.get("parameters", [])):
        if output_wrapper and mutable_output(parameter["type"]):
            outputs.append(mapper.annotation(parameter["type"], namespace, "return"))
            continue
        name = parameter_name(parameter.get("name", ""), index)
        annotation = mapper.annotation(parameter["type"], namespace, "input")
        default = " = ..." if parameter.get("has_default") else ""
        parameters.append(f"{name}: {annotation}{default}")

    result = mapper.annotation(method.get("return_type", "void"), namespace, "return")
    if outputs:
        values = ([] if result == "None" else [result]) + outputs
        result = values[0] if len(values) == 1 else f"tuple[{', '.join(values)}]"
    return parameters, result


def output_suffix(method: dict[str, Any]) -> str:
    for parameter in method.get("parameters", []):
        if not mutable_output(parameter["type"]):
            continue
        normalized = normalize_cpp_type(parameter["type"])
        parts = template_parts(normalized)
        if parts:
            template = parts[0].rsplit("::", 1)[-1]
            return snake_case(template)
        return snake_case(normalized.rsplit("::", 1)[-1].removesuffix("_"))
    return "result"


def python_method_name(cpp_class: str, method: dict[str, Any]) -> str:
    if (
        cpp_class == "unitree::robot::ClientBase"
        and method_signature(method) == "SetTimeout(int64_t)"
    ):
        return "set_timeout_microseconds"
    return python_identifier(snake_case(method["name"]))


def class_base(cpp_class: dict[str, Any], module_namespace: str) -> str:
    for base in cpp_class.get("bases", []):
        normalized = normalize_cpp_type(base["type"])
        if normalized == "unitree::robot::Client":
            return "Client"
        if normalized == "unitree::robot::ClientBase":
            return "ClientBase"
        if normalized.startswith(module_namespace + "::"):
            return normalized.rsplit("::", 1)[-1]
    return "object"


def render_robot_module(
    namespace: str,
    classes: list[dict[str, Any]],
    enums: list[dict[str, Any]],
    mapper: TypeMapper,
    classifications: dict[tuple[str, str], dict[str, str]],
    available_policy: dict[str, set[str]],
    available_classes: set[str],
    manifest: list[dict[str, Any]],
) -> str:
    lines = [
        '"""Full SDK signature preview; see api_manifest.json for availability."""',
        "from __future__ import annotations",
        "",
        "import enum",
        "from collections.abc import Callable, Mapping, Sequence",
        "from typing import Any, overload",
    ]
    if namespace != "unitree::robot":
        lines.extend(["", "from . import Client, ClientBase"])
    lines.append("")

    for cpp_enum in sorted(enums, key=lambda item: item["name"]):
        lines.append(f"class {cpp_enum['name']}(enum.IntEnum):")
        values = cpp_enum.get("values", [])
        if values:
            lines.extend(f"    {item['name']} = ..." for item in values)
        else:
            lines.append("    ...")
        lines.append("")

    client_class_names = {
        item["name"]
        for item in classes
        if item["name"].endswith("Client") or item["name"] in CLIENT_NAMES
    }
    for cpp_class in sorted(classes, key=lambda item: item["name"]):
        cpp_name = qualified_name(cpp_class)
        base = class_base(cpp_class, namespace)
        lines.append(f"class {cpp_class['name']}({base}):")
        body: list[str] = []

        constructors = [
            item
            for item in cpp_class.get("constructors", [])
            if item.get("access") == "public"
        ]
        for index, constructor in enumerate(constructors):
            if len(constructors) > 1:
                body.append("    @overload")
            parameters, _ = method_annotations(constructor, namespace, mapper, False)
            status = (
                "AVAILABLE"
                if cpp_name in available_classes and not parameters
                else "SIGNATURE_ONLY"
            )
            body.extend(
                [
                    f"    def __init__(self{', ' if parameters else ''}{', '.join(parameters)}) -> None:",
                    f'        """{status}; C++: {cpp_name}::{method_signature(constructor)}."""',
                    "        ...",
                ]
            )
            manifest.append(
                {
                    "cpp_class": cpp_name,
                    "cpp_signature": method_signature(constructor),
                    "python_path": f"unitree_sdk2_cpp.{namespace.removeprefix('unitree::').replace('::', '.')}.{cpp_class['name']}.__init__",
                    "status": status,
                    "safety": "CONSTRUCTION",
                }
            )

        for field in cpp_class.get("fields", []):
            if field.get("access") == "public":
                body.append(
                    f"    {python_identifier(snake_case(field['name']))}: "
                    f"{mapper.annotation(field['type'], namespace, 'return')}"
                )

        methods = [
            item
            for item in cpp_class.get("methods", [])
            if item.get("access") == "public"
        ]
        output_wrapper = cpp_class["name"] in client_class_names
        base_names = [python_method_name(cpp_name, item) for item in methods]
        input_shapes = [
            tuple(
                mapper.annotation(parameter["type"], namespace, "input")
                for parameter in method.get("parameters", [])
                if not (output_wrapper and mutable_output(parameter["type"]))
            )
            for method in methods
        ]
        shape_counts = Counter(zip(base_names, input_shapes, strict=True))
        python_names = [
            (
                f"{base_name}_{output_suffix(method)}"
                if output_wrapper and shape_counts[(base_name, shape)] > 1
                else base_name
            )
            for method, base_name, shape in zip(
                methods, base_names, input_shapes, strict=True
            )
        ]
        grouped: Counter[str] = Counter(python_names)
        for method, python_name in zip(methods, python_names, strict=True):
            if grouped[python_name] > 1:
                body.append("    @overload")
            parameters, result = method_annotations(
                method, namespace, mapper, output_wrapper
            )
            if cpp_name == "unitree::robot::ClientBase":
                if method_signature(method) == "SetTimeout(int64_t)":
                    parameters = ["microseconds: int"]
                elif method_signature(method) == "SetTimeout(float)":
                    parameters = ["seconds: float"]
            classification = classifications.get(
                (cpp_name, method_signature(method)), {}
            )
            status = method_status(
                cpp_name, method, available_policy, available_classes
            )
            safety = classification.get("safety", "UNCLASSIFIED")
            strategy = classification.get("binding_strategy", "SIGNATURE_PREVIEW")
            body.extend(
                [
                    f"    def {python_name}(self{', ' if parameters else ''}{', '.join(parameters)}) -> {result}:",
                    f'        """{status} | {safety} | {strategy}. C++: {method_signature(method)}."""',
                    "        ...",
                ]
            )
            manifest.append(
                {
                    "cpp_class": cpp_name,
                    "cpp_signature": method_signature(method),
                    "python_path": f"unitree_sdk2_cpp.{namespace.removeprefix('unitree::').replace('::', '.')}.{cpp_class['name']}.{python_name}",
                    "status": status,
                    "safety": safety,
                    "binding_strategy": strategy,
                    "python_return": result,
                }
            )

        lines.extend(body or ["    ..."])
        lines.append("")
    return "\n".join(lines)


def render_idl_module(
    module_name: str,
    report: dict[str, Any],
    inventory: dict[str, Any],
    mapper: TypeMapper,
) -> tuple[str, list[dict[str, Any]]]:
    classes_by_name = {qualified_name(item): item for item in inventory["classes"]}
    lines = [
        '"""Generated DDS message bindings."""',
        "from __future__ import annotations",
        "",
        "from collections.abc import Sequence",
        "from typing import Any",
        "",
    ]
    manifest: list[dict[str, Any]] = []
    for item in report["classes"]:
        cpp_class = classes_by_name[item["qualified_name"]]
        fields = {
            field["name"].removesuffix("_"): field for field in cpp_class["fields"]
        }
        lines.extend(
            [
                f"class {item['python_name']}:",
                "    def __init__(self) -> None: ...",
            ]
        )
        manifest.append(
            {
                "cpp_class": item["qualified_name"],
                "cpp_signature": f"{cpp_class['name']}()",
                "python_path": (
                    f"unitree_sdk2_cpp.idl.{module_name}."
                    f"{item['python_name']}.__init__"
                ),
                "status": "AVAILABLE",
                "safety": "VALUE_TYPE",
            }
        )
        for property_name in item["properties"]:
            annotation = mapper.annotation(
                fields[property_name]["type"], cpp_class["namespace"], "return"
            )
            input_annotation = mapper.annotation(
                fields[property_name]["type"], cpp_class["namespace"], "input"
            )
            lines.extend(
                [
                    "    @property",
                    f"    def {property_name}(self) -> {annotation}: ...",
                    f"    @{property_name}.setter",
                    f"    def {property_name}(self, value: {input_annotation}) -> None: ...",
                ]
            )
            manifest.append(
                {
                    "cpp_class": item["qualified_name"],
                    "cpp_signature": fields[property_name]["type"],
                    "python_path": (
                        f"unitree_sdk2_cpp.idl.{module_name}."
                        f"{item['python_name']}.{property_name}"
                    ),
                    "status": "AVAILABLE",
                    "safety": "VALUE_TYPE",
                }
            )
        if any(method["name"] == "operator==" for method in cpp_class["methods"]):
            lines.append("    def __eq__(self, other: object) -> bool: ...")
            manifest.append(
                {
                    "cpp_class": item["qualified_name"],
                    "cpp_signature": "operator==(const value &) const",
                    "python_path": (
                        f"unitree_sdk2_cpp.idl.{module_name}."
                        f"{item['python_name']}.__eq__"
                    ),
                    "status": "AVAILABLE",
                    "safety": "VALUE_TYPE",
                }
            )
        if any(method["name"] == "operator!=" for method in cpp_class["methods"]):
            lines.append("    def __ne__(self, other: object) -> bool: ...")
            manifest.append(
                {
                    "cpp_class": item["qualified_name"],
                    "cpp_signature": "operator!=(const value &) const",
                    "python_path": (
                        f"unitree_sdk2_cpp.idl.{module_name}."
                        f"{item['python_name']}.__ne__"
                    ),
                    "status": "AVAILABLE",
                    "safety": "VALUE_TYPE",
                }
            )
        lines.append("")
    return "\n".join(lines), manifest


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def generate(arguments: argparse.Namespace) -> dict[str, Any]:
    idl_inventory = json.loads(arguments.idl_inventory.read_text(encoding="utf-8"))
    robot_inventory = json.loads(arguments.robot_inventory.read_text(encoding="utf-8"))
    classification = json.loads(arguments.classification.read_text(encoding="utf-8"))
    policy = json.loads(arguments.policy.read_text(encoding="utf-8"))
    read_only_report = json.loads(
        arguments.read_only_report.read_text(encoding="utf-8")
    )
    idl_reports = [
        json.loads(path.read_text(encoding="utf-8")) for path in arguments.idl_report
    ]

    output = arguments.output
    package = output / "unitree_sdk2_cpp-stubs"
    idl_python_names = {
        item["qualified_name"]: item["python_name"]
        for report in idl_reports
        for item in report["classes"]
    }
    mapper = TypeMapper(
        [
            *idl_inventory["classes"],
            *robot_inventory["classes"],
            *robot_inventory["enums"],
        ],
        idl_python_names,
    )
    available_policy = {
        name: set(signatures) for name, signatures in policy["classes"].items()
    }
    available_classes = {
        item["qualified_name"]
        for item in [
            *read_only_report["classes"],
            *read_only_report.get("value_classes", []),
        ]
    }
    classifications = {
        (client["qualified_name"], method["signature"]): method
        for client in classification["clients"]
        for method in client["methods"]
    }

    write_text(
        package / "__init__.pyi",
        '''"""Unitree SDK2 extension API signature preview."""
class OsHelper:
    @staticmethod
    def instance() -> OsHelper: ...
    def get_uid(self) -> int: ...
    def get_gid(self) -> int: ...
    def get_user(self) -> str: ...
    def get_processor_number(self) -> int: ...
    def get_page_size(self) -> int: ...
    def get_hostname(self) -> str: ...
''',
    )
    write_text(
        package / "channel.pyi",
        '''"""Typed CycloneDDS channel API."""
from collections.abc import Callable
from typing import Any, Generic, TypeVar

MessageT = TypeVar("MessageT")

def registered_message_types() -> list[str]: ...
def initialize(domain_id: int = 0, network_interface: str = "") -> None: ...
def initialize_from_config(config_file: str = "") -> None: ...
def release() -> None: ...

class ChannelPublisher(Generic[MessageT]):
    def __init__(self, topic: str, message_type: type[MessageT]) -> None: ...
    @property
    def topic(self) -> str: ...
    @property
    def message_type_name(self) -> str: ...
    def init_channel(self) -> None: ...
    def close_channel(self) -> None: ...
    def write(self, message: MessageT, wait_microsec: int = 0) -> bool: ...

class ChannelSubscriber(Generic[MessageT]):
    def __init__(
        self,
        topic: str,
        message_type: type[MessageT],
        callback: Callable[[MessageT], None],
        queue_length: int = 0,
    ) -> None: ...
    @property
    def topic(self) -> str: ...
    @property
    def message_type_name(self) -> str: ...
    @property
    def last_data_available_time(self) -> int: ...
    def init_channel(self) -> None: ...
    def close_channel(self) -> None: ...
''',
    )

    idl_module_names = ["go2", "hg", "hg_doubleimu", "ros2"]
    write_text(
        package / "idl" / "__init__.pyi",
        '"""DDS message namespaces."""',
    )
    manifest_entries: list[dict[str, Any]] = []
    for name, report in zip(idl_module_names, idl_reports, strict=True):
        content, entries = render_idl_module(name, report, idl_inventory, mapper)
        write_text(package / "idl" / f"{name}.pyi", content)
        manifest_entries.extend(entries)

    manual_paths = {
        "unitree_sdk2_cpp.OsHelper.instance": "OsHelper::Instance()",
        "unitree_sdk2_cpp.OsHelper.get_uid": "OsHelper::GetUID()",
        "unitree_sdk2_cpp.OsHelper.get_gid": "OsHelper::GetGID()",
        "unitree_sdk2_cpp.OsHelper.get_user": "OsHelper::GetUser()",
        "unitree_sdk2_cpp.OsHelper.get_processor_number": "OsHelper::GetProcessorNumber()",
        "unitree_sdk2_cpp.OsHelper.get_page_size": "OsHelper::GetPageSize()",
        "unitree_sdk2_cpp.OsHelper.get_hostname": "OsHelper::GetHostname()",
        "unitree_sdk2_cpp.channel.registered_message_types": "registered_message_types()",
        "unitree_sdk2_cpp.channel.initialize": "ChannelFactory::Init(int32_t, const std::string &)",
        "unitree_sdk2_cpp.channel.initialize_from_config": "ChannelFactory::Init(const std::string &)",
        "unitree_sdk2_cpp.channel.release": "ChannelFactory::Release()",
        "unitree_sdk2_cpp.channel.ChannelPublisher.__init__": "ChannelPublisher(const std::string &, type)",
        "unitree_sdk2_cpp.channel.ChannelPublisher.topic": "ChannelPublisher::topic() const",
        "unitree_sdk2_cpp.channel.ChannelPublisher.message_type_name": "ChannelPublisher::message_type_name() const",
        "unitree_sdk2_cpp.channel.ChannelPublisher.init_channel": "ChannelPublisher::init_channel()",
        "unitree_sdk2_cpp.channel.ChannelPublisher.close_channel": "ChannelPublisher::close_channel()",
        "unitree_sdk2_cpp.channel.ChannelPublisher.write": "ChannelPublisher::write(message, int64_t)",
        "unitree_sdk2_cpp.channel.ChannelSubscriber.__init__": "ChannelSubscriber(const std::string &, type, callback, int64_t)",
        "unitree_sdk2_cpp.channel.ChannelSubscriber.topic": "ChannelSubscriber::topic() const",
        "unitree_sdk2_cpp.channel.ChannelSubscriber.message_type_name": "ChannelSubscriber::message_type_name() const",
        "unitree_sdk2_cpp.channel.ChannelSubscriber.last_data_available_time": "ChannelSubscriber::last_data_available_time() const",
        "unitree_sdk2_cpp.channel.ChannelSubscriber.init_channel": "ChannelSubscriber::init_channel()",
        "unitree_sdk2_cpp.channel.ChannelSubscriber.close_channel": "ChannelSubscriber::close_channel()",
    }
    manifest_entries.extend(
        {
            "cpp_class": path.rsplit(".", 1)[0],
            "cpp_signature": signature,
            "python_path": path,
            "status": "AVAILABLE",
            "safety": "DDS_LIFECYCLE" if ".channel." in path else "READ_ONLY",
        }
        for path, signature in manual_paths.items()
    )

    robot_classes = [
        item
        for item in robot_inventory["classes"]
        if item["namespace"].startswith("unitree::robot")
    ]
    robot_enums = [
        item
        for item in robot_inventory["enums"]
        if item["namespace"].startswith("unitree::robot")
    ]
    by_namespace: dict[str, list[dict[str, Any]]] = defaultdict(list)
    enums_by_namespace: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in robot_classes:
        by_namespace[item["namespace"]].append(item)
    for item in robot_enums:
        enums_by_namespace[item["namespace"]].append(item)

    submodules = sorted(
        namespace.removeprefix("unitree::robot::")
        for namespace in by_namespace
        if namespace != "unitree::robot"
    )
    root_content = render_robot_module(
        "unitree::robot",
        by_namespace["unitree::robot"],
        enums_by_namespace["unitree::robot"],
        mapper,
        classifications,
        available_policy,
        available_classes,
        manifest_entries,
    )
    write_text(package / "robot" / "__init__.pyi", root_content)
    for name in submodules:
        namespace = f"unitree::robot::{name}"
        write_text(
            package / "robot" / f"{name}.pyi",
            render_robot_module(
                namespace,
                by_namespace[namespace],
                enums_by_namespace[namespace],
                mapper,
                classifications,
                available_policy,
                available_classes,
                manifest_entries,
            ),
        )

    write_text(package / "py.typed", "")
    status_counts = Counter(item["status"] for item in manifest_entries)
    manifest = {
        "schema_version": 1,
        "warning": (
            "SIGNATURE_ONLY APIs are design-time previews and are not guaranteed "
            "to exist in the current binary extension."
        ),
        "summary": {
            "idl_classes": sum(len(report["classes"]) for report in idl_reports),
            "idl_properties": sum(
                len(item["properties"])
                for report in idl_reports
                for item in report["classes"]
            ),
            "robot_classes": len(robot_classes),
            "robot_public_signatures": sum(
                len([c for c in item["constructors"] if c["access"] == "public"])
                + len([m for m in item["methods"] if m["access"] == "public"])
                for item in robot_classes
            ),
            "manifest_entries": len(manifest_entries),
            "status": dict(sorted(status_counts.items())),
        },
        "entries": sorted(
            manifest_entries,
            key=lambda item: (item["python_path"], item["cpp_signature"]),
        ),
    }
    (package / "api_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--idl-inventory", type=Path, required=True)
    parser.add_argument("--robot-inventory", type=Path, required=True)
    parser.add_argument("--classification", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--read-only-report", type=Path, required=True)
    parser.add_argument("--idl-report", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    manifest = generate(arguments)
    print(json.dumps(manifest["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
