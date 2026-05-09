"""Filename parsing + formatting + metadata resolution."""

import re
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from api_client import MangaAPIClient, MangaResult, VolumeData


@dataclass
class ParsedFilename:
    raw: str = ""
    manga_name: str = ""
    volume: str = ""
    chapter: str = ""
    group: str = ""
    year: str = ""
    extra: str = ""
    source_pattern: str = ""
    is_volume_only: bool = False  # True if volume but no chapter


@dataclass
class FullMetadata:
    parsed: ParsedFilename = field(default_factory=ParsedFilename)
    manga_title: str = ""
    manga_title_english: str = ""
    manga_title_japanese: str = ""
    authors: list[str] = field(default_factory=list)
    artists: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    year: int = 0
    status: str = ""
    volume_title: str = ""
    chapter_range: str = ""
    chapter_count: int = 0
    release_date: str = ""
    score: float = 0.0
    cover_url: str = ""
    volume_cover_url: str = ""
    mal_id: int = 0
    mangadex_id: str = ""
    anilist_id: int = 0
    api_sources: list[str] = field(default_factory=list)

    @property
    def display_title(self):
        return self.manga_title_english or self.manga_title or self.parsed.manga_name

    @property
    def author_str(self):
        return ", ".join(self.authors) if self.authors else "Unknown"


_PATTERNS = []


def _p(pattern, desc, flags=re.IGNORECASE):
    _PATTERNS.append((re.compile(pattern, flags), desc))


# Volume + chapter
_p(r"^(?P<name>.+?)\s+v(?P<vol>\d+)\s*(?:c(?P<ch>[\d\.\-]+))?\s*(?:\((?P<year>\d{4})\))?\s*(?:\[(?P<group>[^\]]+)\])?\s*$", "name v01")
_p(r"^(?P<name>.+?)\s+Vol\.?\s*(?P<vol>\d+)\s*(?:Ch\.?\s*(?P<ch>[\d\.\-]+))?\s*(?:\((?P<year>\d{4})\))?\s*(?:\[(?P<group>[^\]]+)\])?\s*$", "name Vol.01")
_p(r"^(?P<name>.+?)\s+Volume\s*(?P<vol>\d+)\s*(?:Chapter\s*(?P<ch>[\d\.\-]+))?\s*(?:\((?P<year>\d{4})\))?\s*$", "name Volume 01")
_p(r"^(?P<name>.+?)\s+Tome?\s*(?P<vol>\d+)\s*(?:\((?P<year>\d{4})\))?\s*$", "name Tome 01")
_p(r"^(?P<name>.+?)\s+Band\s*(?P<vol>\d+)\s*(?:\((?P<year>\d{4})\))?\s*$", "name Band 01")
_p(r"^(?P<name>.+?)\s+#(?P<vol>\d+)\s*(?:\((?P<year>\d{4})\))?\s*$", "name #01")
_p(r"^\[(?P<group>[^\]]+)\]\s*(?P<name>.+?)\s+v(?P<vol>\d+)\s*(?:c(?P<ch>[\d\.\-]+))?\s*$", "[grp] name v01")
_p(r"^\[(?P<group>[^\]]+)\]\s*(?P<name>.+?)\s*[-–—]\s*Vol\.?\s*(?P<vol>\d+)\s*$", "[grp] name - Vol.01")
_p(r"^(?P<name>.+?)\s*[-–—]\s*v(?P<vol>\d+)\s*(?:c(?P<ch>[\d\.\-]+))?\s*$", "name - v01")
_p(r"^(?P<name>.+?)\s*[-–—]\s*Vol\.?\s*(?P<vol>\d+)\s*$", "name - Vol.01")
_p(r"^(?P<name>.+?)\s+v(?P<vol>\d+)\s*[-–—]\s*c(?P<ch>[\d\.\-]+)\s*$", "name v01 - c001")
_p(r"^(?P<name>.+?)\s*[-–—]\s*(?P<vol>\d{1,3})\s*$", "name - 01")

