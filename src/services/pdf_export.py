from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Iterable, Sequence

from pypdf import PdfReader, PdfWriter, Transformation
from pypdf import PageObject
from pypdf.generic import NameObject, NumberObject

from .downloads import InstrumentSelection

A4_WIDTH = 595.28
A4_HEIGHT = 841.89
A5_LANDSCAPE_WIDTH = A4_WIDTH
A5_LANDSCAPE_HEIGHT = A4_HEIGHT / 2


@dataclass(frozen=True)
class ExportResult:
    export_path: Path | None
    pages_written: int
    missing_files: tuple[str, ...]
    debug_report: Path | None


def export_instrument_collection(
    download_root: Path,
    *,
    titles: Sequence[str],
    instruments: Sequence[InstrumentSelection],
    export_dir: Path,
    log_callback: Callable[[str], None] | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
    debug: bool = False,
) -> ExportResult:
    normalized_titles = _normalize_titles(titles)
    if not normalized_titles:
        return ExportResult(export_path=None, pages_written=0, missing_files=())

    ordered_instruments = sorted(instruments, key=lambda item: item.display.lower())
    work_items: list[tuple[str, str, Path]] = []
    missing: list[str] = []
    debug_lines: list[str] = [] if debug else []

    for instrument in ordered_instruments:
        repeats = instrument.count
        if repeats <= 0:
            continue
        for _ in range(repeats):
            for title in normalized_titles:
                pdf_path = _find_local_pdf(download_root, instrument.display, title)
                if not pdf_path:
                    missing.append(f"{instrument.display}: {title}")
                    _log(log_callback, f"Missing {instrument.display}: {title}")
                    continue
                work_items.append((instrument.display, title, pdf_path))

    total_items = len(work_items)
    _report_progress(progress_callback, 0, total_items)

    a5_pages: list[PageObject] = []
    completed = 0
    for instrument_display, _, pdf_path in work_items:
        _log(log_callback, f"Preparing {pdf_path.name} for {instrument_display}...")
        try:
            for index, page in enumerate(_pages_from_pdf(pdf_path), start=1):
                if not hasattr(page, "mediabox"):
                    _log(
                        log_callback,
                        f"Skipped non-page object in {pdf_path.name}.",
                    )
                    if debug:
                        debug_lines.append(
                            f"{pdf_path.name} page {index}: skipped non-page object"
                        )
                    continue
                if debug:
                    debug_lines.append(
                        f"{pdf_path.name} page {index}: {_describe_page(page)}"
                    )
                a5_pages.append(_to_a5_landscape(page))
        except Exception as exc:
            _log(log_callback, f"Failed to read {pdf_path.name}: {exc}")
            if debug:
                debug_lines.append(f"{pdf_path.name}: failed to read ({exc})")
        completed += 1
        _report_progress(progress_callback, completed, total_items)

    debug_report = _write_debug_report(export_dir, debug_lines) if debug else None
    if debug_report:
        _log(log_callback, f"Debug report saved: {debug_report}")

    if not a5_pages:
        return ExportResult(
            export_path=None,
            pages_written=0,
            missing_files=tuple(missing),
            debug_report=debug_report,
        )

    if len(a5_pages) % 2 != 0:
        a5_pages.append(_blank_a5_page())

    half = len(a5_pages) // 2
    top_pages = a5_pages[:half]
    bottom_pages = a5_pages[half:]

    writer = PdfWriter()
    for top_page, bottom_page in zip(top_pages, bottom_pages, strict=True):
        a4_page = PageObject.create_blank_page(width=A4_WIDTH, height=A4_HEIGHT)
        _merge_page_at(a4_page, bottom_page, 0, 0)
        _merge_page_at(a4_page, top_page, 0, A5_LANDSCAPE_HEIGHT)
        writer.add_page(a4_page)

    export_dir.mkdir(parents=True, exist_ok=True)
    export_path = export_dir / _export_filename()
    with export_path.open("wb") as handle:
        writer.write(handle)

    return ExportResult(
        export_path=export_path,
        pages_written=len(a5_pages),
        missing_files=tuple(missing),
        debug_report=debug_report,
    )


