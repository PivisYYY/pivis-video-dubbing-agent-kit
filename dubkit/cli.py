from __future__ import annotations
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import sys
from .common import PipelineError, load


def doctor():
    supported = platform.system() == 'Darwin' and platform.machine() == 'arm64'
    tools = {name: bool(shutil.which(name)) for name in ('ffmpeg', 'ffprobe', 'ollama', 'yt-dlp', 'uv')}
    dependencies = {}
    for name in ('mlx-audio', 'mlx-whisper', 'huggingface-hub', 'soundfile'):
        try:
            dependencies[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            dependencies[name] = None
    result = {'supported_platform': supported, 'system': platform.system(), 'machine': platform.machine(),
              'python': platform.python_version(), 'python_supported': sys.version_info >= (3, 11),
              'tools': tools, 'dependencies': dependencies,
              'free_disk_bytes': shutil.disk_usage(Path.cwd()).free,
              'pipeline_ready': supported and sys.version_info >= (3, 11) and tools['ffmpeg'] and tools['ffprobe'] and all(dependencies.values()),
              'capability_scope': 'single_speaker_or_manually_prepared_single_speaker_clip',
              'not_yet_supported': ['automatic_multi_speaker_diarization', 'Windows', 'Linux', 'CUDA'],
              'no_automatic_downloads_or_global_configuration_changes': True}
    return result


def make_parser():
    parser = argparse.ArgumentParser(description='Inspect, install and run the local video dubbing workflow; see AGENTS.md')
    parser.add_argument('--version', action='version', version='0.1.0')
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('doctor', help='Read-only platform and dependency inspection')
    models = sub.add_parser('models').add_subparsers(dest='model_action', required=True)
    models.add_parser('list', help='Read-only pinned speech model inventory')
    fetch = models.add_parser('fetch', help='Download pinned speech models only with explicit permission')
    fetch.add_argument('--accept-download', action='store_true', required=True)
    fetch.add_argument('--alias', choices=['asr', 'tts', 'custom_tts'])
    for verb in ('status', 'verify'):
        p = sub.add_parser(verb)
        p.add_argument('--job', type=Path, required=True)
    approve = sub.add_parser('approve', help='Record human listening/visual sign-off, never invoke without it')
    approve.add_argument('--job', type=Path, required=True)
    approve.add_argument('--note', required=True)
    revise = sub.add_parser('revise', help='Explicitly revise translated phrases while retaining unchanged audio')
    revise.add_argument('--job', type=Path, required=True)
    revise.add_argument('--translations', type=Path, required=True)
    run = sub.add_parser('run')
    run.add_argument('--input', required=True, help='Local video or unsigned public HTTP(S) video URL')
    run.add_argument('--job', type=Path, required=True)
    run.add_argument('--llm-url', default='http://localhost:11434/v1')
    run.add_argument('--llm-model', required=True, help='Existing compatible model selected for this machine')
    run.add_argument('--allow-remote-llm', action='store_true', help='Authorize HTTPS text-model requests; may send transcript and incur cost')
    run.add_argument('--accept-download', action='store_true', help='Authorize missing pinned speech model downloads')
    run.add_argument('--sample-seconds', type=float)
    run.add_argument('--approved-sample', type=Path)
    run.add_argument('--voice', default='Vivian')
    run.add_argument('--ref-audio', type=Path)
    run.add_argument('--ref-text-file', type=Path)
    run.add_argument('--burn-subtitles', action='store_true')
    return parser


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        if args.action == 'doctor':
            result = doctor()
        elif args.action == 'models':
            from .models import model_status, resolve_model
            if args.model_action == 'list':
                result = model_status()
            else:
                aliases = [args.alias] if args.alias else ['asr', 'custom_tts']
                result = {alias: str(resolve_model(alias, accept_download=True)) for alias in aliases}
        elif args.action == 'status':
            state = load(args.job / 'state.json')
            result = {k: state.get(k) for k in ('status', 'active_stage', 'active_unit', 'error_type', 'error', 'generated_audio_this_run', 'sample_seconds')}
        else:
            from . import pipeline
            if args.action == 'verify':
                result = pipeline.verify(args.job)
            elif args.action == 'approve':
                result = pipeline.approve(args.job, args.note)
            elif args.action == 'revise':
                result = pipeline.revise_translations(args.job, args.translations)
            else:
                if not doctor()['pipeline_ready']:
                    raise PipelineError('Platform or speech dependencies are not ready; run doctor and follow README before inference')
                options = vars(args).copy()
                options.pop('action')
                options['ref_text'] = args.ref_text_file.read_text(encoding='utf-8').strip() if args.ref_text_file else None
                result = pipeline.run(args.job, options)
        print(json.dumps({'ok': True, **result}, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (PipelineError, OSError, ValueError, KeyError, ImportError) as exc:
        print(json.dumps({'ok': False, 'error_type': type(exc).__name__, 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
