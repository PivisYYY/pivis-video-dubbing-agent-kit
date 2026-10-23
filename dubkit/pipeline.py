from __future__ import annotations
from contextlib import contextmanager
import fcntl
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
from urllib.parse import urlsplit, parse_qsl
import wave

from . import __version__
from .common import PipelineError, QualityError, command, digest, load, object_digest, probe, save
from .alignment import source_units, align_phrases, ass_subtitles, srt
from . import llm


@contextmanager
def job_lock(job: Path):
    job.mkdir(parents=True, exist_ok=True)
    with (job / '.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise PipelineError('This job is already active') from None
        yield


def _artifacts(job, names):
    return {name: digest(job / name) for name in names}


def _stage(job, state, name, key, outputs, execute):
    old = state.setdefault('stages', {}).get(name)
    signature = object_digest(key)
    if old and old.get('key') == signature:
        expected = old.get('outputs', {})
        if expected and all((job / path).is_file() and digest(job / path) == sha for path, sha in expected.items()):
            return False
        raise QualityError(f'Cached {name} output is missing or changed; inspect the job, do not silently reuse it')
    state.update(status='RUNNING', active_stage=name)
    save(job / 'state.json', state)
    execute()
    state['stages'][name] = {'key': signature, 'outputs': _artifacts(job, outputs)}
    save(job / 'state.json', state)
    return True


def _prepare_source(job, input_arg, sample_seconds):
    source = job / 'original.mp4'
    parsed = urlsplit(input_arg)
    if parsed.scheme in ('http', 'https'):
        credential_keys = ('token', 'secret', 'password', 'signature', 'credential', 'api_key', 'authorization')
        if parsed.username or parsed.password or any(any(word in key.casefold() for word in credential_keys) for key, _ in parse_qsl(parsed.query)):
            raise PipelineError('Credential-bearing or signed source URLs are not accepted; download privately then use a local file')
        if not shutil.which('yt-dlp'):
            raise PipelineError('URL input needs yt-dlp; install it in the project environment after authorization')
        command(['yt-dlp', '--no-playlist', '--no-write-info-json', '--no-write-thumbnail',
                 '--merge-output-format', 'mp4', '-f', 'bv*[height<=1080]+ba/b', '-o', str(source), input_arg], log=job / 'source.log')
    else:
        path = Path(input_arg).expanduser().resolve()
        if not path.is_file() or path == source.resolve():
            raise PipelineError('Input must be an existing independent media file')
        shutil.copyfile(path, source)
    info = probe(source)
    types = {x.get('codec_type') for x in info['streams']}
    if not {'audio', 'video'} <= types:
        raise QualityError('Source must include both video and audio')
    args = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', source]
    if sample_seconds is not None:
        args += ['-t', str(sample_seconds)]
    args += ['-map', '0:v:0', '-map', '0:a:0', '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
             '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-map_metadata', '-1', '-movflags', '+faststart', job / 'source.mp4']
    command(args, log=job / 'source.log')
    command(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', job / 'source.mp4',
             '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', job / 'source.wav'], log=job / 'source.log')
    actual = probe(job / 'source.mp4')
    save(job / 'source.json', {'duration_s': float(actual['format']['duration']), 'original_sha256': digest(source),
                              'source_sha256': digest(job / 'source.mp4'), 'sample_seconds': sample_seconds,
                              'source_kind': 'url' if parsed.scheme in ('http', 'https') else 'local_file'})


def _speech_model_keys(options):
    from .models import load_registry
    registry = load_registry()
    tts_alias = 'tts' if options.get('ref_audio') else 'custom_tts'
    return {alias: {'repo_id': registry[alias]['repo_id'], 'revision': registry[alias]['revision']}
            for alias in ('asr', tts_alias)}


def generation_contract(options):
    ref_path = options.get('ref_audio')
    ref_text = options.get('ref_text')
    return {'package_version': __version__, 'models': _speech_model_keys(options),
            'llm_model': options['llm_model'], 'llm_url': options['llm_url'],
            'speaker': options.get('voice', 'Vivian'), 'temperature': 0.3,
            'ref_audio_sha256': digest(Path(ref_path)) if ref_path else None,
            'ref_text_sha256': object_digest(ref_text) if ref_text else None,
            'source_volume': 0.08, 'max_atempo': 1.1, 'alignment': 'strict_final_chinese_asr_words',
            'burn_subtitles': options.get('burn_subtitles', False)}


