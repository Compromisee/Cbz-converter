"""
Multi-API manga client — aggregates data from multiple sources simultaneously.
Properly handles volume-only files with cover art and metadata fallbacks.
"""

import re
import time
import threading
import requests
from typing import Optional
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class MangaResult:
    mal_id: int = 0
    mangadex_id: str = ""
    anilist_id: int = 0
    kitsu_id: str = ""
    title: str = ""
    title_english: str = ""
    title_japanese: str = ""
    authors: list[str] = field(default_factory=list)
    artists: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    status: str = ""
    year: int = 0
    synopsis: str = ""
    cover_url: str = ""
    volumes_total: int = 0
    chapters_total: int = 0
    score: float = 0.0
    source: str = ""
    sources_merged: list[str] = field(default_factory=list)

    def to_dict(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__}

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def merge_from(self, other: "MangaResult"):
        """Fill in missing fields from another source."""
        if not self.title_english and other.title_english:
            self.title_english = other.title_english
        if not self.title_japanese and other.title_japanese:
            self.title_japanese = other.title_japanese
        if not self.authors and other.authors:
            self.authors = other.authors
        if not self.artists and other.artists:
            self.artists = other.artists
        if not self.genres and other.genres:
            self.genres = other.genres
        if not self.tags and other.tags:
            self.tags = other.tags
        if not self.status and other.status:
            self.status = other.status
        if not self.year and other.year:
            self.year = other.year
        if not self.synopsis and other.synopsis:
            self.synopsis = other.synopsis
        if not self.cover_url and other.cover_url:
            self.cover_url = other.cover_url
        if not self.volumes_total and other.volumes_total:
            self.volumes_total = other.volumes_total
        if not self.chapters_total and other.chapters_total:
            self.chapters_total = other.chapters_total
        if not self.score and other.score:
            self.score = other.score
        if not self.mal_id and other.mal_id:
            self.mal_id = other.mal_id
        if not self.anilist_id and other.anilist_id:
            self.anilist_id = other.anilist_id
        if not self.kitsu_id and other.kitsu_id:
            self.kitsu_id = other.kitsu_id
        if not self.mangadex_id and other.mangadex_id:
            self.mangadex_id = other.mangadex_id
        if other.source and other.source not in self.sources_merged:
            self.sources_merged.append(other.source)


@dataclass
class VolumeData:
    """Per-volume info aggregated from multiple sources."""
    volume: str = ""
    chapter_range: str = ""
    chapter_count: int = 0
    volume_title: str = ""
    release_date: str = ""
    cover_url: str = ""
    chapters: list[dict] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


