"""Fixed-size page cache + on-disk file I/O.

The pager is the *only* component that talks to the filesystem.  Everything
above it works with `Page` objects identified by a page number.

Layout of `data.db`:

    [ page 0 ][ page 1 ][ page 2 ] ... [ page N-1 ]

Each page is exactly PAGE_SIZE bytes.
"""

import os
from collections import OrderedDict

from ..errors import DBError

PAGE_SIZE = 4096


class Page:
    """A single fixed-size block of bytes."""

    __slots__ = ("page_no", "data", "dirty")

    def __init__(self, page_no: int, data: bytes | None  = None):
        self.page_no = page_no
        self.data = bytearray(PAGE_SIZE) if data is None else bytearray(data)
        self.dirty = False

    def __len__(self):
        return len(self.data)

    def __repr__(self):
        return f"<Page {self.page_no}{' dirty' if self.dirty else ''}>"


class Pager:
    def __init__(self, path: str, cache_size: int = 128):
        self.path = path
        self.page_size = PAGE_SIZE
        self.cache_size = cache_size

        if os.path.exists(path):
            size = os.path.getsize(path)
            self._fh = open(path, "r+b")
        else:
            size = 0
            self._fh = open(path, "w+b")

        self._num_pages = (size + PAGE_SIZE - 1) // PAGE_SIZE
        self._cache = OrderedDict()

    # ------------------------------------------------------------------ #
    @property
    def num_pages(self) -> int:
        return self._num_pages

    # ------------------------------------------------------------------ #
    def read_page(self, page_no: int) -> Page:
        if page_no < 0 or page_no >= self._num_pages:
            raise DBError(f"page {page_no} is out of range (0..{self._num_pages - 1})")

        cached = self._cache.get(page_no)
        if cached is not None:
            self._cache.move_to_end(page_no)
            return cached

        self._fh.seek(page_no * self.page_size)
        raw = self._fh.read(self.page_size)
        if len(raw) < self.page_size:
            raw = raw + b"\x00" * (self.page_size - len(raw))

        page = Page(page_no, raw)
        self._cache[page_no] = page
        self._evict()
        return page

    def allocate_page(self) -> Page:
        page_no = self._num_pages
        self._num_pages += 1

        page = Page(page_no)
        page.dirty = True
        self._cache[page_no] = page
        self._evict()
        return page

    def mark_dirty(self, page: Page):
        page.dirty = True

    # ------------------------------------------------------------------ #
    def _evict(self):
        while len(self._cache) > self.cache_size:
            _, page = self._cache.popitem(last=False)
            if page.dirty:
                self._write_page(page)

    def _write_page(self, page: Page):
        self._fh.seek(page.page_no * self.page_size)
        self._fh.write(page.data)
        page.dirty = False

    # ------------------------------------------------------------------ #
    def flush(self):
        for page in self._cache.values():
            if page.dirty:
                self._write_page(page)
        self._fh.flush()
        os.fsync(self._fh.fileno())

    def close(self):
        try:
            self.flush()
        finally:
            self._fh.close()
            self._cache.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()