def _input_identity(value):
    if urlsplit(value).scheme in ('http', 'https'):
        return object_digest({'url': value})
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise PipelineError('Input file is unavailable')
    return digest(path)


def require_sample_approval(sample_job, input_identity, contract):
    if not sample_job:
        raise QualityError('Full production requires --approved-sample pointing to a human-approved sample job')
    sample_job = Path(sample_job).expanduser().resolve()
    approval = load(sample_job / 'approval.json')
    sample_state = load(sample_job / 'state.json')
    if sample_state.get('sample_seconds') is None:
        raise QualityError('Approval must be for a short sample, not another full job')
    if approval.get('input_identity') != input_identity or approval.get('contract_hash') != object_digest(contract):
        raise QualityError('Approved sample source or generation contract differs')
    if not (sample_job / 'final.mp4').is_file() or digest(sample_job / 'final.mp4') != approval.get('video_sha256'):
        raise QualityError('Approved sample media has changed')
    verify(sample_job)


def run(job: Path, options: dict):
    job = Path(job).expanduser().resolve()
    os.umask(0o077)
    with job_lock(job):
        state = load(job / 'state.json') if (job / 'state.json').exists() else {'schema_version': 1, 'stages': {}}
        try:
            return _run_locked(job, state, options)
        except Exception as exc:
            state.update(status='BLOCKED', error_type=type(exc).__name__, error=str(exc))
            save(job / 'state.json', state)
            raise


