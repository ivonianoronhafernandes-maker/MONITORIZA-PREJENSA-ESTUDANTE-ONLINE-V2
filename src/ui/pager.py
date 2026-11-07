"""Numbered pagination (‹ 1 2 3 … 12 ›) shared by the Students and Attendance tables."""
from __future__ import annotations

import streamlit as st


def total_pages(count: int, page_size: int) -> int:
    return max(1, -(-count // page_size))


def current_page(key: str, pages: int) -> int:
    return min(max(int(st.session_state.get(key, 1)), 1), pages)


def _window(page: int, pages: int) -> list[int | None]:
    """Page numbers to draw; None is an ellipsis. Always the first and last page, plus the neighbours."""
    if pages <= 6:
        return list(range(1, pages + 1))
    shown = {1, pages, page - 1, page, page + 1}
    if page <= 3:
        shown |= {2, 3}
    if page >= pages - 2:
        shown |= {pages - 2, pages - 1}
    out: list[int | None] = []
    last = 0
    for n in sorted(p for p in shown if 1 <= p <= pages):
        if n - last > 1:
            out.append(None)
        out.append(n)
        last = n
    return out


def render(key: str, count: int, page_size: int, noun: str) -> None:
    """Footer: 'Showing 1 to 10 of N <noun>' on the left and page buttons on the right."""
    pages = total_pages(count, page_size)
    page = current_page(key, pages)
    first = (page - 1) * page_size + 1 if count else 0
    items = _window(page, pages)
    info, nav = st.columns([3, 3 + len(items) * 0.45], vertical_alignment="center")
    info.caption(f"Hatudu {first} to'o {min(page * page_size, count)} husi {count:,} {noun}")
    with nav.container(key=f"pager-{key}"):
        cols = st.columns([1] * (len(items) + 2))
        if cols[0].button("", icon=":material/chevron_left:", key=f"{key}_prev", disabled=page <= 1, width="stretch"):
            st.session_state[key] = page - 1
            st.rerun()
        for col, n in zip(cols[1:-1], items):
            if n is None:
                col.markdown("<div class='pg-dots'>…</div>", unsafe_allow_html=True)
            elif col.button(str(n), key=f"{key}_p{n}", type="primary" if n == page else "secondary", width="stretch"):
                st.session_state[key] = n
                st.rerun()
        if cols[-1].button("", icon=":material/chevron_right:", key=f"{key}_next", disabled=page >= pages, width="stretch"):
            st.session_state[key] = page + 1
            st.rerun()
