"""
Shared safe-write helpers for portfolio.json and other critical state files.

Atomic write pattern: write to a sibling .tmp file, fsync, then os.replace().
On POSIX os.replace is atomic — the file at the final path is either the old
content or the new content; never partial / truncated.
"""
import json
import os
import sys
import tempfile


def safe_write_json(path: str, data, indent: int = 2) -> None:
    """Atomically write `data` as pretty JSON to `path`.

    Guarantees: if the process crashes or disk fills, `path` either keeps its
    old content or gets the full new content. Never a half-written file.
    """
    path = os.path.abspath(path)
    dirname = os.path.dirname(path) or '.'
    os.makedirs(dirname, exist_ok=True)

    # Create temp file in same dir so os.replace stays atomic (same filesystem)
    fd, tmp = tempfile.mkstemp(dir=dirname, prefix='.tmp-', suffix='.json')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        # Clean up the orphan tmp on any failure
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def safe_write_text(path: str, text: str) -> None:
    """Atomic text-file write — same guarantees as safe_write_json."""
    path = os.path.abspath(path)
    dirname = os.path.dirname(path) or '.'
    os.makedirs(dirname, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dirname, prefix='.tmp-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


if __name__ == '__main__':
    # Self-test
    import tempfile as _tf
    with _tf.TemporaryDirectory() as td:
        target = os.path.join(td, 'a.json')
        safe_write_json(target, {'x': 1, 'arr': [1, 2, 3]})
        assert json.load(open(target)) == {'x': 1, 'arr': [1, 2, 3]}
        print('safe_write_json: OK')
