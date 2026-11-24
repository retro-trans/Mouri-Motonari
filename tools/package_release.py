"""Release files for a build (same set as the other retro-trans PS1 releases).

    python tools/package_release.py 0.8.0

Reads the Japanese image (repository root) and the build
work/output/test/MouriMotonari-English-v<V>.bin (made with
`python tools/build.py --name MouriMotonari-English-v<V>`), and writes to work/release/v<V>/:
  MouriMotonari-English-v<V>.xdelta   VCDIFF patch (tools/vcdiff.py), decoded again from the
                                      source and checked against the target hash
  MouriMotonari-English-v<V>.cue      CUE naming the patched BIN
  README-v<V>.txt                     instructions and source / target hashes
  CHANGELOG-v<V>.txt                  CHANGELOG.md
  BUILD-MANIFEST.json, VALIDATION.json, SHA1SUMS-v<V>.txt, SHA256SUMS-v<V>.txt, SHA256SUMS.txt
work/release/ is not committed.
"""
import hashlib
import io
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vcdiff                   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'Mouri Motonari - Chikai no Sanshi (Japan).bin')
NAME = 'MouriMotonari-English-v%s'
REPO = 'https://github.com/retro-trans/Mouri-Motonari'
DISCORD = 'https://discord.gg/nZBZfTDfCP'


class _Sink(io.RawIOBase):
    """file-like that hashes what is written (the decoded target is never stored)"""
    def __init__(self):
        self.h = hashlib.sha256()
        self.n = 0

    def write(self, b):
        self.h.update(b)
        self.n += len(b)
        return len(b)


def hashes(data):
    return {'size': len(data), 'md5': hashlib.md5(data).hexdigest(),
            'sha1': hashlib.sha1(data).hexdigest(), 'sha256': hashlib.sha256(data).hexdigest()}


def readme(v, name, src, tgt):
    same = 'the same length as the original' if src['size'] == tgt['size'] else 'a different length'
    return """Mouri Motonari: Chikai no Sanshi English translation v{v}
{rule}

Game: Mouri Motonari: Chikai no Sanshi (PlayStation, Japan, Koei, SLPS-01285)

Patch: {name}.xdelta (xdelta3 / VCDIFF)

Source image (your own dump of the Japanese disc, raw single-track BIN, MODE2/2352)
  size    {s[size]} bytes
  MD5     {s[md5]}
  SHA-1   {s[sha1]}
  SHA-256 {s[sha256]}

Patched image (output)
  size    {t[size]} bytes
  SHA-256 {t[sha256]}

How to apply
  Retro Trans (https://github.com/retro-trans/retro-trans-tools), DeltaPatcher, or xdelta3:
    xdelta3 -d -s "Mouri Motonari - Chikai no Sanshi (Japan).bin" {name}.xdelta {name}.bin
  Keep checksum verification on. A CHD must be extracted to BIN/CUE first
  (chdman extractcd).
  The patched BIN has {same}: load it through
  {name}.cue (its FILE line names {name}.bin),
  or copy your own CUE and edit its FILE line.

Playing
  - Boot the patched image fresh; emulator save states keep the old executable and data.
    Memory-card saves work, including saves made with the Japanese game.
  - The story films keep the original Japanese voices with English subtitles.
  - L2 on the battle map shows or hides Endurance / SP bars under every unit.
  - Tested in DuckStation.

Known limits
  - No human proofreading yet. Film subtitles come from assisted transcripts of the
    Japanese voices; a human listening pass is outstanding.
  - No full playthrough yet: played by hand up to Episode 8.
  - The stylized title logo and the Eiketsuden series logo are kept in Japanese.
  - Real PlayStation hardware not tested.

This patch is free. Do not sell it or anything made with it.
Discord: {discord}
Source: {repo}
""".format(v=v, rule='=' * len('Mouri Motonari: Chikai no Sanshi English translation v' + v),
           name=name, s=src, t=tgt, same=same, discord=DISCORD, repo=REPO)


def main():
    v = sys.argv[1]
    name = NAME % v
    tgt_path = os.path.join(ROOT, 'work', 'output', 'test', name + '.bin')
    out = os.path.join(ROOT, 'work', 'release', 'v' + v)
    os.makedirs(out, exist_ok=True)
    src_b = open(SRC, 'rb').read()
    tgt_b = open(tgt_path, 'rb').read()
    src, tgt = hashes(src_b), hashes(tgt_b)
    print('making patch...')
    patch = vcdiff.make(src_b, tgt_b)
    sink = _Sink()
    vcdiff.apply(src_b, patch, sink)
    ok = sink.n == tgt['size'] and sink.h.hexdigest() == tgt['sha256']
    if not ok:
        raise SystemExit('patch does not reproduce the target')
    del tgt_b
    files = {}
    files[name + '.xdelta'] = patch
    files[name + '.cue'] = ('FILE "%s.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n'
                            % name).encode()
    files['README-v%s.txt' % v] = readme(v, name, src, tgt).encode()
    files['CHANGELOG-v%s.txt' % v] = open(os.path.join(ROOT, 'CHANGELOG.md'), 'rb').read()
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                         stderr=subprocess.DEVNULL).decode().strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    manifest = {
        'game_id': 'mouri-motonari-chikai-no-sanshi', 'game_name': 'Mouri Motonari: Chikai no Sanshi',
        'platform': 'PS1', 'version': v, 'source_commit': commit, 'schema_version': 1,
        'patches': [{
            'patch': name + '.xdelta', 'edition': 'original', 'language': 'en',
            'source_version': 'original', 'source_format': 'bin', 'target_format': 'bin',
            'source_sha256': src['sha256'], 'source_bytes': src['size'],
            'target_sha256': tgt['sha256'], 'target_bytes': tgt['size'],
            'patch_sha256': hashlib.sha256(patch).hexdigest(), 'patch_bytes': len(patch)}],
        'package_ids': [{'platform': 'PS1', 'kind': 'disc-id', 'id': 'SLPS-01285'}],
    }
    files['BUILD-MANIFEST.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    validation = {'schema_version': 1,
                  'manifest_sha256': hashlib.sha256(files['BUILD-MANIFEST.json']).hexdigest(),
                  'patches': [{'patch': name + '.xdelta', 'roundtrip_verified': ok,
                               'target_sha256': tgt['sha256']}]}
    files['VALIDATION.json'] = (json.dumps(validation, indent=2) + '\n').encode()
    files['SHA256SUMS.txt'] = ''.join('%s  %s\n' % (hashlib.sha256(files[f]).hexdigest(), f)
                                      for f in ('BUILD-MANIFEST.json', name + '.xdelta',
                                                'VALIDATION.json')).encode()
    listed = sorted(files)
    for algo, fn in (('sha1', 'SHA1SUMS-v%s.txt' % v), ('sha256', 'SHA256SUMS-v%s.txt' % v)):
        files[fn] = ''.join('%s  %s\n' % (hashlib.new(algo, files[f]).hexdigest(), f)
                            for f in listed).encode()
    for f, b in files.items():
        with open(os.path.join(out, f), 'wb') as fh:
            fh.write(b)
        print('%-40s %10d' % (f, len(b)))
    print('source sha256', src['sha256'])
    print('target sha256', tgt['sha256'], 'roundtrip ok')


if __name__ == '__main__':
    main()
