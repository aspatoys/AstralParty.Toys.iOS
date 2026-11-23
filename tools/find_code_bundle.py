"""Resolve an Addressables key to the bundle file that carries it, and report
whether that bundle is shipped in-app (RuntimePath) or downloaded (WebServerConfig).

Usage: python find_code_bundle.py <catalog.json> <asset-key> [<asset-key> ...]
       python find_code_bundle.py <catalog.json> --key <bundleKey>
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
    if t == 0:
        ln = i32(b, off)
        return b[off + 4:off + 4 + ln].decode('ascii', 'ignore')
    if t == 1:
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


class Cat:
    def __init__(self, path):
        d = json.load(open(path, encoding='utf-8'))
        self.d = d
        self.internal = d['m_InternalIds']
        self.providers = d['m_ProviderIds']
        self.rtypes = d.get('m_resourceTypes', [])
        key_data = base64.b64decode(d['m_KeyDataString'])
        bucket_data = base64.b64decode(d['m_BucketDataString'])
        entry_data = base64.b64decode(d['m_EntryDataString'])

        nb = i32(bucket_data, 0)
        idx = 4
        self.buckets = []
        for _ in range(nb):
            off = i32(bucket_data, idx); idx += 4
            ec = i32(bucket_data, idx); idx += 4
            ents = [i32(bucket_data, idx + 4 * j) for j in range(ec)]
            idx += 4 * ec
            self.buckets.append((off, ents))

        self.keys = [read_object(key_data, self.buckets[i][0]) for i in range(nb)]

        ne = i32(entry_data, 0)
        idx = 4
        self.entries = []
        for _ in range(ne):
            self.entries.append(struct.unpack_from('<7i', entry_data, idx))
            idx += 28

        self.key_index = {}
        for i, k in enumerate(self.keys):
            self.key_index.setdefault(k, []).append(i)

    def rtype(self, i):
        if 0 <= i < len(self.rtypes):
            r = self.rtypes[i]
            return f"{r.get('m_AssemblyName','?')}::{r.get('m_ClassName','?')}"
        return f"<bad rtype {i}>"

    def provider(self, i):
        if 0 <= i < len(self.providers):
            return self.providers[i].split('.')[-1]
        return f"<bad prov {i}>"

    def show(self, key):
        idxs = self.key_index.get(key)
        if not idxs:
            print(f"  key {key!r}: NOT FOUND")
            return
        for ki in idxs:
            off, ents = self.buckets[ki]
            print(f"  key {key!r} (keyIndex={ki}) -> {len(ents)} entr(ies)")
            for ei in ents:
                e = self.entries[ei]
                iid = self.internal[e[0]] if 0 <= e[0] < len(self.internal) else f"<bad {e[0]}>"
                kind = ('REMOTE' if 'WebServerConfig' in iid
                        else 'LOCAL' if 'RuntimePath' in iid else 'OTHER')
                print(f"    entry#{ei}: [{kind}] provider={self.provider(e[1])} "
                      f"type={self.rtype(e[6])}")
                print(f"        internalId[{e[0]}] = {iid}")
                dep = e[2]
                if 0 <= dep < len(self.keys):
                    dk = self.keys[dep]
                    print(f"        dependencyKey[{dep}] = {dk!r}")
                    didxs = self.key_index.get(dk, [])
                    for dki in didxs:
                        for dei in self.buckets[dki][1]:
                            de = self.entries[dei]
                            diid = (self.internal[de[0]]
                                    if 0 <= de[0] < len(self.internal) else f"<bad {de[0]}>")
                            dkind = ('REMOTE' if 'WebServerConfig' in diid
                                     else 'LOCAL' if 'RuntimePath' in diid else 'OTHER')
                            print(f"          -> bundle entry#{dei}: [{dkind}] {diid}")
                else:
                    print(f"        dependencyKey[{dep}] = <out of range>")


def main():
    path = sys.argv[1]
    args = sys.argv[2:]
    c = Cat(path)
    print(f"### {path}")
    print(f"  internalIds={len(c.internal)} keys={len(c.keys)} entries={len(c.entries)}")
    if args and args[0] == '--key':
        c.show(args[1])
        return
    for k in args:
        c.show(k)


if __name__ == '__main__':
    main()
