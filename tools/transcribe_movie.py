"""Transcribe the speech of a movie (STR) with Whisper (faster-whisper, GPU), Japanese.

Runs in a 64-bit Python with faster-whisper (the project's Python is 32-bit). This machine
already has one, set up for another project; override with WHISPER_PY / WHISPER_HF:
    <WHISPER_PY> tools/transcribe_movie.py MOVIE01 [--model large-v3] [--prompt "names ..."]

Input: work/source/movie/<name>.wav (16 kHz mono, from tools/movie.py audio).
Output: work/source/movie/<name>.transcript.json: [{start, end, text, avg_logprob, no_speech}]
"""
import glob
import json
import os
import sys
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WHISPER_HOME = os.environ.get('WHISPER_HF', r'E:\Projects\Gundam UC Climax\work\bin\whisper\hf')
os.environ.setdefault('HF_HOME', WHISPER_HOME)
site = os.path.join(os.path.dirname(sys.executable), '..', 'Lib', 'site-packages', 'nvidia')
for d in glob.glob(os.path.join(site, '*', 'bin')):
    os.add_dll_directory(os.path.abspath(d))
    os.environ['PATH'] = os.path.abspath(d) + os.pathsep + os.environ['PATH']
MOVIE = os.path.join(ROOT, 'work', 'source', 'movie')


def main(name, model_name='large-v3', prompt=None):
    import numpy as np
    from faster_whisper import WhisperModel
    w = wave.open(os.path.join(MOVIE, name + '.wav'))
    assert w.getframerate() == 16000 and w.getnchannels() == 1
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype('float32') / 32768
    model = WhisperModel(model_name, device='cuda', compute_type='float16')
    segs, _ = model.transcribe(audio, language='ja', beam_size=5, vad_filter=True,
                               condition_on_previous_text=False, temperature=0.0,
                               word_timestamps=True, initial_prompt=prompt)
    out = [{'start': round(s.start, 2), 'end': round(s.end, 2), 'text': s.text.strip(),
            'avg_logprob': round(s.avg_logprob, 3), 'no_speech': round(s.no_speech_prob, 3)}
           for s in segs]
    p = os.path.join(MOVIE, name + '.transcript.json')
    json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(len(out), 'segments ->', p)


if __name__ == '__main__':
    a = sys.argv[1:]
    m = a[a.index('--model') + 1] if '--model' in a else 'large-v3'
    pr = a[a.index('--prompt') + 1] if '--prompt' in a else None     # names, as one string
    main(a[0], m, pr)