def merge_pdf_files(paths: Iterable[Path], output_path: Path) -> None:
    writer = PdfWriter()
    for path in paths:
        for page in _pages_from_pdf(path):
            writer.add_page(page)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as handle:
        writer.write(handle)


def rotate_page(page: PageObject, degrees: int) -> PageObject:
    page.rotate(degrees)
    return page


def resize_page_to_a5_landscape(page: PageObject) -> PageObject:
    return _to_a5_landscape(page)


def _normalize_titles(titles: Sequence[str]) -> list[str]:
    return sorted({title.strip() for title in titles if title.strip()}, key=str.lower)


def _export_filename() -> str:
    return f"export_{date.today():%Y%m%d}.pdf"


def _pages_from_pdf(path: Path) -> Iterable[PageObject]:
    reader = PdfReader(str(path))
    yield from reader.pages


def _find_local_pdf(download_root: Path, instrument_display: str, title: str) -> Path | None:
    instrument_dir = download_root.joinpath(*instrument_display.split(" / "))
    if not instrument_dir.exists():
        return None
    files = [path for path in instrument_dir.iterdir() if path.suffix.lower() == ".pdf"]
    return _match_local_pdf_for_title(files, title)


def _match_local_pdf_for_title(files: Sequence[Path], title: str) -> Path | None:
    normalized_title = title.strip().lower()
    if not normalized_title:
        return None

    for path in files:
        name_lower = path.name.lower()
        if name_lower == normalized_title:
            return path
        if name_lower.endswith(".pdf") and name_lower[:-4] == normalized_title:
            return path

    starts_with = [path for path in files if path.name.lower().startswith(normalized_title)]
    if starts_with:
        return min(starts_with, key=lambda path: len(path.name))

    contains = [path for path in files if normalized_title in path.name.lower()]
    if contains:
        return min(contains, key=lambda path: len(path.name))

    return None


def _blank_a5_page() -> PageObject:
    return PageObject.create_blank_page(width=A5_LANDSCAPE_WIDTH, height=A5_LANDSCAPE_HEIGHT)


def _to_a5_landscape(page: PageObject) -> PageObject:
    working = _normalized_page_view(page)
    width = float(working.mediabox.width)
    height = float(working.mediabox.height)
    if width < height:
        working = _rotate_content(working, 90)
        width = float(working.mediabox.width)
        height = float(working.mediabox.height)

    scale = min(A5_LANDSCAPE_WIDTH / width, A5_LANDSCAPE_HEIGHT / height)
    if scale != 1.0:
        working.scale_by(scale)
        width *= scale
        height *= scale

    tx = (A5_LANDSCAPE_WIDTH - width) / 2
    ty = (A5_LANDSCAPE_HEIGHT - height) / 2
    if tx or ty:
        working.add_transformation(Transformation().translate(tx, ty))

    target = PageObject.create_blank_page(
        width=A5_LANDSCAPE_WIDTH,
        height=A5_LANDSCAPE_HEIGHT,
    )
    target.merge_page(working)
    return target


def _merge_page_at(target: PageObject, source: PageObject, x: float, y: float) -> None:
    if not (x or y):
        target.merge_page(source)
        return

    transform = Transformation().translate(x, y)
    _merge_with_transform(target, source, transform)