# Chapter only
_p(r"^(?P<name>.+?)\s+(?:c|ch\.?)\s*(?P<ch>[\d\.\-]+)\s*$", "name c001")
_p(r"^(?P<name>.+?)\s+Chapter\s*(?P<ch>[\d\.\-]+)\s*$", "name Chapter 001")
_p(r"^(?P<name>.+?)\s*[-–—]\s*Chapter\s*(?P<ch>[\d\.\-]+)\s*$", "name - Chapter 001")
_p(r"^(?P<name>.+?)\s*[-–—]\s*(?:c|ch\.?)\s*(?P<ch>[\d\.\-]+)\s*$", "name - c001")

# Underscores / dots
_p(r"^(?P<name>.+?)_v(?P<vol>\d+)(?:_c(?P<ch>[\d\.\-]+))?\s*$", "name_v01")
_p(r"^(?P<name>.+?)\.v(?P<vol>\d+)(?:\.c(?P<ch>[\d\.\-]+))?\s*$", "name.v01")

# Number at end fallback
_p(r"^(?P<name>.+?)\s+(?P<vol>\d{1,3})\s*$", "name 01")


def parse_filename(filename: str) -> ParsedFilename:
    stem = Path(filename).stem.strip()
    clean = stem
    clean = re.sub(r"\s*\(pg\s+\d+[^)]*\)", "", clean)
    clean = re.sub(r"\s*\(Digital\)", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s*\(f\)", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+END\s*$", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+FIN\s*$", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s*\{[^}]+\}", "", clean)
    clean = re.sub(r"\s+", " ", clean).strip()

    for pattern, desc in _PATTERNS:
        m = pattern.match(clean)
        if m:
            g = m.groupdict()
            name = g.get("name", "").strip()
            name = re.sub(r"[\s_\-]+$", "", name)
            name = re.sub(r"_", " ", name)

            vol = g.get("vol", "") or ""
            ch = g.get("ch", "") or ""
            if vol:
                vol = vol.lstrip("0") or "0"
                if len(vol) == 1:
                    vol = f"0{vol}"

            return ParsedFilename(
                raw=stem, manga_name=name, volume=vol, chapter=ch,
                group=g.get("group", "") or "",
                year=g.get("year", "") or "",
                source_pattern=desc,
                is_volume_only=bool(vol and not ch),
            )

    return ParsedFilename(raw=stem, manga_name=re.sub(r"_", " ", stem), source_pattern="fallback")


DEFAULT_FORMAT = "{manga_name} Vol.{volume} - Ch.{chapter} [{volume_title}] ({date})"

AVAILABLE_VARIABLES = {
    "{manga_name}": "Official manga title",
    "{manga_name_english}": "English title",
    "{manga_name_japanese}": "Japanese title",
    "{volume}": "Volume number",
    "{chapter}": "Chapter number/range",
    "{volume_title}": "Volume title (from API)",
    "{date}": "Release date",
    "{year}": "Publication year",
    "{author}": "Author(s)",
    "{artist}": "Artist(s)",
    "{genre}": "Genres",
    "{status}": "Status",
    "{group}": "Scanlation group",
    "{score}": "Score",
    "{original_filename}": "Original filename",
}


def format_output_name(metadata: FullMetadata, fmt: str = DEFAULT_FORMAT) -> str:
    artists_str = ", ".join(metadata.artists) if metadata.artists else metadata.author_str

    replacements = {
        "{manga_name}": metadata.display_title or "Unknown",
        "{manga_name_english}": metadata.manga_title_english,
        "{manga_name_japanese}": metadata.manga_title_japanese,
        "{volume}": metadata.parsed.volume,
        "{chapter}": metadata.chapter_range or metadata.parsed.chapter,
        "{volume_title}": metadata.volume_title,
        "{date}": metadata.release_date,
        "{year}": str(metadata.year) if metadata.year else metadata.parsed.year,
        "{author}": metadata.author_str if metadata.authors else "",
        "{artist}": artists_str if metadata.artists or metadata.authors else "",
        "{genre}": ", ".join(metadata.genres[:3]) if metadata.genres else "",
        "{status}": metadata.status,
        "{group}": metadata.parsed.group,
        "{score}": f"{metadata.score:.1f}" if metadata.score else "",
        "{original_filename}": metadata.parsed.raw,
    }
    result = fmt
    for var, val in replacements.items():
        result = result.replace(var, val or "")

    result = re.sub(r"\[\s*\]", "", result)
    result = re.sub(r"\(\s*\)", "", result)
    result = re.sub(r"\s*\|\s*\|\s*", " | ", result)
    result = re.sub(r"^\s*\|\s*", "", result)
    result = re.sub(r"\s*\|\s*$", "", result)
    result = re.sub(r"\s*-\s*-\s*", " - ", result)
    result = re.sub(r"\s+-\s*$", "", result)
    result = re.sub(r"^\s*-\s+", "", result)
    result = re.sub(r"\s{2,}", " ", result)
    result = result.strip(" -|,")
    result = re.sub(r'[<>:"/\\|?*]', "", result)
    return result if result else metadata.parsed.raw or "output"


