"""Row (de)serialization.

On-disk layout of a single row:

    +----------------+--------+--------+-----+--------+
    | NULL bitmap    | col a  | col b  | ... | col n  |
    +----------------+--------+--------+-----+--------+
      ceil(n/8) bytes

NULL values occupy no space at all — only a bit in the bitmap.
"""

import struct

from .datatypes import DataType
from .errors import DBError

_INT = struct.Struct("<q")   # 8-byte signed integer
_REAL = struct.Struct("<d")  # 8-byte IEEE double
_BOOL = struct.Struct("<?")  # 1-byte boolean
_LEN = struct.Struct("<I")   # 4-byte unsigned length prefix


def _bitmap_size(ncols: int) -> int:
    return (ncols + 7) // 8


def encode_row(schema, values) -> bytes:
    ncols = len(schema.columns)
    if len(values) != ncols:
        raise DBError(f"expected {ncols} values, got {len(values)}")

    bitmap = bytearray(_bitmap_size(ncols))
    parts = []

    for i, (col, val) in enumerate(zip(schema.columns, values)):
        if val is None:
            bitmap[i // 8] |= 1 << (i % 8)
            continue
        parts.append(_encode_value(col.type, val))

    return bytes(bitmap) + b"".join(parts)


def _encode_value(dtype: DataType, value) -> bytes:
    if dtype is DataType.INTEGER:
        return _INT.pack(int(value))
    if dtype is DataType.REAL:
        return _REAL.pack(float(value))
    if dtype is DataType.BOOLEAN:
        return _BOOL.pack(bool(value))
    if dtype is DataType.TEXT:
        raw = value.encode("utf-8")
        return _LEN.pack(len(raw)) + raw
    raise DBError(f"cannot encode value of type {dtype}")


def decode_row(schema, data: bytes):
    ncols = len(schema.columns)
    nb = _bitmap_size(ncols)
    bitmap = data[:nb]
    pos = nb
    values = []

    for i, col in enumerate(schema.columns):
        if bitmap[i // 8] & (1 << (i % 8)):
            values.append(None)
            continue
        value, pos = _decode_value(col.type, data, pos)
        values.append(value)

    return values


def _decode_value(dtype: DataType, data: bytes, pos: int):
    if dtype is DataType.INTEGER:
        (v,) = _INT.unpack_from(data, pos)
        return v, pos + _INT.size
    if dtype is DataType.REAL:
        (v,) = _REAL.unpack_from(data, pos)
        return v, pos + _REAL.size
    if dtype is DataType.BOOLEAN:
        (v,) = _BOOL.unpack_from(data, pos)
        return v, pos + _BOOL.size
    if dtype is DataType.TEXT:
        (n,) = _LEN.unpack_from(data, pos)
        pos += _LEN.size
        return data[pos:pos + n].decode("utf-8"), pos + n
    raise DBError(f"cannot decode value of type {dtype}")