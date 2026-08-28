# Unitree SDK2 C++ signature-preview stubs

Install the wheel to enable completion and static type checking for
`unitree_sdk2_cpp` before the Linux binary extension is available.

```bash
python -m pip install unitree_sdk2_cpp_stubs-0.1.2-py3-none-any.whl
```

`AVAILABLE` signatures exist in the current binding source. `SIGNATURE_ONLY`
signatures are design-time previews and may include hardware or motion APIs.
They intentionally do not provide a runtime implementation. See the packaged
`api_manifest.json` for availability and safety metadata.

This is a stub-only package: it enables IDE completion and Mypy/Pyright, but it
does not make `import unitree_sdk2_cpp` executable without the Linux extension.
Installing the real extension alongside this wheel supplies the runtime.

The repository also provides a [Chinese beginner guide](../docs/BEGINNER_GUIDE_ZH.md)
and an exhaustive [Chinese API reference](../docs/API_REFERENCE_ZH.md) covering
every generated function, overload, property, parameter, and return value.