class MangaAPIClient:
    """Multi-source aggregating API client."""

    MDEX = "https://api.mangadex.org"
    MDEX_UPLOADS = "https://uploads.mangadex.org"
    JIKAN = "https://api.jikan.moe/v4"
    ANILIST = "https://graphql.anilist.co"
    KITSU = "https://kitsu.io/api/edge"

    def __init__(self, timeout: int = 12):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "CBZ-Converter/5.0"
        self.timeout = timeout
        self._jikan_lock = threading.Lock()
        self._last_jikan = 0
        self._cache = {}
        self._cache_lock = threading.Lock()

    def _jikan_wait(self):
        with self._jikan_lock:
            elapsed = time.time() - self._last_jikan
            if elapsed < 0.5:
                time.sleep(0.5 - elapsed)
            self._last_jikan = time.time()

    # ── Aggregated search ─────────────────────────────────────────────────

    def search_manga(self, query: str, limit: int = 10) -> list[MangaResult]:
        """Search all APIs in parallel and merge results."""
        if not query.strip():
            return []

        cache_key = f"search:{query.lower().strip()}:{limit}"
        with self._cache_lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        # Parallel API calls
        api_results = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(self._safe_search, "mangadex", query, limit): "mangadex",
                pool.submit(self._safe_search, "jikan", query, limit): "jikan",
                pool.submit(self._safe_search, "anilist", query, limit): "anilist",
                pool.submit(self._safe_search, "kitsu", query, limit): "kitsu",
            }
            for fut in as_completed(futures):
                src = futures[fut]
                try:
                    api_results[src] = fut.result()
                except Exception as e:
                    print(f"  [API] {src} error: {e}")
                    api_results[src] = []

        # Merge results by title similarity
        merged = []
        seen_titles = {}

        # Priority: MangaDex first (best for volume covers/data)
        for src in ["mangadex", "anilist", "jikan", "kitsu"]:
            for r in api_results.get(src, []):
                key = self._normalize_title(r.title)
                if key in seen_titles:
                    # Merge into existing
                    existing_idx = seen_titles[key]
                    merged[existing_idx].merge_from(r)
                else:
                    if not r.sources_merged:
                        r.sources_merged = [r.source]
                    seen_titles[key] = len(merged)
                    merged.append(r)

        # Cross-fill: try to get mangadex_id for top results
        for r in merged[:5]:
            if not r.mangadex_id:
                try:
                    r.mangadex_id = self._find_mdex_id(r.title)
                except Exception:
                    pass

        merged = merged[:limit]
        with self._cache_lock:
            self._cache[cache_key] = merged
        return merged

    def _safe_search(self, source, query, limit):
        try:
            if source == "mangadex":
                return self._search_mangadex(query, limit)
            elif source == "jikan":
                return self._search_jikan(query, limit)
            elif source == "anilist":
                return self._search_anilist(query, limit)
            elif source == "kitsu":
                return self._search_kitsu(query, limit)
        except Exception:
            return []
        return []

    @staticmethod
    def _normalize_title(t):
        return re.sub(r"[^a-z0-9]+", "", (t or "").lower())

    # ── MangaDex search ───────────────────────────────────────────────────

    def _search_mangadex(self, q, limit):
        resp = self.session.get(
            f"{self.MDEX}/manga",
            params={
                "title": q, "limit": limit,
                "includes[]": ["author", "artist", "cover_art"],
                "contentRating[]": ["safe", "suggestive", "erotica"],
                "order[relevance]": "desc",
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        out = []
        for it in resp.json().get("data", []):
            a = it.get("attributes", {})

            title = ""
            for lang in ["en", "ja-ro", "ja"]:
                title = a.get("title", {}).get(lang, "")
                if title:
                    break
            if not title:
                t = a.get("title", {})
                title = next(iter(t.values()), "?") if t else "?"

            title_en = ""
            for alt in a.get("altTitles", []):
                if "en" in alt and not title_en:
                    title_en = alt["en"]

            title_jp = a.get("title", {}).get("ja", "") or a.get("title", {}).get("ja-ro", "")

            authors = []
            artists = []
            cover_fn = ""
            for rel in it.get("relationships", []):
                attrs = rel.get("attributes")
                if not attrs:
                    continue
                if rel["type"] == "author":
                    n = attrs.get("name", "")
                    if n: authors.append(n)
                elif rel["type"] == "artist":
                    n = attrs.get("name", "")
                    if n: artists.append(n)
                elif rel["type"] == "cover_art":
                    cover_fn = attrs.get("fileName", "")

            cover = (
                f"{self.MDEX_UPLOADS}/covers/{it['id']}/{cover_fn}.512.jpg"
                if cover_fn else ""
            )

            tags = []
            for tag in a.get("tags", []):
                tn = tag.get("attributes", {}).get("name", {}).get("en", "")
                if tn:
                    tags.append(tn)

            out.append(MangaResult(
                mangadex_id=it["id"],
                title=title,
                title_english=title_en,
                title_japanese=title_jp,
                authors=authors,
                artists=artists,
                genres=tags[:5],
                tags=tags,
                status=a.get("status") or "",
                year=a.get("year") or 0,
                synopsis=(a.get("description", {}).get("en") or "")[:500],
                cover_url=cover,
                source="MangaDex",
                sources_merged=["MangaDex"],
            ))
        return out

    # ── Jikan ─────────────────────────────────────────────────────────────

    def _search_jikan(self, q, limit):
        self._jikan_wait()
        resp = self.session.get(
            f"{self.JIKAN}/manga",
            params={"q": q, "limit": limit, "type": "manga"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        out = []
        for it in resp.json().get("data", []):
            authors = [a.get("name", "") for a in it.get("authors", [])]
            out.append(MangaResult(
                mal_id=it.get("mal_id", 0),
                title=it.get("title", ""),
                title_english=it.get("title_english") or "",
                title_japanese=it.get("title_japanese") or "",
                authors=authors,
                artists=authors,
                genres=[g.get("name", "") for g in it.get("genres", [])],
                status=it.get("status") or "",
                year=it.get("year") or 0,
                synopsis=(it.get("synopsis") or "")[:500],
                cover_url=it.get("images", {}).get("jpg", {}).get("large_image_url") or
                          it.get("images", {}).get("jpg", {}).get("image_url", ""),
                chapters_total=it.get("chapters") or 0,
                volumes_total=it.get("volumes") or 0,
                score=it.get("score") or 0.0,
                source="MAL",
                sources_merged=["MAL"],
            ))
        return out

    # ── AniList ───────────────────────────────────────────────────────────

    def _search_anilist(self, q, limit):
        query = """
        query ($search: String, $perPage: Int) {
          Page(perPage: $perPage) {
            media(search: $search, type: MANGA) {
              id idMal
              title { romaji english native }
              status
              startDate { year }
              chapters volumes
              averageScore
              genres tags { name }
              description(asHtml: false)
              coverImage { large extraLarge }
              staff(perPage: 6) {
                edges { role node { name { full } } }
              }
            }
          }
        }
        """
        resp = self.session.post(
            self.ANILIST,
            json={"query": query, "variables": {"search": q, "perPage": limit}},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {}).get("Page", {}).get("media", [])
        out = []
        for m in data:
            authors = []
            artists = []
            for edge in m.get("staff", {}).get("edges", []):
                role = (edge.get("role") or "").lower()
                name = edge.get("node", {}).get("name", {}).get("full", "")
                if not name:
                    continue
                if "story" in role and "art" in role:
                    if name not in authors: authors.append(name)
                    if name not in artists: artists.append(name)
                elif "story" in role:
                    if name not in authors: authors.append(name)
                elif "art" in role:
                    if name not in artists: artists.append(name)

            t = m.get("title", {})
            cover = m.get("coverImage", {}).get("extraLarge") or m.get("coverImage", {}).get("large", "")

            out.append(MangaResult(
                anilist_id=m.get("id", 0),
                mal_id=m.get("idMal") or 0,
                title=t.get("romaji") or t.get("english") or "?",
                title_english=t.get("english") or "",
                title_japanese=t.get("native") or "",
                authors=authors,
                artists=artists,
                genres=m.get("genres", []),
                tags=[tg.get("name", "") for tg in m.get("tags", [])][:10],
                status=(m.get("status") or "").replace("_", " ").title(),
                year=m.get("startDate", {}).get("year") or 0,
                synopsis=re.sub(r"<[^>]+>", "", m.get("description") or "")[:500],
                cover_url=cover,
                chapters_total=m.get("chapters") or 0,
                volumes_total=m.get("volumes") or 0,
                score=(m.get("averageScore") or 0) / 10,
                source="AniList",
                sources_merged=["AniList"],
            ))
        return out

    # ── Kitsu ─────────────────────────────────────────────────────────────

    def _search_kitsu(self, q, limit):
        resp = self.session.get(
            f"{self.KITSU}/manga",
            params={"filter[text]": q, "page[limit]": limit},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        out = []
        for it in data:
            a = it.get("attributes", {})
            titles = a.get("titles", {})
            cover = ""
            poster = a.get("posterImage")
            if poster:
                cover = poster.get("large") or poster.get("medium") or poster.get("original", "")

            out.append(MangaResult(
                kitsu_id=it.get("id", ""),
                title=a.get("canonicalTitle") or titles.get("en") or titles.get("en_jp") or "?",
                title_english=titles.get("en", ""),
                title_japanese=titles.get("ja_jp", ""),
                status=a.get("status") or "",
                year=int((a.get("startDate") or "0000")[:4]) if a.get("startDate") else 0,
                synopsis=(a.get("synopsis") or "")[:500],
                cover_url=cover,
                chapters_total=a.get("chapterCount") or 0,
                volumes_total=a.get("volumeCount") or 0,
                score=float(a.get("averageRating", 0) or 0) / 10 if a.get("averageRating") else 0,
                source="Kitsu",
                sources_merged=["Kitsu"],
            ))
        return out

    def _find_mdex_id(self, title):
        try:
            resp = self.session.get(
                f"{self.MDEX}/manga",
                params={"title": title, "limit": 1},
                timeout=8,
            )
            resp.raise_for_status()
            d = resp.json().get("data", [])
            return d[0]["id"] if d else ""
        except Exception:
            return ""

    # ─────────────────────────────────────────────────────────────────────
    #  VOLUME DATA — Aggregated from multiple sources
    # ─────────────────────────────────────────────────────────────────────

    def get_volume_data(
        self,
        manga: MangaResult,
        volume: str,
    ) -> VolumeData:
        """
        Aggregate volume data from ALL available APIs.
        Returns volume info with chapter range, title, date, AND cover art.
        Works even for volume-only files (no chapters).
        """
        cache_key = f"voldata:{manga.mangadex_id or manga.mal_id or manga.anilist_id}:{volume}"
        with self._cache_lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        if not volume:
            return VolumeData(volume=volume)

        result = VolumeData(volume=volume)

        # Run multiple sources in parallel
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {}
            if manga.mangadex_id:
                futures[pool.submit(self._mdex_volume_full, manga.mangadex_id, volume)] = "mangadex"
                futures[pool.submit(self._mdex_volume_cover, manga.mangadex_id, volume)] = "mdex_cover"
            if manga.anilist_id:
                futures[pool.submit(self._anilist_volume_data, manga.anilist_id, volume)] = "anilist"

            for fut in as_completed(futures):
                src = futures[fut]
                try:
                    data = fut.result()
                    if not data:
                        continue
                    self._merge_volume_data(result, data, src)
                except Exception as e:
                    print(f"  [vol API] {src} error: {e}")

        # If we still have nothing, build estimated chapter range from manga totals
        if not result.chapter_range and manga.volumes_total and manga.chapters_total:
            result.chapter_range = self._estimate_chapter_range(
                volume, manga.volumes_total, manga.chapters_total
            )

        with self._cache_lock:
            self._cache[cache_key] = result
        return result

    @staticmethod
    def _merge_volume_data(target: VolumeData, source: dict, src_name: str):
        if source.get("chapter_range") and not target.chapter_range:
            target.chapter_range = source["chapter_range"]
        if source.get("chapter_count") and source["chapter_count"] > target.chapter_count:
            target.chapter_count = source["chapter_count"]
        if source.get("volume_title") and not target.volume_title:
            target.volume_title = source["volume_title"]
        if source.get("release_date") and not target.release_date:
            target.release_date = source["release_date"]
        if source.get("cover_url") and not target.cover_url:
            target.cover_url = source["cover_url"]
        if source.get("chapters") and not target.chapters:
            target.chapters = source["chapters"]
        if src_name not in target.sources:
            target.sources.append(src_name)

    @staticmethod
    def _estimate_chapter_range(volume: str, total_vols: int, total_chs: int) -> str:
        """Estimate chapter range when API doesn't provide it."""
        try:
            v = int(volume.lstrip("0") or "0")
            if v <= 0 or total_vols <= 0:
                return ""
            chs_per_vol = total_chs / total_vols
            start = int((v - 1) * chs_per_vol) + 1
            end = int(v * chs_per_vol)
            if start == end:
                return str(start)
            return f"{start}-{end}"
        except Exception:
            return ""

    # ── MangaDex volume data ──────────────────────────────────────────────

    def _mdex_volume_full(self, mdex_id, volume):
        """Get all chapters in a volume from MangaDex feed."""
        all_ch = []
        offset = 0

        try:
            while True:
                resp = self.session.get(
                    f"{self.MDEX}/manga/{mdex_id}/feed",
                    params={
                        "translatedLanguage[]": "en",
                        "volume[]": volume,
                        "order[chapter]": "asc",
                        "limit": 100,
                        "offset": offset,
                    },
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                batch = resp.json().get("data", [])
                for ch in batch:
                    at = ch.get("attributes", {})
                    all_ch.append({
                        "chapter": at.get("chapter") or "",
                        "title": at.get("title") or "",
                        "date": (at.get("publishAt") or "")[:10],
                    })
                if len(batch) < 100:
                    break
                offset += 100
        except Exception:
            pass

        # Fallback: aggregate endpoint (works for vol-only data)
        if not all_ch:
            try:
                resp = self.session.get(
                    f"{self.MDEX}/manga/{mdex_id}/aggregate",
                    params={"translatedLanguage[]": "en"},
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                vols = resp.json().get("volumes", {})
                if volume in vols:
                    chs = vols[volume].get("chapters", {})
                    nums = sorted(
                        chs.keys(),
                        key=lambda x: float(x) if x.replace(".", "").isdigit() else 999,
                    )
                    cr = f"{nums[0]}-{nums[-1]}" if len(nums) > 1 else (nums[0] if nums else "")
                    return {"chapter_range": cr, "chapter_count": vols[volume].get("count", 0)}
            except Exception:
                pass
            return {}

        # Dedupe + sort
        seen = set()
        unique = []
        for c in all_ch:
            k = c["chapter"]
            if k and k not in seen:
                unique.append(c); seen.add(k)
            elif not k:
                unique.append(c)
        unique.sort(key=lambda c: float(c["chapter"]) if c["chapter"].replace(".", "").isdigit() else 999)

        ch_nums = [c["chapter"] for c in unique if c["chapter"]]
        ch_range = f"{ch_nums[0]}-{ch_nums[-1]}" if len(ch_nums) > 1 else (ch_nums[0] if ch_nums else "")

        # Volume title: skip generic titles
        vol_title = ""
        for c in unique:
            t = c.get("title", "").strip()
            if t and not re.match(r"^(chapter|ch\.?|episode|ep\.?|part|pt\.?)\s*[\d.]+$", t, re.IGNORECASE):
                vol_title = t
                break

        dates = sorted([c["date"] for c in unique if c["date"] and len(c["date"]) >= 10])

        return {
            "chapter_range": ch_range,
            "chapter_count": len(unique),
            "volume_title": vol_title,
            "release_date": dates[0] if dates else "",
            "chapters": unique,
        }

    def _mdex_volume_cover(self, mdex_id, volume):
        """Get the cover art for a specific volume."""
        try:
            resp = self.session.get(
                f"{self.MDEX}/cover",
                params={
                    "manga[]": mdex_id,
                    "limit": 100,
                    "order[volume]": "asc",
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            covers = resp.json().get("data", [])

            # Find cover matching this volume
            target_vol = volume.lstrip("0") or "0"
            for cov in covers:
                attrs = cov.get("attributes", {})
                cv = (attrs.get("volume") or "").lstrip("0") or "0"
                if cv == target_vol:
                    fn = attrs.get("fileName", "")
                    if fn:
                        return {
                            "cover_url": f"{self.MDEX_UPLOADS}/covers/{mdex_id}/{fn}.512.jpg",
                            "release_date": (attrs.get("createdAt") or "")[:10],
                        }
        except Exception:
            pass
        return {}

    # ── AniList volume data (limited) ─────────────────────────────────────

    def _anilist_volume_data(self, anilist_id, volume):
        """AniList doesn't have per-volume data, but we can confirm volume exists."""
        query = """
        query ($id: Int) {
          Media(id: $id, type: MANGA) {
            volumes chapters
          }
        }
        """
        try:
            resp = self.session.post(
                self.ANILIST,
                json={"query": query, "variables": {"id": anilist_id}},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            m = resp.json().get("data", {}).get("Media", {})
            total_vols = m.get("volumes") or 0
            total_chs = m.get("chapters") or 0
            if total_vols and total_chs:
                ch_range = MangaAPIClient._estimate_chapter_range(volume, total_vols, total_chs)
                if ch_range:
                    return {"chapter_range": ch_range}
        except Exception:
            pass
        return {}