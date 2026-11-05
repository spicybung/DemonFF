"""Shared file writing for the model and collision readers."""
import os
import tempfile


def writeAtomic(filename, content):
    destination = os.path.abspath(os.fspath(filename))
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='wb', dir=os.path.dirname(destination),
            prefix=os.path.basename(destination) + '.', suffix='.tmp', delete=False
        ) as stream:
            temporary = stream.name
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)