class MetadataResolver:
    def __init__(self):
        self.api = MangaAPIClient()

    def auto_detect(self, filename, log_cb=None):
        log = log_cb or (lambda m: None)
        parsed = parse_filename(filename)
        log(f"Parsed: '{parsed.manga_name}' vol={parsed.volume} ch={parsed.chapter or '(none)'} [{parsed.source_pattern}]")
        if parsed.is_volume_only:
            log(f"  → Volume-only file detected")

        results = []
        if parsed.manga_name:
            log(f"Searching all APIs (parallel)...")
            try:
                results = self.api.search_manga(parsed.manga_name, limit=8)
                if results:
                    log(f"Found {len(results)} results")
                    for r in results[:3]:
                        log(f"  • {r.title} [{', '.join(r.sources_merged)}]")
                else:
                    log("No results from any API")
            except Exception as e:
                log(f"Search failed: {e}")
        return parsed, results

    def resolve_file(
        self, filename, selected_manga=None,
        title_override="", author_override="",
        voltitle_override="", date_override="",
        log_cb=None,
    ) -> FullMetadata:
        log = log_cb or (lambda m: None)
        parsed = parse_filename(filename)
        meta = FullMetadata(parsed=parsed)

        meta.manga_title = title_override or (selected_manga.title if selected_manga else parsed.manga_name)
        meta.manga_title_english = title_override or (selected_manga.title_english if selected_manga else "")
        meta.parsed.manga_name = title_override or parsed.manga_name

        if author_override:
            meta.authors = [a.strip() for a in author_override.split(",") if a.strip()]
        elif selected_manga and selected_manga.authors:
            meta.authors = selected_manga.authors

        if selected_manga:
            meta.manga_title_japanese = selected_manga.title_japanese
            meta.artists = selected_manga.artists
            meta.genres = selected_manga.genres
            meta.status = selected_manga.status
            meta.year = selected_manga.year
            meta.score = selected_manga.score
            meta.cover_url = selected_manga.cover_url
            meta.mal_id = selected_manga.mal_id
            meta.mangadex_id = selected_manga.mangadex_id
            meta.anilist_id = selected_manga.anilist_id
            meta.api_sources = selected_manga.sources_merged

        # Per-volume data fetch (works for chapter or volume-only files)
        vol = parsed.volume
        if vol and selected_manga:
            log(f"Aggregating volume {vol} data from {len(selected_manga.sources_merged)} source(s)...")
            try:
                vd = self.api.get_volume_data(selected_manga, vol)

                if vd.chapter_range:
                    meta.chapter_range = vd.chapter_range
                    log(f"  Ch: {vd.chapter_range}")
                elif parsed.chapter:
                    meta.chapter_range = parsed.chapter

                if vd.chapter_count:
                    meta.chapter_count = vd.chapter_count

                if vd.volume_title and not voltitle_override:
                    meta.volume_title = vd.volume_title
                    log(f"  Title: {vd.volume_title}")

                if vd.release_date and not date_override:
                    meta.release_date = vd.release_date
                    log(f"  Date: {vd.release_date}")

                if vd.cover_url:
                    meta.volume_cover_url = vd.cover_url
                    log(f"  Cover: vol-specific")

                if vd.sources:
                    log(f"  Sources used: {', '.join(vd.sources)}")
            except Exception as e:
                log(f"  Vol fetch error: {e}")
        elif parsed.chapter:
            meta.chapter_range = parsed.chapter

        if voltitle_override:
            meta.volume_title = voltitle_override
        if date_override:
            meta.release_date = date_override

        return meta