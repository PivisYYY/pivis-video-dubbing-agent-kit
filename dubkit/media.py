"""Streaming PCM metrics from the actual encoded final audio track."""
from array import array
from pathlib import Path
import subprocess
import sys
import tempfile
from .common import PipelineError, QualityError


def audio_metrics(path: Path) -> dict:
    peak = 0
    count = 0
    clipped = 0
    square_sum = 0
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:a:0', '-vn',
                                    '-c:a', 'pcm_s16le', '-f', 's16le', '-'], stdout=subprocess.PIPE, stderr=errors)
        remainder = b''
        try:
            while True:
                chunk = process.stdout.read(65536)
                if not chunk:
                    break
                chunk = remainder + chunk
                limit = len(chunk) - len(chunk) % 2
                remainder = chunk[limit:]
                samples = array('h')
                samples.frombytes(chunk[:limit])
                if sys.byteorder != 'little':
                    samples.byteswap()
                for value in samples:
                    amplitude = abs(value)
                    peak = max(peak, amplitude)
                    clipped += amplitude >= 32767
                    square_sum += value * value
                count += len(samples)
            exit_code = process.wait(timeout=30)
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.kill()
                process.wait()
    if exit_code or remainder or not count:
        raise PipelineError('Cannot decode a complete final PCM audio stream')
    if clipped:
        raise QualityError('Final decoded audio contains full-scale PCM samples; inspect clipping rather than claiming a clean output')
    return {'decoded_samples': count, 'peak_linear': peak / 32768,
            'rms_linear': (square_sum / count) ** 0.5 / 32768, 'full_scale_samples': clipped}
