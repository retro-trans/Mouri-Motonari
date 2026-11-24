"""Re-transcribe part of a movie's speech (Whisper, Japanese) with other settings.

Runs in the Whisper Python (see tools/transcribe_movie.py):
    <WHISPER_PY> tools/transcribe_clip.py MOVIE04 32.5 62 [--prompt "..."] [--vad]

Prints the segments (times from the start of the film) with their words; writes nothing.
Used where the full-film pass merged music into a long garbled segment.
"""
import os
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import transcribe_movie  # noqa: E402  (sets up HF_HOME and the CUDA DLL paths)


def main():
    import numpy as np
    from faster_whisper import WhisperModel
    a = sys.argv[1:]
    name, t0, t1 = a[0], float(a[1]), float(a[2])
    prompt = a[a.index('--prompt') + 1] if '--prompt' in a else None
    w = wave.open(os.path.join(transcribe_movie.MOVIE, name + '.wav'))
    rate = w.getframerate()
    w.setpos(int(t0 * rate))
    pcm = w.readframes(int((t1 - t0) * rate))
    audio = np.frombuffer(pcm, dtype='<i2').astype('float32') / 32768
    model = WhisperModel('large-v3', device='cuda', compute_type='float16')
    for temp in (0.0,):
        segs, _ = model.transcribe(audio, language='ja', beam_size=5, vad_filter='--vad' in a,
                                   condition_on_previous_text=False, temperature=temp,
                                   word_timestamps=True, initial_prompt=prompt)
        for s in segs:
            print('%6.2f-%6.2f p=%5.2f ns=%.2f %s' % (s.start + t0, s.end + t0, s.avg_logprob,
                                                     s.no_speech_prob, s.text.strip()))
            print('        ' + ' '.join('%s@%.1f' % (x.word, x.start + t0) for x in (s.words or [])))


if __name__ == '__main__':
    main()
