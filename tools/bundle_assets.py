#!/usr/bin/env python3
"""读写 Unity bundle 里的 TextAsset（热更程序集）。

来源：CesiumLoader 安卓工具链的 `tools/bundle_assets.py`（原样搬运，只加了 PEP 723 声明）。

**注意**：UnityPy 的 `TextAsset.m_Script` 会把内容当 UTF-8 字符串解码，
对二进制程序集是有损的（高位字节会被替换/丢失）。这里一律走原始对象数据
`get_raw_data()` / `set_raw_data()` 自己解析 `m_Name + m_Script`，保证字节一致。

    uv run tools/bundle_assets.py list      <bundle>
    uv run tools/bundle_assets.py extract   <bundle> <outdir>
    uv run tools/bundle_assets.py roundtrip <bundle> <outbundle>
    uv run tools/bundle_assets.py replace   <bundle> <assetName> <newfile> <outbundle>
    uv run tools/bundle_assets.py verify    <bundle> <assetName> <file>
"""

# /// script
# requires-python = ">=3.10"
# dependencies = ["UnityPy==1.25.3"]
# ///

from __future__ import annotations

import argparse
import hashlib
import os
import struct
import sys

import UnityPy


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_text_asset(raw: bytes) -> tuple[str, bytes]:
    """TextAsset 原始布局：m_Name(string) + 对齐 + m_Script(string) + 对齐。"""
    offset = 0
    (name_len,) = struct.unpack_from("<i", raw, offset)
    offset += 4
    name = raw[offset:offset + name_len].decode("utf-8", "replace")
    offset += name_len
    while offset % 4:
        offset += 1
    (script_len,) = struct.unpack_from("<i", raw, offset)
    offset += 4
    script = raw[offset:offset + script_len]
    return name, script


def build_text_asset(name: str, script: bytes) -> bytes:
    out = bytearray()
    name_bytes = name.encode("utf-8")
    out += struct.pack("<i", len(name_bytes)) + name_bytes
    while len(out) % 4:
        out.append(0)
    out += struct.pack("<i", len(script)) + script
    while len(out) % 4:
        out.append(0)
    return bytes(out)


def objects(env):
    for obj in env.objects:
        if obj.type.name == "TextAsset":
            yield obj


def read_all(bundle: str) -> dict[str, bytes]:
    env = UnityPy.load(bundle)
    result: dict[str, bytes] = {}
    for obj in objects(env):
        name, script = parse_text_asset(obj.get_raw_data())
        result[name] = script
    return result


def cmd_list(bundle: str) -> int:
    for name, script in read_all(bundle).items():
        kind = ".NET" if script[:2] == b"MZ" else "?"
        print(f"{name:<45} {len(script):>10} B  {kind}  sha256={sha(script)}")
    return 0


def cmd_extract(bundle: str, outdir: str) -> int:
    os.makedirs(outdir, exist_ok=True)
    items = read_all(bundle)
    for name, script in items.items():
        with open(os.path.join(outdir, name), "wb") as handle:
            handle.write(script)
    print(f"导出 {len(items)} 个 TextAsset -> {outdir}")
    return 0


def cmd_roundtrip(bundle: str, out_bundle: str) -> int:
    env = UnityPy.load(bundle)
    data = env.file.save(packer="original")
    with open(out_bundle, "wb") as handle:
        handle.write(data)

    before = read_all(bundle)
    after = read_all(out_bundle)
    same = before == after
    for name in sorted(before):
        if before.get(name) != after.get(name):
            print(f"  差异: {name}")
    print(f"资源一致性: {'一致' if same else '不一致'}（{len(before)} 个 TextAsset）")
    print(f"原始 {os.path.getsize(bundle)} B -> 重写 {os.path.getsize(out_bundle)} B  sha256={sha(open(out_bundle,'rb').read())}")
    return 0 if same else 1


def cmd_replace(bundle: str, asset_name: str, new_file: str, out_bundle: str) -> int:
    with open(new_file, "rb") as handle:
        replacement = handle.read()

    env = UnityPy.load(bundle)
    target = None
    for obj in objects(env):
        name, _ = parse_text_asset(obj.get_raw_data())
        if name == asset_name:
            target = obj
            break
    if target is None:
        print(f"找不到 TextAsset: {asset_name}", file=sys.stderr)
        return 1

    before_len = len(parse_text_asset(target.get_raw_data())[1])
    target.set_raw_data(build_text_asset(asset_name, replacement))

    data = env.file.save(packer="original")
    with open(out_bundle, "wb") as handle:
        handle.write(data)

    after = read_all(out_bundle).get(asset_name)
    ok = after == replacement
    print(f"{asset_name}: {before_len} B -> {len(replacement)} B  写入{'成功' if ok else '失败'}")
    print(f"包体 {os.path.getsize(bundle)} B -> {os.path.getsize(out_bundle)} B  sha256={sha(open(out_bundle,'rb').read())}")
    return 0 if ok else 1


def cmd_verify(bundle: str, asset_name: str, expected_file: str) -> int:
    with open(expected_file, "rb") as handle:
        expected = handle.read()
    actual = read_all(bundle).get(asset_name)
    ok = actual == expected
    print(f"{asset_name}: {'一致' if ok else '不一致'}  bundle={len(actual) if actual else 0} B  file={len(expected)} B")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list"); p.add_argument("bundle")
    p = sub.add_parser("extract"); p.add_argument("bundle"); p.add_argument("outdir")
    p = sub.add_parser("roundtrip"); p.add_argument("bundle"); p.add_argument("outbundle")
    p = sub.add_parser("replace"); p.add_argument("bundle"); p.add_argument("asset"); p.add_argument("newfile"); p.add_argument("outbundle")
    p = sub.add_parser("verify"); p.add_argument("bundle"); p.add_argument("asset"); p.add_argument("file")

    args = parser.parse_args()
    if args.command == "list":
        return cmd_list(args.bundle)
    if args.command == "extract":
        return cmd_extract(args.bundle, args.outdir)
    if args.command == "roundtrip":
        return cmd_roundtrip(args.bundle, args.outbundle)
    if args.command == "replace":
        return cmd_replace(args.bundle, args.asset, args.newfile, args.outbundle)
    return cmd_verify(args.bundle, args.asset, args.file)


if __name__ == "__main__":
    sys.exit(main())
