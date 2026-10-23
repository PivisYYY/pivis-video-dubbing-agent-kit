from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


class PipelineError(RuntimeError):
    pass


class QualityError(PipelineError):
    pass


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def object_digest(data) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def save(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write('\n')
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def load(path: Path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def command(args, *, cwd=None, log=None, timeout=None):
    args = [str(x) for x in args]
    if log:
        with Path(log).open('ab') as handle:
            result = subprocess.run(args, cwd=cwd, stdout=handle, stderr=subprocess.STDOUT, timeout=timeout)
        if result.returncode:
            raise PipelineError(f'{Path(args[0]).name} failed with exit {result.returncode}; inspect the job log')
        return ''
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise PipelineError(f'{Path(args[0]).name} failed with exit {result.returncode}')
    return result.stdout


def probe(path: Path) -> dict:
    data = json.loads(command(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path]))
    if not data.get('streams'):
        raise QualityError('No media streams')
    return data