def _normalized_page_view(page: PageObject) -> PageObject:
    try:
        transfer_rotation = getattr(page, "transfer_rotation_to_content", None)
        if callable(transfer_rotation):
            try:
                transfer_rotation()
                _force_rotation_zero(page)
            except Exception:
                pass

        box = _select_box(page)
        llx = float(box.lower_left[0])
        lly = float(box.lower_left[1])
        width = float(box.width)
        height = float(box.height)
        rotation = int(page.get("/Rotate", 0) or 0) % 360

        target_width = width
        target_height = height
        if rotation in (90, 270):
            target_width, target_height = height, width

        normalized = PageObject.create_blank_page(
            width=target_width,
            height=target_height,
        )

        transform = Transformation().translate(-llx, -lly)
        if rotation:
            transform = transform.rotate(-rotation)
            if rotation == 90:
                transform = transform.translate(0, width)
            elif rotation == 180:
                transform = transform.translate(width, height)
            elif rotation == 270:
                transform = transform.translate(height, 0)

        _merge_with_transform(normalized, page, transform)
        _force_rotation_zero(normalized)
        return normalized
    except Exception:
        fallback = PageObject.create_blank_page(
            width=float(page.mediabox.width),
            height=float(page.mediabox.height),
        )
        fallback.merge_page(page)
        _force_rotation_zero(fallback)
        return fallback


def _select_box(page: PageObject):
    return page.mediabox


def _rotate_content(page: PageObject, degrees: int) -> PageObject:
    rotation = degrees % 360
    if not rotation:
        return page
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    target_width = width
    target_height = height
    if rotation in (90, 270):
        target_width, target_height = height, width

    rotated = PageObject.create_blank_page(width=target_width, height=target_height)
    transform = Transformation().rotate(rotation)
    if rotation == 90:
        transform = transform.translate(height, 0)
    elif rotation == 180:
        transform = transform.translate(width, height)
    elif rotation == 270:
        transform = transform.translate(0, width)

    _merge_with_transform(rotated, page, transform)
    _force_rotation_zero(rotated)
    return rotated


def _merge_with_transform(
    target: PageObject, source: PageObject, transform: Transformation
) -> None:
    merge_transformed = getattr(target, "merge_transformed_page", None)
    if callable(merge_transformed):
        merge_transformed(source, transform)
        return

    temp = PageObject.create_blank_page(
        width=target.mediabox.width,
        height=target.mediabox.height,
    )
    temp_merge = getattr(temp, "merge_transformed_page", None)
    if callable(temp_merge):
        temp_merge(source, transform)
    else:
        source.add_transformation(transform)
        temp.merge_page(source)
    target.merge_page(temp)


def _force_rotation_zero(page: PageObject) -> None:
    try:
        page[NameObject("/Rotate")] = NumberObject(0)
    except Exception:
        pass


def _describe_page(page: PageObject) -> str:
    rotation = int(page.get("/Rotate", 0) or 0) % 360
    mediabox = _format_box(page.mediabox)
    cropbox = _format_optional_box(page, "cropbox")
    trimbox = _format_optional_box(page, "trimbox")
    return f"rotate={rotation} mediabox={mediabox} cropbox={cropbox} trimbox={trimbox}"


def _format_box(box) -> str:
    try:
        llx = float(box.lower_left[0])
        lly = float(box.lower_left[1])
        width = float(box.width)
        height = float(box.height)
        return f"{width:.2f}x{height:.2f} ll=({llx:.2f},{lly:.2f})"
    except Exception:
        return "unavailable"


def _format_optional_box(page: PageObject, name: str) -> str:
    try:
        box = getattr(page, name)
        if box is None:
            return "none"
        return _format_box(box)
    except Exception:
        return "unavailable"


def _write_debug_report(export_dir: Path, lines: list[str]) -> Path | None:
    if not lines:
        return None
    export_dir.mkdir(parents=True, exist_ok=True)
    report_path = export_dir / f"{_export_filename()[:-4]}_debug.txt"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def _log(callback: Callable[[str], None] | None, message: str) -> None:
    if callback:
        callback(message)


def _report_progress(
    callback: Callable[[int, int], None] | None,
    completed: int,
    total: int,
) -> None:
    if callback and total > 0:
        callback(completed, total)
