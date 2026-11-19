"""Heap file — an unordered collection of slotted pages, chained together.

Each table owns exactly one heap file.  Pages form a singly linked list via the
`next_page` header field, so growing a table never requires touching the
catalog.
"""

from typing import Iterator, List, NamedTuple, Optional

from ..errors import DBError
from .pager import Pager
from .slotted import SLOT_SIZE, SlottedPage


class RID(NamedTuple):
    """Row identifier: (page number, slot number)."""

    page: int
    slot: int


class HeapFile:
    def __init__(self, pager: Pager, first_page: int):
        self.pager = pager
        self.first_page = first_page
        self._free: List[int] | None = None      # pages that may still fit a row
        self._last: int | None = None            # cached tail of the page chain

    # ------------------------------------------------------------------ #
    # page chain
    # ------------------------------------------------------------------ #
    def _iter_pages(self):
        pid = self.first_page
        while pid is not None:
            sp = SlottedPage(self.pager.read_page(pid))
            yield pid, sp
            pid = sp.next_page

    def _ensure_free(self):
        if self._free is None:
            self._free = [pid for pid, sp in self._iter_pages() if sp.can_fit(1)]

    def _last_page_id(self) -> Optional[int]:
        if self._last is not None:
            return self._last
        pid = self.first_page
        last = pid
        while pid is not None:
            last = pid
            sp = SlottedPage(self.pager.read_page(pid))
            pid = sp.next_page
        self._last = last
        return last

    def pages(self):
        """Iterate over all (page_id, SlottedPage) in the chain."""
        return self._iter_pages()

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    def insert(self, record: bytes) -> RID:
        self._ensure_free()

        while self._free:
            pid = self._free[0]
            sp = SlottedPage(self.pager.read_page(pid))
            slot = sp.insert(record)
            if slot is not None:
                if not sp.can_fit(1):
                    self._free.pop(0)
                return RID(pid, slot)
            self._free.pop(0)

        # No room anywhere: append a fresh page to the chain.
        page = self.pager.allocate_page()
        new_pid = page.page_no

        last = self._last_page_id()
        if last is None:
            self.first_page = new_pid
        else:
            SlottedPage(self.pager.read_page(last)).next_page = new_pid
        self._last = new_pid

        sp = SlottedPage(page)
        slot = sp.insert(record)
        if slot is None:
            raise DBError("record is too large to fit on a single page")

        assert self._free is not None
        self._free.append(new_pid)
        return RID(new_pid, slot)

    def get(self, rid: RID) -> Optional[bytes]:
        sp = SlottedPage(self.pager.read_page(rid.page))
        return sp.get(rid.slot)

    def delete(self, rid: RID) -> bool:
        sp = SlottedPage(self.pager.read_page(rid.page))
        ok = sp.delete(rid.slot)
        if ok and self._free is not None and rid.page not in self._free:
            self._free.append(rid.page)
        return ok

    def update(self, rid: RID, record: bytes) -> RID:
        sp = SlottedPage(self.pager.read_page(rid.page))
        new_slot = sp.update(rid.slot, record)

        if new_slot is not None:
            if self._free is not None:
                fits = sp.can_fit(1)
                if fits and rid.page not in self._free:
                    self._free.append(rid.page)
                elif not fits and rid.page in self._free:
                    self._free.remove(rid.page)
            return RID(rid.page, new_slot)

        # Does not fit on this page — relocate.
        self.delete(rid)
        return self.insert(record)

    # ------------------------------------------------------------------ #
    def scan(self) -> Iterator:
        """Yield (RID, record_bytes) for every live record."""
        pid = self.first_page
        while pid is not None:
            sp = SlottedPage(self.pager.read_page(pid))
            nxt = sp.next_page
            for slot, rec in sp.iter_records():
                yield RID(pid, slot), rec
            pid = nxt

    def __repr__(self):
        return f"<HeapFile first_page={self.first_page}>"