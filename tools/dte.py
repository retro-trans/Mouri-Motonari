"""Dictionary compression for English dialogue (scripts must fit the 0x18000-byte
script buffer at 0x801A8000).

Bytes 0xA0-0xDF (half-width katakana, never used by the script text copier
0x800207B4) stand for up to 64 dictionary strings; the copier hook in
tools/vwf.py expands them. Only dialogue bodies are encoded: '&' speaker lines
(strcmp lookup), captions (box sized by byte count) and choices stay plain.

The dictionary is chosen greedily from the current translation (score =
occurrences x bytes saved, recounted after each pick) and cached by content hash.
"""
import collections
import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, 'work', 'source', 'dte_cache.json')
BASE, COUNT = 0xA0, 64
MAXLEN = 8


def _bodies(texts):
    for t in texts:
        for line in t.split('\n'):
            if line and not line.startswith('&'):
                yield line


def build_dict(texts):
    texts = list(texts)
    key = hashlib.sha1('\0'.join(texts).encode('utf-8')).hexdigest()
    try:
        c = json.load(open(CACHE))
        if c.get('key') == key:
            return [s.encode('latin1') for s in c['dict']]
    except (OSError, ValueError):
        pass
    lines = [l.encode('ascii') for l in _bodies(texts)]
    words = []
    for k in range(COUNT):
        cnt = collections.Counter()
        for l in lines:
            n = len(l)
            for ln in range(2, MAXLEN + 1):
                for i in range(n - ln + 1):
                    s = l[i:i + ln]
                    if max(s) < 0x80:
                        cnt[s] += 1
        if not cnt:
            break
        best = max(cnt, key=lambda s: cnt[s] * (len(s) - 1))
        words.append(best)
        code = bytes((BASE + k,))
        lines = [l.replace(best, code) for l in lines]
    json.dump({'key': key, 'dict': [w.decode('latin1') for w in words]}, open(CACHE, 'w'))
    return words


def encode(text, words):
    """Encode the body lines of a laid-out dialogue text (str) -> bytes."""
    out = []
    for line in text.split('\n'):
        b = line.encode('cp932')
        if line and not line.startswith('&'):
            for k, w in enumerate(words):        # same order as chosen
                b = b.replace(w, bytes((BASE + k,)))
        out.append(b)
    return b'\n'.join(out)


def decode(b, words):
    out = bytearray()
    for c in b:
        out += words[c - BASE] if BASE <= c < BASE + len(words) else bytes((c,))
    return bytes(out)


def blob(words):
    """u16 offsets[64] + NUL-terminated strings."""
    idx, strs = bytearray(), bytearray()
    for k in range(COUNT):
        w = words[k] if k < len(words) else b''
        idx += (2 * COUNT + len(strs)).to_bytes(2, 'little')
        strs += w + b'\0'
    return bytes(idx + strs)
