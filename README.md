<div align="center">

# 📚 CBZ Manga Converter

### Convert CBZ comic archives to EPUB and PDF — with automatic manga metadata, multi-API lookup, and parallel processing

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg?style=flat-square)](#installation)
[![Threading](https://img.shields.io/badge/multithreaded-✓-brightgreen.svg?style=flat-square)](#performance)
[![APIs](https://img.shields.io/badge/APIs-MangaDex%20%7C%20MAL%20%7C%20AniList%20%7C%20Kitsu-ef4444.svg?style=flat-square)](#metadata-sources)

[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](CONTRIBUTING.md)
[![Made with Love](https://img.shields.io/badge/made%20with-❤-red.svg?style=flat-square)](https://github.com)
[![Stars](https://img.shields.io/badge/⭐-star%20this%20repo-yellow.svg?style=flat-square)](#)

**Three interfaces · Four metadata APIs · Smart batch renaming · Lightning-fast parallel conversion**

[🚀 Quick Start](#-quick-start) · [📖 Documentation](#-table-of-contents) · [💡 Examples](#-examples) · [🐛 Issues](#)

---

</div>

## ✨ Features at a Glance

<table>
<tr>
<td width="50%">

### 🎯 Smart Conversion
- **CBZ → PDF** with `img2pdf` (lossless) or `reportlab`
- **CBZ → EPUB3** fixed-layout for e-readers
- **Auto page-size detection** from source images
- **Per-image quality** control (1-100)

</td>
<td width="50%">

### ⚡ Multi-Threaded
- Parallel batch conversion with thread pools
- Configurable workers (1-16)
- Live per-worker progress bars
- Cancellation support
- ~5x faster on multi-volume series

</td>
</tr>
<tr>
<td width="50%">

### 🔍 Metadata Engine
- **4 APIs queried in parallel:** MangaDex, MyAnimeList, AniList, Kitsu
- Automatic data merging (best of each)
- 25+ filename pattern matchers
- Per-volume chapter ranges & dates
- Volume cover art retrieval

</td>
<td width="50%">

### 🎨 Three Interfaces
- **CLI** with colored progress bars
- **Tkinter GUI** with dark theme
- **Web Dashboard** with live polling
- Dry-run mode for previewing
- Drag-and-drop file uploads

</td>
</tr>
</table>

---

## 📑 Table of Contents

- [✨ Features at a Glance](#-features-at-a-glance)
- [🚀 Quick Start](#-quick-start)
- [📦 Installation](#-installation)
  - [Requirements](#requirements)
  - [Optional Dependencies](#optional-dependencies)
- [🎮 Usage](#-usage)
  - [Web Dashboard](#-web-dashboard)
  - [Tkinter GUI](#-tkinter-gui)
  - [Command Line](#-command-line)
- [💡 Examples](#-examples)
- [📝 Naming Variables](#-naming-variables)
- [🌐 Metadata Sources](#-metadata-sources)
- [🧠 Filename Parsing](#-filename-parsing)
- [⚙️ Configuration](#️-configuration)
- [📊 Performance](#-performance)
- [🏗️ Architecture](#️-architecture)
- [🛠️ Troubleshooting](#️-troubleshooting)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

---

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/Compromisee/cbz-converter.git
cd cbz-converter

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run!
python converter.py --web              # Web dashboard (recommended)
python converter.py --gui              # Desktop GUI
python converter.py *.cbz --auto       # CLI batch with auto-metadata
```

> 💡 **First time?** Open the **web dashboard** — it's the most intuitive way to convert and rename your manga collection.

---

## 📦 Installation

### Requirements

| Package | Purpose | Required |
|---------|---------|----------|
| `Pillow` | Image processing | ✅ Yes |
| `requests` | API calls | ✅ Yes |
| `flask` | Web dashboard | ⚪ Optional |
| `img2pdf` | Lossless PDF generation | ⚪ Recommended |
| `reportlab` | Alternative PDF engine | ⚪ Optional |
| `colorama` | Colored terminal output | ⚪ Optional |
| `tkinter` | Desktop GUI | ⚪ Built-in (most systems) |

#### Install Everything

```bash
pip install -r requirements.txt
```

#### Install Selectively

```bash
# Bare minimum (CLI only, PDF only)
pip install Pillow img2pdf requests

# Everything
pip install Pillow img2pdf reportlab requests flask colorama
```

### Optional Dependencies

- **`tkinter`** is included with Python on Windows and macOS. On Debian/Ubuntu Linux: `sudo apt install python3-tk`
- **`img2pdf`** produces smaller, lossless PDFs but only works with JPEG/PNG sources
- **`reportlab`** is more flexible (per-page sizing) but recompresses images

---

## 🎮 Usage

### 🌐 Web Dashboard

The web dashboard is the most feature-complete interface — open it in any browser.

```bash
python converter.py --web
# → opens http://localhost:5000

python converter.py --web --web-port 8080  # custom port
```

**Features:**
- 🎨 Dark theme with red & blue accents
- 📂 Drag-and-drop file uploads
- 🔍 Live manga search with API source tags
- 🏷️ Per-file metadata preview
- 📊 Real-time progress polling
- 💾 Per-file download links
- 👁️ Dry-run mode
- 📁 Custom output directory or auto `OutputFiles/` folder

### 🖥️ Tkinter GUI

Native desktop application with dark theme.

```bash
python converter.py --gui
# or just (with no arguments)
python converter.py
```

**Features:**
- Native file/folder browsers
- Live preview of output names
- Per-file pattern detection display
- Multi-threaded conversion with progress
- Color-coded log output

### 💻 Command Line

The CLI is the most powerful — perfect for automation and large batches.

#### Basic Syntax

```bash
python converter.py [INPUT_FILES...] [OPTIONS]
```

#### All CLI Options

```
INPUT FILES
  Pass one or more .cbz files, or a glob pattern (e.g. *.cbz)

CORE OPTIONS
  -f, --format {pdf,epub}          Output format (default: pdf)
  -o, --output PATH                Output path (single file only)
  --output-dir DIR                 Output directory for batch
  -e, --engine {img2pdf,reportlab} PDF engine (default: img2pdf)
  -s, --size {Auto,A4,Letter,A5,Comic}
                                   Page size (default: Auto = detect from images)
  -q, --quality 1-100              JPEG quality (default: 85)

METADATA
  --auto                           Auto-detect manga from filename
  --search QUERY                   Manual search query
  --select N                       Auto-select Nth result (1-based)
  --title TITLE                    Override manga title
  --author NAMES                   Override author(s), comma-separated
  --name-format FORMAT             Custom naming template
  --keep-name                      Don't rename — keep original filenames

PERFORMANCE
  -w, --workers N                  Parallel workers (default: 4)
  --sequential                     Force single-threaded

DEBUG
  --dry-run                        Preview without converting
  --gui                            Launch desktop GUI
  --web                            Launch web dashboard
  --web-port PORT                  Custom web port (default: 5000)
```

---

## 💡 Examples

### Convert a Single File

```bash
python converter.py "Berserk Vol.01.cbz"
# Output: Berserk Vol.01.pdf
```

### Batch with Auto-Metadata

```bash
# Auto-detect manga, present results, you pick
python converter.py "Shigahime v01.cbz" "Shigahime v02.cbz" --auto

# Auto-detect AND auto-pick first result
python converter.py *.cbz --auto --select 1

# Use a glob with EPUB output
python converter.py manga/*.cbz --auto --select 1 -f epub
```

### Custom Naming

```bash
# Use API metadata in filename
python converter.py *.cbz --auto --select 1 \
  --name-format "{manga_name} Vol.{volume} - Ch.{chapter} [{volume_title}] ({date})"

# Result:
#   Shigahime Vol.01 - Ch.1-6 [The Awakening] (2018-06-08).pdf
#   Shigahime Vol.02 - Ch.7-12 [Hunger] (2018-10-05).pdf

# Use the English title instead
python converter.py *.cbz --auto --select 1 \
  --name-format "{manga_name_english} v{volume} ({year})"
```

### Keep Original Filenames

```bash
# Just convert, no renaming
python converter.py *.cbz --keep-name -f pdf
```

### Dry Run (Preview Without Converting)

```bash
python converter.py *.cbz --auto --select 1 --dry-run

# Output:
# ══════════════════════════════════════════════════════════
#   DRY RUN — No files will be converted
# ══════════════════════════════════════════════════════════
#
#   Shigahime v01.cbz
#     → Shigahime Vol.01 - Ch.1-6 [The Awakening] (2018-06-08).pdf
#     vol=01 | ch=1-6 | "The Awakening" | date=2018-06-08
#
#   Shigahime v02.cbz
#     → Shigahime Vol.02 - Ch.7-12 [Hunger] (2018-10-05).pdf
#     vol=02 | ch=7-12 | "Hunger" | date=2018-10-05
```

### Maximum Performance

```bash
# 8 parallel workers, EPUB, max quality
python converter.py large_collection/*.cbz \
  --auto --select 1 \
  -f epub -q 95 -w 8
```

### Specific Manga Search

```bash
# Don't trust the filename, search manually
python converter.py "vol01.cbz" --search "Vinland Saga" --select 1
```

### Custom Page Size

```bash
# Force A4 instead of auto-detect
python converter.py *.cbz -s A4

# Tablet-optimized comic size
python converter.py *.cbz -s Comic
```

---

## 📝 Naming Variables

Use these variables in `--name-format` or the GUI/web format field. Empty variables are gracefully removed.

| Variable | Description | Example |
|----------|-------------|---------|
| `{manga_name}` | Romanized title (matches filename) | `Shigahime` |
| `{manga_name_english}` | Localized English title | `Corpse Fang Princess` |
| `{manga_name_japanese}` | Native Japanese title | `死牙姫` |
| `{manga_name_original}` | Untouched filename title | `Shigahime` |
| `{volume}` | Volume number | `01` |
| `{chapter}` | Chapter number/range from API | `1-6` |
| `{volume_title}` | Volume title from API | `The Awakening` |
| `{date}` | Earliest publish date | `2018-06-08` |
| `{year}` | Publication year | `2018` |
| `{author}` | Author(s) | `Mochizuki Minetaro` |
| `{artist}` | Artist(s) | `Mochizuki Minetaro` |
| `{genre}` | Top 3 genres | `Horror, Mystery, Drama` |
| `{status}` | Publication status | `Completed` |
| `{group}` | Scanlation group from filename | `XYZ-Scans` |
| `{score}` | API score | `8.4` |
| `{original_filename}` | Original CBZ filename | `Shigahime v01` |

### Format Examples

```bash
# Minimal
"{manga_name} v{volume}"
# → Shigahime v01

# With volume info
"{manga_name} Vol.{volume} - Ch.{chapter}"
# → Shigahime Vol.01 - Ch.1-6

# Full metadata
"{manga_name} | Vol.{volume} - Ch.{chapter} [{volume_title}] ({date}) [{group}]"
# → Shigahime | Vol.01 - Ch.1-6 [The Awakening] (2018-06-08)

# English with year
"{manga_name_english} ({year}) v{volume}"
# → Corpse Fang Princess (2018) v01
```

---

## 🌐 Metadata Sources

The converter queries **all four APIs in parallel** and intelligently merges the results. Each source contributes different strengths:

| API | Best For | Required Account |
|-----|----------|------------------|
| 🟦 **MangaDex** | Volume covers, chapter feeds, accurate volume groupings | No |
| 🟧 **MyAnimeList (Jikan)** | Scores, large covers, comprehensive metadata | No |
| 🟪 **AniList** | Modern data, alternative titles, detailed staff info | No |
| 🟩 **Kitsu** | Backup source, English titles | No |

### Merge Priority

When the same manga appears in multiple sources:
1. **MangaDex** is the primary source (best for volume-level data)
2. Fields missing from MangaDex are filled from **AniList**, then **MAL**, then **Kitsu**
3. Volume covers always come from **MangaDex** (others lack per-volume data)
4. Scores prefer **MAL** when available

### Volume-Only Files

Many CBZ files don't contain chapter info (e.g., `Shigahime v01.cbz`). The converter:
1. Tries MangaDex `/feed` for chapter list → if empty
2. Falls back to `/aggregate` endpoint → if empty
3. **Estimates** chapter range using `total_chapters / total_volumes`
4. Always retrieves volume cover art from MangaDex `/cover`

---

## 🧠 Filename Parsing

The converter recognizes **25+ filename patterns**. Examples:

| Pattern | Example | Detected |
|---------|---------|----------|
| `name v01` | `Berserk v01.cbz` | vol=01 |
| `name v01 c001` | `Berserk v01 c001.cbz` | vol=01, ch=001 |
| `name Vol.01 Ch.001` | `Berserk Vol.01 Ch.001.cbz` | vol=01, ch=001 |
| `name Volume 01 Chapter 001` | `Berserk Volume 01 Chapter 001.cbz` | vol=01, ch=001 |
| `name Tome 01` | `Berserk Tome 01.cbz` (French) | vol=01 |
| `name Band 01` | `Berserk Band 01.cbz` (German) | vol=01 |
| `name #01` | `Spawn #01.cbz` | vol=01 |
| `[Group] name v01` | `[XYZ-Scans] Berserk v01.cbz` | group=XYZ-Scans, vol=01 |
| `name - Vol.01` | `Berserk - Vol.01.cbz` | vol=01 |
| `name c001` | `Berserk c001.cbz` | ch=001 |
| `name Chapter 001` | `Berserk Chapter 001.cbz` | ch=001 |
| `name_v01_c001` | `Berserk_v01_c001.cbz` | vol=01, ch=001 |
| `name.v01.c001` | `Berserk.v01.c001.cbz` | vol=01, ch=001 |

**Noise removal**: The parser strips common artifacts:
- `(pg 171 not trans)`, `(Digital)`, `(f)` → removed
- `END`, `FIN` suffix → removed
- `{Group Tag}`, multiple spaces → cleaned

---

## ⚙️ Configuration

### Page Sizes

| Size | Dimensions (pt) | Use Case |
|------|-----------------|----------|
| `Auto` | Detected from images | **Recommended** — preserves original aspect |
| `A4` | 595 × 842 | International standard |
| `Letter` | 612 × 792 | US standard |
| `A5` | 420 × 595 | Compact / phone-friendly |
| `Comic` | 400 × 600 | Tablet-optimized |

### PDF Engines

#### `img2pdf` (default, recommended)
- ✅ **Lossless** for JPEG/PNG sources
- ✅ Smaller file sizes
- ✅ Faster
- ⚠️ Requires `pip install img2pdf`

#### `reportlab`
- ✅ Per-page custom sizing
- ✅ More flexible layouts
- ⚠️ Recompresses images (quality loss)
- ⚠️ Slower

### Worker Threads

| Workers | Best For |
|---------|----------|
| 1 | Limited RAM, sequential debugging |
| 2-4 | **Recommended** — most CPUs |
| 6-8 | High-end CPUs (8+ cores) |
| 16+ | Server hardware |

> 💡 More workers ≠ always faster. Disk I/O becomes the bottleneck after ~4-6 workers on consumer hardware.

---

## 📊 Performance

Benchmarked on a 5-volume manga (avg 190 pages each, ~115 MB per CBZ) on M1 MacBook Pro:

| Mode | Workers | Time | Speedup |
|------|---------|------|---------|
| Sequential | 1 | 47.3s | 1.0x |
| Parallel | 2 | 26.1s | 1.8x |
| Parallel | **4** | **15.8s** | **3.0x** |
| Parallel | 8 | 14.2s | 3.3x |

**Engine comparison** (single 190-page volume):

| Engine | Time | Output Size |
|--------|------|-------------|
| `img2pdf` | 6.8s | 115 MB |
| `reportlab` (q=95) | 11.4s | 132 MB |
| `reportlab` (q=85) | 9.7s | 89 MB |

---

## 🏗️ Architecture

```
cbz_converter/
├── converter.py          # Main entry point + core conversion + CLI + GUI
├── api_client.py         # Multi-API client with parallel fetching
├── metadata.py           # Filename parsing + format engine
├── workers.py            # Thread pool + progress tracking
├── web_dashboard.py      # Self-contained Flask web app
├── requirements.txt
└── README.md
```

### Module Responsibilities

| Module | Purpose |
|--------|---------|
| `converter.py` | Image extraction, PDF/EPUB generation, CLI argument handling, Tkinter GUI |
| `api_client.py` | Parallel API requests, response merging, caching |
| `metadata.py` | 25+ regex patterns, format string engine, metadata resolution |
| `workers.py` | `WorkerPool`, `Job`, `JobStatus` classes, terminal progress rendering |
| `web_dashboard.py` | Flask routes, single-file HTML/CSS/JS dashboard, session-based job tracking |

### Data Flow

```
CBZ files
   ↓
[parse_filename] → ParsedFilename {name, vol, ch, ...}
   ↓
[search_manga] → MangaResult (merged from 4 APIs in parallel)
   ↓
[get_volume_data] → VolumeData (chapters, title, date, cover)
   ↓
[FullMetadata] ← merged from filename + manga + volume
   ↓
[format_output_name] → "Shigahime Vol.01 - Ch.1-6 [...].pdf"
   ↓
[WorkerPool] → parallel conversion with progress
   ↓
[convert_cbz] → extract → process → write PDF/EPUB
```

---

## 🛠️ Troubleshooting

<details>
<summary><b>"name 'Image' is not defined"</b></summary>

You're missing Pillow. Install with:
```bash
pip install Pillow
```
</details>

<details>
<summary><b>"No PDF engine available"</b></summary>

Install at least one PDF library:
```bash
pip install img2pdf      # recommended
# or
pip install reportlab
```
</details>

<details>
<summary><b>Web dashboard CSS not loading</b></summary>

The latest version uses a single-file dashboard with embedded CSS. Make sure you're running the latest `web_dashboard.py`. The HTML/CSS/JS is all served inline via `Response(HTML_PAGE, mimetype="text/html")`.
</details>

<details>
<summary><b>API search returns nothing</b></summary>

- Check internet connection
- Try a simpler search query (just the manga name without volume info)
- Some manga aren't on all APIs — try `--search` with alternative titles
- Rate limits: Jikan limits to ~3 requests/sec; the converter respects this automatically
</details>

<details>
<summary><b>Wrong manga selected (e.g., "Corpse Fang Princess" instead of "Shigahime")</b></summary>

This happens when API returns a localized English title. Use:
- `{manga_name}` for romanized title (default)
- `{manga_name_original}` to use the filename's title verbatim
- `{manga_name_english}` to explicitly want the localization
</details>

<details>
<summary><b>"Volume X not found in API"</b></summary>

Some APIs don't have data for every volume. The converter falls back to:
1. Aggregate endpoint
2. Estimated chapter range from `total_chapters / total_volumes`
3. Just the parsed volume number from filename

You'll still get a valid output — just with less metadata.
</details>

<details>
<summary><b>Tkinter not available on Linux</b></summary>

```bash
sudo apt install python3-tk        # Debian/Ubuntu
sudo dnf install python3-tkinter   # Fedora
sudo pacman -S tk                  # Arch
```
</details>

<details>
<summary><b>Conversion is slow</b></summary>

- Increase workers: `-w 8`
- Use `img2pdf` engine instead of `reportlab` (default)
- Lower quality: `-q 75`
- Make sure source disk isn't bottlenecked (SSD recommended for large batches)
</details>

---

## 🤝 Contributing

Contributions are welcome! Areas where help is appreciated:

- 🌍 More filename patterns from non-English manga sites
- 🎨 Additional API sources (Bookwalker, Mangaupdates, etc.)
- 🖼️ CBR support (RAR archives)
- 📱 Reading device profiles (Kindle, Kobo, reMarkable)
- 🌐 Internationalization (UI translations)
- 🧪 Test coverage

### Development Setup

```bash
git clone https://github.com/yourusername/cbz-converter.git
cd cbz-converter
pip install -r requirements.txt -e .

# Run tests
pytest tests/

# Run linting
ruff check .
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

### 🌟 Star this repo if it helped you organize your manga library!

**Made with ❤ for manga readers everywhere**

[![GitHub stars](https://img.shields.io/badge/⭐-star%20on%20github-yellow.svg?style=for-the-badge)](#)
[![Twitter](https://img.shields.io/badge/share-twitter-1da1f2.svg?style=for-the-badge&logo=twitter&logoColor=white)](#)

[Back to top ⬆](#-cbz-manga-converter)

</div>
