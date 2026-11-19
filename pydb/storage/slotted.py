"""Slotted page — variable-length records inside one fixed-size page.

Layout
------

    +----------------------------------------------------------+ offset 0
    | header (12 bytes)                                        |
    |   [0:2]  slot_count   uint16                             |
    |   [2:4]  free_end     uint16                             |
    |   [4:6]  dead_space   uint16                             |
    |   [6:8]  reserved                                        |
    |   [8:12] next_page    uint32  (0xFFFFFFFF == none)       |
    +----------------------------------------------------------+ offset 12
    | slot 0   | slot 1   | ... | slot n-1 |  free space       |
    | (offset:2, length:2) each                                |
    +----------------------------------------------------------+ free_end
    |                                                          |
    |            record bytes, growing downwards               |
    |                                                          |
    +----------------------------------------------------------+ page end

A deleted record leaves a *tombstone* (length == 0) and its bytes become
`dead_space`, which is reclaimed by `compact()` when an insert needs room.
"""

import struct

from ..errors import DBError

SLOT_SIZE = 4
HEADER_SIZE = 12
NO_PAGE = 0xFFFFFFFF

_HDR = struct.Struct("<HHHHI")   # slot_count, free_end, dead_space, reserved, next_page
_SLOT = struct.Struct("<HH")     # offset, length


class SlottedPage:
    def __init__(self, page):
        self.page = page
        self.data = page.data
        if self.free_end == 0:          # uninitialised (all-zero) page
            self._init()

    # ------------------------------------------------------------------ #
    # header accessors
    # ------------------------------------------------------------------ #
    def _init(self):
        _HDR.pack_into(self.data, 0, 0, len(self.data), 0, 0, NO_PAGE)
        self.page.dirty = True

    def _set_header(self, slot_count=None, free_end=None, dead_space=None, next_page=None):
        sc, fe, ds, rsv, np_ = _HDR.unpack_from(self.data, 0)
        _HDR.pack_into(
            self.data, 0,
            sc if slot_count is None else slot_count,
            fe if free_end is None else free_end,
            ds if dead_space is None else dead_space,
            rsv,
            np_ if next_page is None else next_page,
        )
        self.page.dirty = True

    @property
    def slot_count(self) -> int:
        return _HDR.unpack_from(self.data, 0)[0]

    @property
    def free_end(self) -> int:
        return _HDR.unpack_from(self.data, 0)[1]

    @property
    def dead_space(self) -> int:
        return _HDR.unpack_from(self.data, 0)[2]

    @property
    def next_page(self):
        v = _HDR.unpack_from(self.data, 0)[4]
        return None if v == NO_PAGE else v

    @next_page.setter
    def next_page(self, value):
        self._set_header(next_page=NO_PAGE if value is None else value)

    @property
    def free_start(self) -> int:
        """Offset where the free region begins (== end of the slot directory)."""
        return HEADER_SIZE + self.slot_count * SLOT_SIZE

    @property
    def free_space(self) -> int:
        return self.free_end - self.free_start

    # ------------------------------------------------------------------ #
    def can_fit(self, nbytes: int) -> bool:
        if nbytes > len(self.data) - HEADER_SIZE - SLOT_SIZE:
            return False
        need = SLOT_SIZE + nbytes
        return self.free_space >= need or self.free_space + self.dead_space >= need

    # ------------------------------------------------------------------ #
    def insert(self, record: bytes):
        """Insert a record; returns the slot number, or None if it doesn't fit."""
        need = SLOT_SIZE + len(record)

        if self.free_space < need:
            if self.free_space + self.dead_space >= need:
                self.compact()
            else:
                return None

        free_end = self.free_end - len(record)
        self.data[free_end:free_end + len(record)] = record

        slot_no = self.slot_count
        _SLOT.pack_into(self.data, HEADER_SIZE + slot_no * SLOT_SIZE, free_end, len(record))
        self._set_header(slot_count=slot_no + 1, free_end=free_end)
        return slot_no

    def get(self, slot_no: int):
        if slot_no < 0 or slot_no >= self.slot_count:
            return None
        off, length = _SLOT.unpack_from(self.data, HEADER_SIZE + slot_no * SLOT_SIZE)
        if length == 0:
            return None
        return bytes(self.data[off:off + length])

    def delete(self, slot_no: int) -> bool:
        if slot_no < 0 or slot_no >= self.slot_count:
            return False

        pos = HEADER_SIZE + slot_no * SLOT_SIZE
        _, length = _SLOT.unpack_from(self.data, pos)
        if length == 0:
            return False

        _SLOT.pack_into(self.data, pos, 0, 0)
        dead = self.dead_space + length

        # Trim trailing tombstones so the slot directory can shrink.
        slot_count = self.slot_count
        while slot_count > 0:
            _, l = _SLOT.unpack_from(self.data, HEADER_SIZE + (slot_count - 1) * SLOT_SIZE)
            if l != 0:
                break
            slot_count -= 1

        self._set_header(slot_count=slot_count, dead_space=dead)
        return True

    def update(self, slot_no: int, record: bytes):
        """Update in place if possible.

        Returns the (possibly new) slot number, or None if the record must be
        relocated to a different page.
        """
        off, length = self._slot(slot_no)

        if len(record) <= length:
            self.data[off:off + len(record)] = record
            _SLOT.pack_into(self.data, HEADER_SIZE + slot_no * SLOT_SIZE, off, len(record))
            self._set_header(dead_space=self.dead_space + (length - len(record)))
            return slot_no

        need = SLOT_SIZE + len(record)
        if self.free_space + self.dead_space + length < need:
            return None                       # caller must relocate

        self.delete(slot_no)
        new_slot = self.insert(record)
        if new_slot is None:                  # should be unreachable
            raise DBError("slotted page: insert failed after successful size check")
        return new_slot

    # ------------------------------------------------------------------ #
    def compact(self):
        """Defragment: pack every live record against the end of the page."""
        n = self.slot_count
        records = []
        for i in range(n):
            off, length = _SLOT.unpack_from(self.data, HEADER_SIZE + i * SLOT_SIZE)
            records.append(bytes(self.data[off:off + length]) if length else None)

        free_end = len(self.data)
        for i, rec in enumerate(records):
            slot_pos = HEADER_SIZE + i * SLOT_SIZE
            if rec is None:
                _SLOT.pack_into(self.data, slot_pos, 0, 0)
            else:
                free_end -= len(rec)
                self.data[free_end:free_end + len(rec)] = rec
                _SLOT.pack_into(self.data, slot_pos, free_end, len(rec))

        self._set_header(free_end=free_end, dead_space=0)

    # ------------------------------------------------------------------ #
    def iter_records(self):
        for i in range(self.slot_count):
            off, length = _SLOT.unpack_from(self.data, HEADER_SIZE + i * SLOT_SIZE)
            if length:
                yield i, bytes(self.data[off:off + length])

    # ------------------------------------------------------------------ #
    def _slot(self, slot_no: int):
        if slot_no < 0 or slot_no >= self.slot_count:
            raise DBError(f"slotted page: invalid slot {slot_no}")
        off, length = _SLOT.unpack_from(self.data, HEADER_SIZE + slot_no * SLOT_SIZE)
        if length == 0:
            raise DBError(f"slotted page: slot {slot_no} is empty")
        return off, length

    def __repr__(self):
        return (
            f"<SlottedPage slots={self.slot_count} free={self.free_space} "
            f"dead={self.dead_space}>"
        )