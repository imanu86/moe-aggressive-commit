"""Bounded SNTv0001 reader; accepted rows only, no discarded speculative tails."""
import hashlib
import struct
from pathlib import Path
import numpy as np

LAYERS = (0, 1, 35, 36)
HEADER = b'SNTv0001' + struct.pack('<4I4i', 2560, 640, 10, 4, *LAYERS)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for raw in iter(lambda: stream.read(1 << 20), b''):
            h.update(raw)
    return h.hexdigest()


def windows(path):
    count = 0
    with Path(path).open('rb') as stream:
        if stream.read(40) != HEADER:
            raise ValueError('invalid SNT header')
        while head := stream.read(24):
            if len(head) != 24:
                raise ValueError('truncated window header')
            t, keep, pos, serial = struct.unpack('<IIqQ', head)
            count += 1
            if not (1 <= keep <= t <= 8 and pos >= 0 and serial > 0 and count <= 512):
                raise ValueError('invalid window bounds')
            size = t * (4 + 4 * (2560*4 + 10*12 + 10*2560*4))
            raw = stream.read(size)
            if len(raw) != size:
                raise ValueError('truncated window payload')
            yield t, keep, pos, serial, raw, head + raw
    if not count:
        raise ValueError('empty trace')


def read_rows(path):
    rows = []
    previous = -1
    for t, keep, pos, serial, raw, _ in windows(path):
        if pos <= previous:
            raise ValueError('overlapping accepted positions')
        tokens = np.frombuffer(raw, '<i4', t)
        at = 4*t
        layers = []
        for layer in LAYERS:
            x = np.frombuffer(raw, '<f4', t*2560, at).reshape(t, 2560); at += t*2560*4
            ids = np.frombuffer(raw, '<i4', t*10, at).reshape(t, 10); at += t*10*4
            weights = np.frombuffer(raw, '<f4', t*10, at).reshape(t, 10); at += t*10*4
            parts = np.frombuffer(raw, '<f4', t*10*2560, at).reshape(t, 10, 2560); at += t*10*2560*4
            tiers = np.frombuffer(raw, '<i4', t*10, at).reshape(t, 10); at += t*10*4
            if not (np.isfinite(x).all() and np.isfinite(weights).all() and np.isfinite(parts).all()
                    and np.all(weights >= 0) and np.all((ids >= 0) & (ids < 512))
                    and np.all((tiers >= 0) & (tiers <= 2)) and np.all(tokens >= 0)):
                raise ValueError('invalid trace values')
            for j in range(keep):
                if len(set(ids[j])) != 10:
                    raise ValueError('duplicate routed expert')
            layers.append((layer, x, ids, weights, parts, tiers))
        assert at == len(raw)
        for j in range(keep):
            rows.append({'pos': pos+j, 'serial': serial, 'token': int(tokens[j]),
                         'layers': {layer: {'x': x[j].copy(), 'ids': ids[j].copy(),
                             'weights': weights[j].copy(), 'parts': parts[j].copy(), 'tiers': tiers[j].copy()}
                         for layer, x, ids, weights, parts, tiers in layers}})
        previous = pos+keep-1
    return rows


def split_trace(path, folder):
    """Respect unchanged GPU replayer bounds: <=64 windows and <=192 inputs."""
    folder.mkdir()
    result = []
    batch = []
    accepted = 0
    def flush():
        dest = folder / f'chunk-{len(result):03d}.snt'
        with dest.open('xb') as stream:
            stream.write(HEADER)
            for raw in batch:
                stream.write(raw)
        result.append(dest)
    for t, keep, pos, serial, raw, record in windows(path):
        if batch and (len(batch) >= 32 or accepted + keep > 128):
            flush(); batch = []; accepted = 0
        batch.append(record); accepted += keep
    if batch:
        flush()
    expected = read_rows(path)
    rebuilt = [row for chunk in result for row in read_rows(chunk)]
    assert len(expected) == len(rebuilt)
    for a, b in zip(expected, rebuilt):
        assert (a['pos'], a['token'], a['serial']) == (b['pos'], b['token'], b['serial'])
        for layer in LAYERS:
            assert all(np.array_equal(a['layers'][layer][k], b['layers'][layer][k])
                       for k in ('x', 'ids', 'weights', 'parts', 'tiers'))
    return result