def _run_locked(job, state, options):
    from .models import resolve_model
    from . import speech
    llm.endpoint(options['llm_url'], options.get('allow_remote_llm', False))
    if bool(options.get('ref_audio')) != bool(options.get('ref_text')):
        raise PipelineError('Reference audio and literal reference transcript are both required for Base voice cloning')
    sample_seconds = options.get('sample_seconds')
    if sample_seconds is not None and (not math.isfinite(sample_seconds) or sample_seconds <= 0):
        raise PipelineError('Sample duration must be positive and finite')
    identity = _input_identity(options['input'])
    contract = generation_contract(options)
    frozen = {'input_identity': identity, 'contract': contract, 'sample_seconds': sample_seconds}
    if state.get('frozen') and state['frozen'] != frozen:
        raise QualityError('Job inputs or model/voice contract changed; create a new job or use the explicit translation revision command')
    if sample_seconds is None:
        require_sample_approval(options.get('approved_sample'), identity, contract)
    state.update(frozen=frozen, input_identity=identity, contract_hash=object_digest(contract), sample_seconds=sample_seconds)
    asr_model = resolve_model('asr', accept_download=options.get('accept_download', False))
    tts_alias = 'tts' if options.get('ref_audio') else 'custom_tts'
    tts_model = resolve_model(tts_alias, accept_download=options.get('accept_download', False))
    _stage(job, state, 'source', frozen, ['source.mp4', 'source.wav', 'source.json'],
           lambda: _prepare_source(job, options['input'], sample_seconds))
    source = load(job / 'source.json')
    if sample_seconds is None:
        approved_source = load(Path(options['approved_sample']) / 'source.json')
        if source['original_sha256'] != approved_source['original_sha256']:
            raise QualityError('Full source bytes differ from the source used for the approved sample')
    duration = source['duration_s']
    asr_key = {'source': digest(job / 'source.wav'), 'model': contract['models']['asr'], 'language': 'en'}
    _stage(job, state, 'asr', asr_key, ['source_asr.json'],
           lambda: save(job / 'source_asr.json', speech.transcribe(job / 'source.wav', asr_model, language='en')))
    units = source_units(load(job / 'source_asr.json'))
    # A sample cut must not silently leave a visibly truncated final sentence.
    if sample_seconds is not None and units[-1]['end'] >= duration - 0.12 and not units[-1]['en'].rstrip().endswith(('.', '!', '?')):
        raise QualityError('Sample ends in an incomplete sentence; choose a longer or reviewed source clip')
    translation_key = {'asr': digest(job / 'source_asr.json'), 'llm': contract['llm_model'], 'base': contract['llm_url'], 'policy': 'faithful-bilingual-phrases-v1'}
    _stage(job, state, 'translate', translation_key, ['translations.json'],
           lambda: save(job / 'translations.json', llm.translate(units, options['llm_url'], options['llm_model'], allow_remote=options.get('allow_remote_llm', False))))
    translated = llm.validate_translations(units, load(job / 'translations.json'))
    review_key = {'translation': digest(job / 'translations.json'), 'model': contract['llm_model']}
    _stage(job, state, 'review', review_key, ['semantic_review.json'],
           lambda: save(job / 'semantic_review.json', llm.review(translated, options['llm_url'], options['llm_model'], allow_remote=options.get('allow_remote_llm', False))))
    if not load(job / 'semantic_review.json')['approved'] or load(job / 'semantic_review.json')['issues']:
        raise QualityError('Text-only semantic review rejected the translation; inspect semantic_review.json and revise without removing source facts')
    audio_dir = job / 'audio'
    audio_dir.mkdir(exist_ok=True)
    records, cues, generated = [], [], 0
    for index, unit in enumerate(translated):
        stem = unit['id']
        raw = audio_dir / (stem + '.raw.wav')
        final = audio_dir / (stem + '.wav')
        evidence = audio_dir / (stem + '.json')
        offset = max(0.0, unit['start'])
        next_start = translated[index+1]['start'] if index+1 < len(translated) else duration
        window = next_start - offset
        audio_inputs = {'text': unit['zh'], 'contract': contract, 'start': offset, 'window': window}
        audio_key = object_digest(audio_inputs)
        legacy_key = object_digest({**audio_inputs, 'phrases': unit['phrases']})
        if evidence.exists():
            stored = load(evidence)
            if stored.get('key') in (audio_key, legacy_key) and final.is_file() and stored.get('sha256') == digest(final):
                saved_asr = audio_dir / (stem + '.asr.json')
                if not saved_asr.is_file() or digest(saved_asr) != stored['asr_sha256']:
                    raise QualityError('Cached Chinese ASR evidence changed')
                # Display-only semantic phrase edits reuse the same accepted audio;
                # remap real word boundaries instead of calling TTS again.
                stored['cues'] = align_phrases(unit['phrases'], load(saved_asr), offset=offset, wav_duration=stored['duration_s'])
                stored['key'] = audio_key
                save(evidence, stored)
                records.append(stored)
                cues.extend(stored['cues'])
                continue
        state.update(active_stage='tts', active_unit=stem)
        save(job / 'state.json', state)
        raw_meta = speech.synthesize(unit['zh'], raw, tts_model, mode='clone' if options.get('ref_audio') else 'custom',
                                     speaker=options.get('voice', 'Vivian'), ref_audio=options.get('ref_audio'),
                                     ref_text=options.get('ref_text'), temperature=0.3)
        generated += 1
        natural_duration = float(raw_meta['duration_s'])
        if window <= 0 or natural_duration <= 0:
            raise QualityError('Invalid speech window or generated duration')
        speed = max(1.0, natural_duration / window)
        if speed > 1.1:
            save(audio_dir / (stem + '.rejection.json'), {'reason': 'speech_exceeds_window', 'natural_duration_s': natural_duration,
                 'window_s': window, 'required_atempo': speed, 'max_atempo': 1.1, 'raw_sha256': digest(raw)})
            raise QualityError(f'{stem}: speech exceeds its window beyond allowed 1.10x; retain the raw evidence and revise natural wording/grouping, never silently drop facts')
        command(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', raw, '-af', f'atempo={speed:.8f}',
                 '-ar', '24000', '-ac', '1', '-c:a', 'pcm_s16le', final], log=job / 'speech.log')
        with wave.open(str(final), 'rb') as audio:
            final_duration = audio.getnframes() / audio.getframerate()
        asr = speech.transcribe(final, asr_model, language='zh')
        save(audio_dir / (stem + '.asr.json'), asr)
        unit_cues = align_phrases(unit['phrases'], asr, offset=offset, wav_duration=final_duration)
        if offset + final_duration > next_start + 0.06:
            raise QualityError('Placed speech overlaps its next source window')
        stored = {'key': audio_key, 'id': stem, 'file': final.relative_to(job).as_posix(), 'sha256': digest(final),
                  'offset_s': offset, 'natural_duration_s': natural_duration, 'duration_s': final_duration,
                  'atempo': speed, 'sample_rate_hz': 24000, 'cues': unit_cues,
                  'asr_sha256': digest(audio_dir / (stem + '.asr.json')), 'content_gate': 'strict_normalized_text_match'}
        save(evidence, stored)
        records.append(stored)
        cues.extend(unit_cues)
    for previous, current in zip(cues, cues[1:]):
        if current['start'] < previous['end'] - 0.03:
            raise QualityError('Overlapping final subtitle cues')
    save(job / 'placement.json', records)
    save(job / 'captions.json', cues)
    for language in ('zh', 'en'):
        (job / f'{language}.srt').write_text(srt(cues, language), encoding='utf-8')
    video_info = probe(job / 'source.mp4')
    video_stream = next(x for x in video_info['streams'] if x.get('codec_type') == 'video')
    (job / 'bilingual.ass').write_text(ass_subtitles(cues, video_stream['width'], video_stream['height']), encoding='utf-8')
    render_key = {'source': digest(job / 'source.mp4'), 'placement': digest(job / 'placement.json'),
                  'captions': digest(job / 'captions.json'), 'ass': digest(job / 'bilingual.ass'), 'contract': contract}
    def render():
        inputs = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', job / 'source.mp4']
        filters = ['[0:a:0]aresample=48000,volume=0.08,apad[original]']
        labels = ['[original]']
        for n, record in enumerate(records, 1):
            inputs += ['-i', job / record['file']]
            filters.append(f'[{n}:a:0]aresample=48000,adelay={round(record["offset_s"] * 1000)}:all=1[d{n}]')
            labels.append(f'[d{n}]')
        filters.append(''.join(labels) + f'amix=inputs={len(labels)}:normalize=0:duration=longest,alimiter=limit=0.97:level=false,atrim=0:{duration:.6f}[mix]')
        if options.get('burn_subtitles'):
            filters.append('[0:v:0]ass=bilingual.ass[v]')
        inputs += ['-i', job / 'zh.srt', '-i', job / 'en.srt', '-filter_complex', ';'.join(filters),
                   '-map', '[v]' if options.get('burn_subtitles') else '0:v:0', '-map', '[mix]',
                   '-map', f'{len(records)+1}:0', '-map', f'{len(records)+2}:0',
                   '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p',
                   '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-c:s', 'mov_text',
                   '-metadata:s:s:0', 'language=zho', '-metadata:s:s:1', 'language=eng',
                   '-map_metadata', '-1', '-t', str(duration), '-movflags', '+faststart', job / 'final.mp4']
        command(inputs, cwd=job, log=job / 'render.log')
    _stage(job, state, 'render', render_key, ['final.mp4', 'zh.srt', 'en.srt', 'bilingual.ass', 'captions.json', 'placement.json'], render)
    state.update(status='VERIFYING', generated_audio_this_run=generated)
    save(job / 'state.json', state)
    result = verify(job, write=True)
    state.update(status='MACHINE_COMPLETE', active_stage=None, active_unit=None,
                 generated_audio_this_run=generated, video_sha256=result['video_sha256'], error=None, error_type=None)
    save(job / 'state.json', state)
    return {'status': state['status'], 'job': str(job), 'final_video': str(job / 'final.mp4'),
            'generated_audio_this_run': generated, 'machine_verified': True,
            'human_listening_approved': (job / 'approval.json').exists(), 'full_video_verified': sample_seconds is None}


