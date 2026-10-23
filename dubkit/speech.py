"""Real Apple Silicon (MLX) speech I/O for the dubbing pipeline.

ASR: mlx-whisper 0.4.3, pinned public model mlx-community/whisper-large-v3-turbo.
TTS: mlx-audio 0.5.1 with the public Qwen3-TTS-12Hz-0.6B 8-bit checkpoints:
Base-8bit for reference-audio voice cloning (mode='clone') and
CustomVoice-8bit for preset speakers such as the default 'Vivian'
(mode='custom').

Every function performs real model work through the real libraries and never
fabricates audio or text. Synthesized audio is delivered as standard PCM16 WAV
converted with soundfile, whatever sample format the TTS backend wrote.
"""

from __future__ import annotations

import math
import os
import shutil
import tempfile
from collections import OrderedDict
from pathlib import Path

import mlx_whisper
import numpy as np
import soundfile
from mlx_audio.tts.generate import generate_audio
from mlx_audio.tts.utils import load_model

from .common import PipelineError, QualityError, digest

ASR_MODEL_ID = 'mlx-community/whisper-large-v3-turbo'
TTS_CLONE_MODEL_ID = 'mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit'
TTS_CUSTOM_MODEL_ID = 'mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit'
DEFAULT_SPEAKER = 'Vivian'

# Synthesis is strictly sequential and the TTS model cache is bounded.
# The ASR library may retain its own model cache; callers must not run GPU
# stages concurrently or infer memory use from audio duration alone.
_MAX_LOADED_MODELS = 2
_LOADED_TTS_MODELS: 'OrderedDict[str, object]' = OrderedDict()

_REF_TEXT_SUFFIXES = {'.txt', '.text', '.wav', '.mp3', '.flac', '.m4a', '.aac', '.ogg'}


def _plain(value):
    """Convert numpy scalars/arrays to plain JSON-serializable Python types."""
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def transcribe(audio, model_path, language='en', word_timestamps=True) -> dict:
    """Run real MLX Whisper ASR on an audio file.

    Calls mlx_whisper.transcribe with the audio path as the first positional
    argument and the pinned model via path_or_hf_repo (local snapshot path or
    public repo id). Never passes initial_prompt or any expected text.
    Exceptions from the backend propagate unchanged. numpy scalars in the
    result are converted to plain Python numbers so the dict round-trips
    through JSON with words/start/end/text preserved. With word_timestamps on,
    a result without word timestamps is an error, not a silent empty alignment.
    """
    audio_path = Path(audio)
    if not audio_path.is_file():
        raise PipelineError('ASR input audio file not found: ' + audio_path.name)
    model_id = str(model_path or '').strip()
    if not model_id:
        raise PipelineError('ASR model path or repo id is required')
    result = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=model_id,
        language=language,
        word_timestamps=bool(word_timestamps),
        condition_on_previous_text=False,
    )
    plain = _plain(result)
    if not isinstance(plain, dict) or not isinstance(plain.get('segments'), list):
        raise PipelineError('ASR returned an unexpected result shape; refusing to guess')
    if word_timestamps and not any(
        isinstance(seg, dict) and seg.get('words') for seg in plain['segments']
    ):
        raise QualityError('ASR returned no word timestamps while word_timestamps is on')
    return plain


def _load_tts_model(model_path):
    path = Path(model_path).expanduser()
    key = os.fspath(path.resolve() if path.exists() else path)
    model = _LOADED_TTS_MODELS.get(key)
    if model is not None:
        _LOADED_TTS_MODELS.move_to_end(key)
        return model
    model = load_model(path)
    _LOADED_TTS_MODELS[key] = model
    while len(_LOADED_TTS_MODELS) > _MAX_LOADED_MODELS:
        _LOADED_TTS_MODELS.popitem(last=False)
    return model


def _ref_text_is_path(ref_text: str) -> bool:
    candidate = Path(ref_text.strip())
    if candidate.is_file():
        return True
    return ' ' not in ref_text.strip() and candidate.suffix.lower() in _REF_TEXT_SUFFIXES


