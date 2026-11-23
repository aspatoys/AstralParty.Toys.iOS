"""Decode a Unity Addressables catalog JSON (m_*DataString blobs).

Usage:
  python decode_catalog.py <catalog.json> [--grep SUBSTR] [--dll] [--key KEY] [--summary]

Prints remote/local split of m_InternalIds and the key -> internalId mapping.
"""
import base64
import json
import struct
import sys


def i32(b, o):
    return struct.unpack_from('<i', b, o)[0]


def read_object(b, off):
    t = b[off]
    off += 1
    if t == 0:  # AsciiString
        ln = i32(b, off)
        return b[off + 4:off + 4 + ln].decode('ascii', 'ignore')
    if t == 1:  # UnicodeString
        ln = i32(b, off)
        return b[off + 4:off + 4 + ln * 2].decode('utf-16-le', 'ignore')
    if t == 2:
        return struct.unpack_from('<H', b, off)[0]
    if t == 3:
        return struct.unpack_from('<I', b, off)[0]
    if t == 4:
        return i32(b, off)
    if t == 5:
        return "Hash128:" + b[off:off + 16].hex()
    return f"<type{t}>"


def load(path):
    d = json.load(open(path, encoding='utf-8'))
    internal = d['m_InternalIds']
    prefixes = d.get('m_InternalIdPrefixes') or []
    key_data = base64.b64decode(d['m_KeyDataString'])
    bucket_data = base64.b64decode(d['m_BucketDataString'])
    entry_data = base64.b64decode(d['m_EntryDataString'])

    nb = i32(bucket_data, 0)
    idx = 4
    buckets = []
    for _ in range(nb):
        off = i32(bucket_data, idx)
        idx += 4
        ec = i32(bucket_data, idx)
        idx += 4
        ents = [i32(bucket_data, idx + 4 * j) for j in range(ec)]
        idx += 4 * ec
        buckets.append((off, ents))

    keys = [read_object(key_data, buckets[i][0]) for i in range(nb)]

    ne = i32(entry_data, 0)
    idx = 4
    entries = []
    for _ in range(ne):
        entries.append(struct.unpack_from('<7i', entry_data, idx))
        idx += 28

    return d, internal, prefixes, keys, buckets, entries


def resolve_internal(internal, prefixes, i):
    if i < 0 or i >= len(internal):
        return f"<bad index {i}>"
    v = internal[i]
    # Newer catalogs may store "prefixIndex:rest"; handle both shapes.
    if prefixes and isinstance(v, str) and ':' in v and v.split(':', 1)[0].isdigit():
        p, rest = v.split(':', 1)
        pi = int(p)
        if 0 <= pi < len(prefixes):
            return prefixes[pi] + rest
    return v


def main():
    path = sys.argv[1]
    argv = sys.argv[2:]
    grep = None
    want_dll = False
    want_key = None
    if '--grep' in argv:
        grep = argv[argv.index('--grep') + 1]
    if '--dll' in argv:
        want_dll = True
    if '--key' in argv:
        want_key = argv[argv.index('--key') + 1]

    d, internal, prefixes, keys, buckets, entries = load(path)

    remote = [x for x in internal if 'WebServerConfig' in x]
    local = [x for x in internal if 'RuntimePath' in x]
    other = [x for x in internal if 'WebServerConfig' not in x and 'RuntimePath' not in x]

    print(f"file            : {path}")
    print(f"buildResultHash : {d.get('m_BuildResultHash')}")
    print(f"locatorId       : {d.get('m_LocatorId')}")
    print(f"internalIds     : {len(internal)}  remote={len(remote)} local={len(local)} other={len(other)}")
    print(f"prefixes        : {len(prefixes)} {prefixes[:3] if prefixes else ''}")
    print(f"keys            : {len(keys)}   entries: {len(entries)}")
    if other:
        print("  non-standard internalIds (first 10):")
        for x in other[:10]:
            print(f"    {x}")
    # distinct local platform dirs
    plat = sorted({x.split('}/')[1].split('/')[0] for x in local if '}/' in x})
    print(f"local platform dirs: {plat}")

    # key -> internalId map
    print("\n=== dll / assembly keys ===" if want_dll else "\n=== matching keys ===")
    shown = 0
    for bi, (off, ents) in enumerate(buckets):
        k = keys[bi]
        if not isinstance(k, str):
            continue
        if want_dll:
            if not k.lower().endswith('.dll'):
                continue
        elif want_key is not None:
            if k != want_key:
                continue
        elif grep is not None:
            if grep.lower() not in k.lower():
                continue
        else:
            continue
        for ei in ents:
            e = entries[ei]
            iid = resolve_internal(internal, prefixes, e[0])
            kind = 'REMOTE' if 'WebServerConfig' in iid else ('LOCAL' if 'RuntimePath' in iid else 'OTHER')
            print(f"[{kind}] {k}\n        loc={iid}")
            shown += 1
    if shown == 0:
        print("  (none)")


if __name__ == '__main__':
    main()