def verify(job: Path, *, write=False):
    job = Path(job)
    state = load(job / 'state.json')
    source = load(job / 'source.json')
    captions = load(job / 'captions.json')
    placement = load(job / 'placement.json')
    if not captions or not placement:
        raise QualityError('Missing final speech/caption evidence')
    for name, stage in state.get('stages', {}).items():
        for rel, expected in stage.get('outputs', {}).items():
            if not (job / rel).is_file() or digest(job / rel) != expected:
                raise QualityError(f'Artifact integrity check failed at {name}')
    duration = source['duration_s']
    previous_end = -1.0
    for cue in captions:
        start, end = cue['start'], cue['end']
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= duration + 0.15) or start < previous_end - 0.03:
            raise QualityError('Invalid final caption timeline')
        previous_end = end
        if not cue['zh'].strip() or not cue['en'].strip() or cue.get('alignment_method') != 'exact_text_match_to_final_chinese_asr_word_boundaries':
            raise QualityError('Missing bilingual content or real-audio alignment provenance')
    for record in placement:
        if not (job / record['file']).is_file() or digest(job / record['file']) != record['sha256']:
            raise QualityError('Placed speech hash mismatch')
        if record['content_gate'] != 'strict_normalized_text_match' or not (0.9 <= record['atempo'] <= 1.1):
            raise QualityError('Speech contract failed')
        asr_path = job / 'audio' / (record['id'] + '.asr.json')
        if not asr_path.is_file() or digest(asr_path) != record['asr_sha256']:
            raise QualityError('ASR evidence hash mismatch')
        with wave.open(str(job / record['file']), 'rb') as audio:
            if audio.getframerate() != record['sample_rate_hz'] or audio.getnframes() <= 0:
                raise QualityError('Actual WAV sample rate differs from placement metadata')
    actual = probe(job / 'final.mp4')
    audio_streams = [s for s in actual['streams'] if s.get('codec_type') == 'audio']
    video_streams = [s for s in actual['streams'] if s.get('codec_type') == 'video']
    subtitle_streams = [s for s in actual['streams'] if s.get('codec_type') == 'subtitle']
    if not video_streams or not audio_streams or len(subtitle_streams) != 2 or int(audio_streams[0]['sample_rate']) != 48000:
        raise QualityError('Final video/audio/subtitle streams are incomplete')
    if abs(float(actual['format']['duration']) - duration) > 0.2:
        raise QualityError('Final media duration differs from source')
    for index, language in [(0, 'zh'), (1, 'en')]:
        decoded = command(['ffmpeg', '-v', 'error', '-i', job / 'final.mp4', '-map', f'0:s:{index}', '-f', 'srt', '-'])
        for cue in captions:
            if cue[language] not in decoded:
                raise QualityError('Embedded subtitle content is incomplete')
    # Decode the entire video and audio, not just the container header.
    command(['ffmpeg', '-v', 'error', '-i', job / 'final.mp4', '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-'])
    from .media import audio_metrics
    metrics = audio_metrics(job / 'final.mp4')
    result = {'machine_verified': True, 'video_sha256': digest(job / 'final.mp4'), 'duration_s': duration,
              'audio_metrics': metrics,
              'speech_units': len(placement), 'bilingual_cues': len(captions), 'audio_sample_rate_hz': 48000,
              'source_audio_mix_volume': 0.08, 'semantic_review': 'text_model_only',
              'human_listening_approved': (job / 'approval.json').exists(),
              'note': 'Machine checks do not replace listening, visual review or user approval.'}
    if write:
        save(job / 'verification.json', result)
    return result