def synthesize(
    text: str,
    output,
    model_path,
    *,
    mode: str = 'custom',
    speaker: str = DEFAULT_SPEAKER,
    ref_audio=None,
    ref_text=None,
    temperature: float = 0.3,
) -> dict:
    """Run real MLX-Audio TTS and deliver exactly one PCM16 WAV segment.

    mode='clone' uses the Base checkpoint with explicit voice-cloning input:
    ref_audio must be an existing file and ref_text must be the literal
    transcript content, never a file path. mode='custom' uses the CustomVoice
    checkpoint's preset speaker, forwarded through the library's `voice`
    parameter (the real speaker argument for Qwen3-TTS); reference material is
    rejected there so a fake ref can never silently mask the preset. The
    reference audio file is only ever read; its checksum is verified unchanged
    after generation.

    Generation runs in a private temp directory inside the output's parent.
    The backend reports failures by returning quietly and writes one WAV file
    per segment, so the wrapper validates artifacts: zero or multiple segment
    files raise instead of silently dropping audio (newline-separated text
    synthesizes as several segments; split the text upstream). The single
    segment is read with soundfile, converted to PCM16 at its real sample
    rate, and atomically moved to `output` after a read-back check.

    Returns runtime evidence only: sample_rate_hz, frames, duration_s,
    channels, model_path, mode and speaker (None for clone mode).
    """
    if not isinstance(text, str) or not text.strip():
        raise PipelineError('Speech text is empty; nothing to synthesize')
    if mode not in ('clone', 'custom'):
        raise PipelineError("mode must be 'clone' (Base checkpoint with reference audio) or 'custom' (CustomVoice preset speaker)")
    model_id = str(model_path or '').strip()
    if not model_id:
        raise PipelineError('TTS model path or repo id is required')
    temperature = float(temperature)
    if not math.isfinite(temperature) or not 0.0 <= temperature <= 2.0:
        raise PipelineError('temperature must be finite within [0, 2]')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    voice = None
    clone_path = None
    if mode == 'clone':
        if not ref_audio or not ref_text:
            raise PipelineError('Base voice cloning requires both ref_audio and ref_text')
        clone_path = Path(ref_audio).expanduser()
        if not clone_path.is_file():
            raise PipelineError('Reference audio file not found: ' + clone_path.name)
        ref_text = str(ref_text)
        if _ref_text_is_path(ref_text):
            raise PipelineError('ref_text must be the transcript text content, not a file path')
        reference_info = soundfile.info(str(clone_path))
        if reference_info.samplerate != 16000 or reference_info.channels != 1 or reference_info.frames <= 0:
            raise PipelineError('Reference must be a nonempty 16 kHz mono audio file; convert to a separate file without overwriting the original')
        ref_digest = digest(clone_path)
    else:
        if ref_audio or ref_text:
            raise PipelineError("custom mode uses the preset speaker; ref_audio/ref_text are only for mode='clone'")
        speaker = str(speaker).strip()
        if not speaker:
            raise PipelineError('custom mode requires a non-empty preset speaker name')
        voice = speaker

    model = _load_tts_model(model_path)
    work_dir = Path(tempfile.mkdtemp(prefix='.tts-', dir=output.parent))
    try:
        generate_audio(
            text=text,
            model=model,
            voice=voice,
            ref_audio=str(clone_path) if clone_path else None,
            ref_text=ref_text if mode == 'clone' else None,
            stt_model=None,
            output_path=str(work_dir),
            lang_code='zh',
            speed=1.0,
            temperature=temperature,
            max_tokens=1200,
            audio_format='wav',
            verbose=False,
        )
        # generate_audio swallows its own exceptions and returns None; the
        # written artifacts are the only trustworthy evidence.
        segments = sorted(work_dir.glob('*.wav'))
        if not segments:
            raise PipelineError('TTS produced no audio segment; inspect the backend trace for the swallowed error')
        if len(segments) > 1:
            raise PipelineError(
                f'TTS produced {len(segments)} segment files; refusing to silently drop any - split the text into single segments upstream'
            )
        if clone_path and digest(clone_path) != ref_digest:
            raise QualityError('Reference audio changed during synthesis; refusing the result')
        data, sample_rate = soundfile.read(str(segments[0]), dtype='float32', always_2d=True)
        if sample_rate <= 0:
            raise PipelineError('TTS segment reports a non-positive sample rate')
        if data.shape[0] == 0:
            raise PipelineError('TTS segment contains no audio frames')
        handle, staging = tempfile.mkstemp(prefix='.' + output.name, dir=output.parent)
        os.close(handle)
        try:
            soundfile.write(staging, data, sample_rate, subtype='PCM_16', format='WAV')
            written = soundfile.info(staging)
            if written.frames != data.shape[0] or written.samplerate != sample_rate:
                raise QualityError('Converted WAV read-back differs from the generated segment')
            os.replace(staging, output)
            staging = None
        finally:
            if staging is not None and os.path.exists(staging):
                os.unlink(staging)
        final = soundfile.info(str(output))
        return {
            'sample_rate_hz': int(final.samplerate),
            'frames': int(final.frames),
            'duration_s': final.frames / final.samplerate,
            'channels': int(final.channels),
            'model_path': model_id,
            'mode': mode,
            'speaker': None if mode == 'clone' else speaker,
        }
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
