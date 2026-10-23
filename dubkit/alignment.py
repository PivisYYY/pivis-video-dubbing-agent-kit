from __future__ import annotations
import math
import re
import unicodedata
from .common import QualityError


def normalized(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKC', text).casefold() if c.isalnum())


def words_from_asr(asr: dict) -> list[dict]:
    words = [w for seg in asr.get('segments', []) for w in seg.get('words', []) if w.get('word', '').strip()]
    if not words:
        raise QualityError('ASR returned no word timestamps')
    previous = -1.0
    for word in words:
        start, end = float(word['start']), float(word['end'])
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end < start or start < previous - 0.03:
            raise QualityError('Invalid or unordered ASR word timestamps')
        previous = start
    return words


def source_units(asr: dict) -> list[dict]:
    words = words_from_asr(asr)
    units, current = [], []
    def flush():
        if not current:
            return
        text = ' '.join(w['word'].strip() for w in current)
        text = re.sub(r'\s+([,.;:!?])', r'\1', text)
        units.append({'id': f'u{len(units)+1:04}', 'start': float(current[0]['start']),
                      'end': float(current[-1]['end']), 'en': text, 'source_words': [dict(w) for w in current]})
        current.clear()
    for word in words:
        current.append(word)
        # Linguistic sentence boundaries, never split merely because of an ASR segment or a gap.
        if re.search(r'[.!?]["\u201d\u2019]*$', word['word'].strip()):
            flush()
    flush()
    if not units:
        raise QualityError('No complete source speech units')
    for unit in units:
        if unit['end'] <= unit['start']:
            raise QualityError('Nonpositive source speech duration')
        if len(unit['en']) > 1600:
            raise QualityError('Source sentence too long; supply reviewed sentence boundaries')
    return units


def align_phrases(phrases: list[dict], asr: dict, *, offset: float, wav_duration: float) -> list[dict]:
    words = words_from_asr(asr)
    expected = normalized(''.join(p['zh'] for p in phrases))
    observed = normalized(''.join(w['word'] for w in words))
    if not expected or expected != observed:
        raise QualityError('Chinese audio read-back differs from requested speech; inspect expected text and saved independent ASR, do not weaken the gate')
    boundaries = []
    for word in words:
        start, end = float(word['start']), float(word['end'])
        if end > wav_duration + 0.15:
            raise QualityError('ASR word timestamp exceeds final audio duration')
        # Every character points to an actual ASR WORD boundary. No uniform/proportional timing.
        boundaries.extend([(start, min(end, wav_duration))] * len(normalized(word['word'])))
    cues, cursor = [], 0
    for phrase in phrases:
        size = len(normalized(phrase['zh']))
        if not size:
            raise QualityError('Punctuation-only subtitle')
        first, last = boundaries[cursor], boundaries[cursor + size - 1]
        start, end = offset + first[0], offset + last[1]
        if end <= start or (cues and start < cues[-1]['end'] - 0.03):
            raise QualityError('Subtitle semantic boundary splits an ASR word; revise the phrase boundary')
        cues.append({'start': start, 'end': end, 'zh': phrase['zh'], 'en': phrase['en'],
                     'alignment_method': 'exact_text_match_to_final_chinese_asr_word_boundaries'})
        cursor += size
    return cues


def timestamp(value: float, ass=False) -> str:
    ticks = round(value * (100 if ass else 1000))
    per = 100 if ass else 1000
    hour, ticks = divmod(ticks, 3600 * per)
    minute, ticks = divmod(ticks, 60 * per)
    second, sub = divmod(ticks, per)
    if ass:
        return f'{hour}:{minute:02}:{second:02}.{sub:02}'
    return f'{hour:02}:{minute:02}:{second:02},{sub:03}'


def srt(cues, language):
    return ''.join(f'{i}\n{timestamp(c["start"])} --> {timestamp(c["end"])}\n{c[language]}\n\n' for i, c in enumerate(cues, 1))


def _escape_ass(text):
    return text.replace('\\', '＼').replace('{', '｛').replace('}', '｝').replace('\r', '').replace('\n', ' ')


def ass_subtitles(cues, width, height):
    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Chinese,PingFang SC,36,&H00FFFFFF,&H000000FF,&H00101010,&H90000000,0,0,0,0,100,100,0,0,1,2,0,2,35,35,65,1
Style: English,Arial,23,&H00E6E6E6,&H000000FF,&H00101010,&H90000000,0,0,0,0,100,100,0,0,1,1.5,0,2,35,35,30,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    lines = [header]
    for cue in cues:
        for language, style, size in [('zh', 'Chinese', 36), ('en', 'English', 23)]:
            text = _escape_ass(cue[language])
            estimated_width = sum(1.0 if unicodedata.east_asian_width(c) in ('W', 'F') else 0.6 for c in text) * size
            factor = min(1.0, (width - 80) / max(1.0, estimated_width))
            font_size = size * factor
            if font_size < (18 if language == 'zh' else 12):
                raise QualityError('Subtitle would become unreadably small; revise semantic phrase boundaries')
            prefix = '{\\fs' + f'{font_size:.1f}' + '}'
            lines.append(f'Dialogue: 0,{timestamp(cue["start"], True)},{timestamp(cue["end"], True)},{style},,0,0,0,,{prefix}{text}\n')
    return ''.join(lines)