def approve(job: Path, note: str):
    if not note.strip():
        raise PipelineError('Approval requires a meaningful listening/review note')
    with job_lock(job):
        result = verify(job)
        state = load(job / 'state.json')
        data = {'video_sha256': result['video_sha256'], 'input_identity': state['input_identity'],
                'contract_hash': state['contract_hash'], 'note': note.strip(),
                'declaration': 'Caller explicitly reports human listening and visual approval; not automatically inferred.'}
        save(job / 'approval.json', data)
        return data


def revise_translations(job: Path, proposed: Path):
    with job_lock(job):
        state = load(job / 'state.json')
        units = source_units(load(job / 'source_asr.json'))
        translations = llm.validate_translations(units, load(proposed))
        if 'translate' not in state.get('stages', {}):
            raise PipelineError('Translation stage must exist before revision')
        previous = job / ('translations.previous.' + digest(job / 'translations.json')[:12] + '.json')
        if not previous.exists():
            shutil.copyfile(job / 'translations.json', previous)
        save(job / 'translations.json', translations)
        state['stages']['translate']['outputs'] = _artifacts(job, ['translations.json'])
        for stage in ('review', 'render'):
            state['stages'].pop(stage, None)
        for path in ('approval.json', 'verification.json'):
            (job / path).unlink(missing_ok=True)
        state.update(status='REVISION_READY', error=None, error_type=None)
        save(job / 'state.json', state)
        return {'status': 'REVISION_READY', 'unchanged_audio_reused_on_next_run': True}
