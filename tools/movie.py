"""Movies (MOVIE/MOVIEnn.STR: MDEC video 320x240 15 fps + XA audio 37.8 kHz stereo).

    python tools/movie.py raw MOVIE01       raw 2352-byte sectors from the original disc
    python tools/movie.py audio MOVIE01     16 kHz mono WAV for tools/transcribe_movie.py
    python tools/movie.py frames MOVIE01    every frame as PNG (jPSXdec), NNNN.png = header frame
    python tools/movie.py patch MOVIE01     re-encode the frames edited by tools/movie_edit.py
                                            into a copy of the raw sectors (work/output/movie)
    python tools/movie.py preview MOVIE01   MP4 of the patched movie (work/output/movie)

Source files go to work/source/movie/. ffmpeg (demuxer psxstr) and jPSXdec need the raw
sectors: the ISO copy in work/source/disc has lost the sector subheaders that tell video and
audio sectors apart. jPSXdec (work/bin/jpsxdec, v2.0, from github.com/m35/jpsxdec) replaces
frames in place: only the macroblocks that changed are re-encoded, at the lowest
quantization scale that fits the frame's sectors (replace.log lists the scale per frame).
tools/build.py writes the patched sectors of every work/output/movie/<name>.raw over the
movie on the disc (same LBA, same size).
"""
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_BIN = os.path.join(ROOT, 'Mouri Motonari - Chikai no Sanshi (Japan).bin')
FILELIST = os.path.join(ROOT, 'work', 'source', 'disc', '_filelist.json')
SRC = os.path.join(ROOT, 'work', 'source', 'movie')
OUT = os.path.join(ROOT, 'work', 'output', 'movie')
JPSXDEC = os.path.join(ROOT, 'work', 'bin', 'jpsxdec', 'app', 'jpsxdec_v2.0', 'jpsxdec.jar')
SECTOR = 2352


def entry(name):
    d = json.load(open(FILELIST))
    for v in (d.values() if isinstance(d, dict) else d):
        if v['path'] == 'MOVIE/%s.STR' % name:
            return v
    raise KeyError(name)


def raw_path(name):
    p = os.path.join(SRC, name + '.raw')
    if not os.path.exists(p):
        v = entry(name)
        n = (v['size'] + 2047) // 2048
        with open(SRC_BIN, 'rb') as f:
            f.seek(v['lba'] * SECTOR)
            data = f.read(n * SECTOR)
        os.makedirs(SRC, exist_ok=True)
        open(p, 'wb').write(data)
    return p


def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error', '-y'] + list(args), check=True)


def jpsxdec(cwd, *args):
    r = subprocess.run(['java', '-jar', JPSXDEC] + list(args), cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stdout + r.stderr)
    return r.stdout


def index(cwd, raw):
    idx = os.path.join(cwd, os.path.basename(raw)[:-4] + '.idx')
    if not os.path.exists(idx):
        jpsxdec(cwd, '-f', os.path.basename(raw), '-x', os.path.basename(idx))
    return os.path.basename(idx)


def frames(name):
    raw = raw_path(name)
    d = os.path.join(SRC, name)
    os.makedirs(d, exist_ok=True)
    idx = index(SRC, raw)
    jpsxdec(SRC, '-x', idx, '-i', '0', '-vf', 'png', '-num', 'Header', '-noaud', '-dir', name)
    for f in os.listdir(d):
        m = re.search(r'#(\d+)\]\.png$', f)
        if m:
            os.replace(os.path.join(d, f), os.path.join(d, '%04d.png' % int(m.group(1))))
    print(d, len(os.listdir(d)), 'frames')


def patch(name):
    """copy the original raw sectors and let jPSXdec re-encode the edited frames into it"""
    ed = os.path.join(OUT, name)
    out = os.path.join(OUT, name + '.raw')
    shutil.copyfile(raw_path(name), out)
    work = ed                                      # replace.xml names the PNGs relative to it
    for f in os.listdir(work):
        if f.endswith('.log') or f.endswith('.idx'):
            os.remove(os.path.join(work, f))
    shutil.copyfile(out, os.path.join(work, name + '.raw'))
    idx = index(work, os.path.join(work, name + '.raw'))
    jpsxdec(work, '-x', idx, '-i', '0', '-replaceframes', 'replace.xml')
    shutil.move(os.path.join(work, name + '.raw'), out)
    os.remove(os.path.join(work, idx))
    log = open(os.path.join(work, 'replace.log'), encoding='utf-8', errors='replace').read()
    qs = {}
    cur = None
    for line in log.splitlines():
        m = re.search(r'Replacing frame (\d+)', line)
        if m:
            cur = int(m.group(1)) + 1
        m = re.search(r'Trying quantization scale (\d+)', line)
        if m and cur:
            qs[cur] = int(m.group(1))
    bad = [line for line in log.splitlines() if 'SEVERE' in line or 'WARNING' in line]
    hist = {}
    for q in qs.values():
        hist[q] = hist.get(q, 0) + 1
    print('%s: %d frames re-encoded; quantization scale: %s' % (
        out, len(qs), ', '.join('%d x%d' % kv for kv in sorted(hist.items()))))
    worst = sorted(qs.items(), key=lambda kv: -kv[1])[:8]
    print('coarsest:', ', '.join('frame %d q%d' % kv for kv in worst))
    for line in bad[:20]:
        print(line)
    json.dump(qs, open(os.path.join(work, 'qscale.json'), 'w'))


def preview(name):
    """MP4 of the patched movie, decoded by jPSXdec (ffmpeg's MDEC decoder is less exact and
    shows grey blocks that the console does not)"""
    work = os.path.join(OUT, 'preview')
    os.makedirs(work, exist_ok=True)
    shutil.copyfile(os.path.join(OUT, name + '.raw'), os.path.join(work, name + '.raw'))
    idx = index(work, os.path.join(work, name + '.raw'))
    jpsxdec(work, '-x', idx, '-i', '0', '-vf', 'avi:rgb', '-q', 'psx', '-dir', '.')
    avi = [f for f in os.listdir(work) if f.endswith('.avi')][0]
    out = os.path.join(OUT, name + '.mp4')
    ffmpeg('-i', os.path.join(work, avi), '-vf', 'scale=640:480:flags=neighbor', '-c:v', 'libx264',
           '-crf', '16', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', out)
    shutil.rmtree(work)
    print(out)


def main():
    cmd, name = sys.argv[1], sys.argv[2]
    if cmd == 'raw':
        print(raw_path(name))
    elif cmd == 'audio':
        out = os.path.join(SRC, name + '.wav')
        ffmpeg('-f', 'psxstr', '-i', raw_path(name), '-vn', '-ac', '1', '-ar', '16000', out)
        print(out)
    elif cmd == 'frames':
        frames(name)
    elif cmd == 'patch':
        patch(name)
    elif cmd == 'preview':
        preview(name)


if __name__ == '__main__':
    main()
