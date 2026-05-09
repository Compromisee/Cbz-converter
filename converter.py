#!/usr/bin/env python3
"""CBZ to EPUB/PDF — multithreaded with multi-API fallback."""

import os
import sys
import zipfile
import argparse
import tempfile
import threading
import re
from pathlib import Path
from io import BytesIO
from collections import Counter

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init()
    C = True
except ImportError:
    C = False
    class Fore: RED = GREEN = YELLOW = CYAN = MAGENTA = WHITE = BLUE = ""
    class Style: RESET_ALL = ""

HAS_TK = False
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    HAS_TK = True
except ImportError: pass

HAS_PIL = False
Image = None
try:
    from PIL import Image as PILImage
    Image = PILImage
    HAS_PIL = True
except ImportError: pass

HAS_REPORTLAB = False
try:
    from reportlab.pdfgen import canvas as pdfcanvas
    from reportlab.lib.utils import ImageReader
    HAS_REPORTLAB = True
except ImportError: pass

HAS_IMG2PDF = False
try:
    import img2pdf
    HAS_IMG2PDF = True
except ImportError: pass

from metadata import (parse_filename, format_output_name, MetadataResolver,
    FullMetadata, AVAILABLE_VARIABLES, DEFAULT_FORMAT)
from api_client import MangaResult
from workers import WorkerPool, Job, JobStatus, TerminalProgress

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}
PAGE_SIZES = {"A4": (595.28, 841.89), "Letter": (612, 792),
              "A5": (419.53, 595.28), "Comic": (400, 600), "Auto": None}

KEEP_ORIGINAL = "{original_filename}"


def natural_sort_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def extract_cbz(path, dest):
    with zipfile.ZipFile(path, "r") as z:
        z.extractall(dest)
    imgs = []
    for root, _, files in os.walk(dest):
        for f in files:
            if Path(f).suffix.lower() in SUPPORTED_EXTS:
                imgs.append(os.path.join(root, f))
    imgs.sort(key=lambda p: natural_sort_key(os.path.basename(p)))
    return imgs


def detect_page_size(images):
    if not HAS_PIL or not images: return (595.28, 841.89)
    sizes = []
    for p in images[:10]:
        try:
            with Image.open(p) as img: sizes.append(img.size)
        except: pass
    if not sizes: return (595.28, 841.89)
    w, h = Counter(sizes).most_common(1)[0][0]
    if w > 1400 or h > 2000:
        r = min(1400/w, 2000/h)
        w, h = int(w*r), int(h*r)
    return (float(w), float(h))


def _jpeg(path, q=95):
    with Image.open(path) as img:
        w, h = img.size
        if img.mode not in ("RGB", "L"): img = img.convert("RGB")
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=q)
        return buf.getvalue(), w, h


def _pdf_img2pdf(images, out, ps=None, progress_cb=None):
    data = []
    for i, p in enumerate(images):
        try:
            with Image.open(p) as img:
                fmt, mode = img.format, img.mode
            if fmt in ("JPEG", "PNG") and mode in ("RGB", "L"):
                with open(p, "rb") as f: data.append(f.read())
            else:
                d, _, _ = _jpeg(p, 95); data.append(d)
        except: continue
        if progress_cb: progress_cb(i+1, len(images))
    if not data: raise ValueError("No valid images")
    layout = None
    if ps:
        try:
            layout = img2pdf.get_layout_fun(
                (img2pdf.mm_to_pt(ps[0]*25.4/72), img2pdf.mm_to_pt(ps[1]*25.4/72)))
        except: pass
    with open(out, "wb") as f:
        f.write(img2pdf.convert(data, layout_fun=layout) if layout else img2pdf.convert(data))


def _pdf_reportlab(images, out, ps=(595.28, 841.89), q=85, auto=False, progress_cb=None):
    c = pdfcanvas.Canvas(out)
    for i, p in enumerate(images):
        try:
            d, iw, ih = _jpeg(p, q)
            if auto:
                mx = 1800
                if iw > mx or ih > mx:
                    r = min(mx/iw, mx/ih); pw, ph = iw*r, ih*r
                else: pw, ph = float(iw), float(ih)
            else: pw, ph = ps
            c.setPageSize((pw, ph))
            buf = BytesIO(d)
            if auto:
                c.drawImage(ImageReader(buf), 0, 0, width=pw, height=ph)
            else:
                r = min(pw/iw, ph/ih); sw, sh = iw*r, ih*r
                c.drawImage(ImageReader(buf), (pw-sw)/2, (ph-sh)/2, width=sw, height=sh)
            c.showPage()
        except: pass
        if progress_cb: progress_cb(i+1, len(images))
    c.save()


def _epub(images, out, title="Comic", author="Unknown", q=85, progress_cb=None):
    import uuid, zipfile as zf
    bid = str(uuid.uuid4())
    total = len(images)
    st = (title or "Comic").replace("&","&amp;").replace("<","&lt;")
    sa = (author or "Unknown").replace("&","&amp;").replace("<","&lt;")
    with zf.ZipFile(out, "w", zf.ZIP_DEFLATED) as epub:
        epub.writestr(zf.ZipInfo("mimetype"), "application/epub+zip", compress_type=zf.ZIP_STORED)
        epub.writestr("META-INF/container.xml",
            '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        items, spine = [], []
        for i, p in enumerate(images):
            pn = f"{i+1:04d}"
            try: d, w, h = _jpeg(p, q)
            except: continue
            epub.writestr(f"OEBPS/images/page_{pn}.jpg", d)
            epub.writestr(f"OEBPS/text/page_{pn}.xhtml",
                f'<?xml version="1.0" encoding="utf-8"?><!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml">'
                f'<head><meta charset="utf-8"/><title>P{i+1}</title>'
                f'<style>body{{margin:0;background:#000;display:flex;justify-content:center;align-items:center;min-height:100vh}}'
                f'img{{max-width:100%;max-height:100vh;object-fit:contain}}</style></head>'
                f'<body><img src="../images/page_{pn}.jpg" width="{w}" height="{h}"/></body></html>')
            items.append(f'<item id="img{pn}" href="images/page_{pn}.jpg" media-type="image/jpeg"/>')
            items.append(f'<item id="page{pn}" href="text/page_{pn}.xhtml" media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="page{pn}"/>')
            if progress_cb: progress_cb(i+1, total)
        epub.writestr("OEBPS/content.opf",
            f'<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid" version="3.0">'
            f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>{st}</dc:title><dc:creator>{sa}</dc:creator>'
            f'<dc:language>en</dc:language><dc:identifier id="bookid">urn:uuid:{bid}</dc:identifier>'
            f'<meta property="rendition:layout">pre-paginated</meta></metadata>'
            f'<manifest>{"".join(items)}<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/></manifest>'
            f'<spine toc="ncx">{"".join(spine)}</spine></package>')
        navs = "".join(f'<navPoint id="n{i+1}" playOrder="{i+1}"><navLabel><text>P{i+1}</text></navLabel>'
            f'<content src="text/page_{i+1:04d}.xhtml"/></navPoint>' for i in range(total))
        epub.writestr("OEBPS/toc.ncx",
            f'<?xml version="1.0"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
            f'<head><meta name="dtb:uid" content="urn:uuid:{bid}"/></head>'
            f'<docTitle><text>{st}</text></docTitle><navMap>{navs}</navMap></ncx>')


def convert_cbz(input_path, output_path, output_format="pdf",
                pdf_engine="img2pdf", page_size="A4", quality=85,
                title=None, author="Unknown", progress_cb=None, log_cb=None):
    log = log_cb or (lambda m: None)
    if not HAS_PIL: raise RuntimeError("Pillow required")
    if not os.path.isfile(input_path): raise FileNotFoundError(input_path)
    if title is None: title = Path(input_path).stem

    with tempfile.TemporaryDirectory() as tmp:
        images = extract_cbz(input_path, tmp)
        if not images: raise ValueError("No images in CBZ")
        log(f"{len(images)} pages")

        auto = (page_size == "Auto")
        ps = detect_page_size(images) if auto else PAGE_SIZES.get(page_size, PAGE_SIZES["A4"])

        fmt = output_format.lower()
        if fmt == "pdf":
            if pdf_engine == "img2pdf" and HAS_IMG2PDF:
                _pdf_img2pdf(images, output_path, None if auto else ps, progress_cb)
            elif HAS_REPORTLAB:
                _pdf_reportlab(images, output_path, ps, quality, auto, progress_cb)
            else: raise RuntimeError("No PDF engine")
        elif fmt == "epub":
            _epub(images, output_path, title, author, quality, progress_cb)
    return output_path


# ─────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────

def run_cli():
    parser = argparse.ArgumentParser(
        prog="cbz-converter",
        description="Convert CBZ → EPUB/PDF — multithreaded, multi-API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{Fore.CYAN}Examples:{Style.RESET_ALL}
  python converter.py *.cbz --auto --select 1
  python converter.py *.cbz --keep-name        # don't rename
  python converter.py *.cbz --auto --dry-run
  python converter.py *.cbz --auto -w 8 -f epub
  python converter.py --web
  python converter.py --gui
""",
    )
    parser.add_argument("input", nargs="*")
    parser.add_argument("-f", "--format", choices=["pdf", "epub"], default="pdf")
    parser.add_argument("-o", "--output")
    parser.add_argument("--output-dir")
    parser.add_argument("-e", "--engine", choices=["img2pdf", "reportlab"], default="img2pdf")
    parser.add_argument("-s", "--size", choices=list(PAGE_SIZES.keys()), default="Auto")
    parser.add_argument("-q", "--quality", type=int, default=85)
    parser.add_argument("--title", default="")
    parser.add_argument("--author", default="")
    parser.add_argument("--auto", action="store_true")
    parser.add_argument("--search")
    parser.add_argument("--name-format", default=DEFAULT_FORMAT)
    parser.add_argument("--keep-name", action="store_true",
                        help="Keep original filename (don't rename)")
    parser.add_argument("--select", type=int)
    parser.add_argument("-w", "--workers", type=int, default=4)
    parser.add_argument("--sequential", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--web", action="store_true")
    parser.add_argument("--web-port", type=int, default=5000)

    args = parser.parse_args()

    if args.gui: run_gui(); return
    if args.web:
        from web_dashboard import run_web_dashboard
        run_web_dashboard(port=args.web_port); return
    if not args.input: parser.error("No input files")

    # If keeping name, override format
    if args.keep_name:
        args.name_format = KEEP_ORIGINAL

    resolver = MetadataResolver()
    selected = None

    if (args.auto or args.search) and not args.keep_name:
        query = args.search or parse_filename(args.input[0]).manga_name
        if query:
            print(f"\n{Fore.CYAN}Searching: '{query}'{Style.RESET_ALL}")
            try:
                results = resolver.api.search_manga(query)
            except Exception as e:
                print(f"{Fore.RED}Search error: {e}{Style.RESET_ALL}")
                results = []

            if results:
                if args.select and 1 <= args.select <= len(results):
                    selected = results[args.select - 1]
                    print(f"{Fore.GREEN}Selected: {selected.title} [{selected.source}]{Style.RESET_ALL}")
                else:
                    print(f"\n{Fore.YELLOW}Results:{Style.RESET_ALL}")
                    for i, r in enumerate(results, 1):
                        a = ", ".join(r.authors[:2]) or "?"
                        print(f"  {Fore.CYAN}{i}.{Style.RESET_ALL} [{r.source}] {r.title}"
                              f" ({r.year or '?'}) — {a} ⭐{r.score or '?'}")
                    try:
                        ch = input(f"\n{Fore.YELLOW}Select: {Style.RESET_ALL}").strip()
                        if ch.isdigit() and 1 <= int(ch) <= len(results):
                            selected = results[int(ch) - 1]
                    except (KeyboardInterrupt, EOFError): pass

    print(f"\n{Fore.CYAN}Resolving metadata for {len(args.input)} file(s)...{Style.RESET_ALL}")

    jobs = []
    for i, cbz in enumerate(args.input):
        if not os.path.isfile(cbz):
            print(f"{Fore.RED}Not found: {cbz}{Style.RESET_ALL}"); continue

        if args.keep_name:
            # Just use original filename
            meta = FullMetadata(parsed=parse_filename(cbz))
            out_name = Path(cbz).stem
        else:
            meta = resolver.resolve_file(
                filename=cbz, selected_manga=selected,
                title_override=args.title, author_override=args.author,
                log_cb=lambda m: print(f"  {m}"),
            )
            out_name = format_output_name(meta, args.name_format)

        if args.output and len(args.input) == 1:
            out_path = args.output
        else:
            out_dir = args.output_dir or os.path.dirname(os.path.abspath(cbz))
            out_path = os.path.join(out_dir, f"{out_name}.{args.format}")

        jobs.append((Job(id=i, filename=os.path.basename(cbz),
            input_path=cbz, output_path=out_path,
            dry_run_output=os.path.basename(out_path)), meta))

    if not jobs: return

    if args.dry_run:
        print(f"\n{Fore.YELLOW}{'='*70}\n  DRY RUN\n{'='*70}{Style.RESET_ALL}\n")
        for j, meta in jobs:
            print(f"  {Fore.CYAN}{j.filename}{Style.RESET_ALL}")
            print(f"    → {Fore.GREEN}{j.dry_run_output}{Style.RESET_ALL}")
            details = []
            if meta.parsed.volume: details.append(f"vol={meta.parsed.volume}")
            if meta.chapter_range or meta.parsed.chapter:
                details.append(f"ch={meta.chapter_range or meta.parsed.chapter}")
            if meta.volume_title: details.append(f'"{meta.volume_title}"')
            if meta.release_date: details.append(f"date={meta.release_date}")
            if details: print(f"    {' | '.join(details)}")
        print(f"\n  {len(jobs)} files would be converted\n")
        return

    print(f"\n{Fore.CYAN}Converting with {args.workers} workers{Style.RESET_ALL}\n")
    pool = WorkerPool(max_workers=args.workers)
    for _ in range(len(jobs) + 2): print()
    progress = TerminalProgress(pool)

    def task_fn(job, progress_cb, log_cb, cancel):
        if cancel.is_set(): return
        meta = next((m for j, m in jobs if j.id == job.id), None)
        convert_cbz(job.input_path, job.output_path, args.format, args.engine,
            args.size, args.quality, meta.display_title if meta else None,
            meta.author_str if meta else "Unknown", progress_cb, log_cb)

    job_list = [j for j, _ in jobs]
    progress.start()
    try:
        pool.run_jobs(job_list, task_fn, sequential=args.sequential)
    except KeyboardInterrupt:
        pool.cancel()
    progress.stop()

    done = sum(1 for j in job_list if j.status == JobStatus.DONE)
    failed = sum(1 for j in job_list if j.status == JobStatus.FAILED)
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"  {Fore.GREEN}✓ {done} converted{Style.RESET_ALL}")
    if failed: print(f"  {Fore.RED}✗ {failed} failed{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")


# ─────────────────────────────────────────────────────────────────────────
#  GUI
# ─────────────────────────────────────────────────────────────────────────

def run_gui():
    if not HAS_TK: print("tkinter not available"); sys.exit(1)

    class GUI:
        def __init__(self, root):
            self.root = root
            self.root.title("CBZ Manga Converter")
            self.root.geometry("820x980")
            self.root.configure(bg="#0a0a0f")
            self._files = []
            self._running = False
            self._resolver = MetadataResolver()
            self._search_results = []
            self._selected_manga = None
            self._pool = None
            self._styles()
            self._build()

        def _styles(self):
            s = ttk.Style(); s.theme_use("clam")
            BG, SURF, FG = "#0a0a0f", "#15151d", "#e0e0ec"
            ACC_R, ACC_B = "#ef4444", "#3b82f6"
            BTN, BTNA = "#1e1e2a", "#2d2d3d"
            s.configure(".", background=BG, foreground=FG, font=("Segoe UI", 10))
            s.configure("TFrame", background=BG)
            s.configure("TLabel", background=BG, foreground=FG)
            s.configure("TLabelframe", background=BG, foreground=ACC_B, bordercolor="#2a2a3a")
            s.configure("TLabelframe.Label", background=BG, foreground=ACC_B, font=("Segoe UI", 10, "bold"))
            s.configure("TButton", background=BTN, foreground=FG, borderwidth=0, padding=6)
            s.map("TButton", background=[("active", BTNA)])
            s.configure("Red.TButton", background=ACC_R, foreground="#fff", font=("Segoe UI", 10, "bold"))
            s.map("Red.TButton", background=[("active", "#dc2626")])
            s.configure("Blue.TButton", background=ACC_B, foreground="#fff", font=("Segoe UI", 10, "bold"))
            s.map("Blue.TButton", background=[("active", "#2563eb")])
            s.configure("TCombobox", fieldbackground=BTN, background=BTN, foreground=FG)
            s.configure("TEntry", fieldbackground=BTN, foreground=FG, insertcolor=FG)
            s.configure("TProgressbar", troughcolor=BTN, background=ACC_B)
            s.configure("TRadiobutton", background=BG, foreground=FG)
            s.configure("TCheckbutton", background=BG, foreground=FG)

        def _build(self):
            canvas = tk.Canvas(self.root, bg="#0a0a0f", highlightthickness=0)
            vsb = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
            mf = ttk.Frame(canvas)
            mf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0,0), window=mf, anchor="nw")
            canvas.configure(yscrollcommand=vsb.set)
            canvas.pack(side="left", fill="both", expand=True)
            vsb.pack(side="right", fill="y")
            canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

            p = {"padx": 12, "pady": 4}
            tk.Label(mf, text="CBZ Manga Converter", font=("Segoe UI", 18, "bold"),
                bg="#0a0a0f", fg="#3b82f6").pack(pady=(10,4), padx=12)
            tk.Label(mf, text="Multithreaded · Multi-API · Per-file metadata",
                bg="#15151d", fg="#ef4444", font=("Segoe UI", 9), padx=8, pady=3).pack(fill="x", padx=12, pady=(0,4))

            # Files
            ff = ttk.LabelFrame(mf, text="Files"); ff.pack(fill="x", **p)
            lf = ttk.Frame(ff); lf.pack(fill="both", expand=True, padx=6, pady=6)
            sb = ttk.Scrollbar(lf); sb.pack(side="right", fill="y")
            self.flb = tk.Listbox(lf, bg="#15151d", fg="#e0e0ec", selectbackground="#3b82f6",
                font=("Consolas", 9), height=5, borderwidth=0, yscrollcommand=sb.set)
            self.flb.pack(fill="both", expand=True); sb.config(command=self.flb.yview)
            self.flb.bind("<<ListboxSelect>>", self._on_fsel)
            br = ttk.Frame(ff); br.pack(fill="x", padx=6, pady=(0,6))
            ttk.Button(br, text="+Files", command=self._add_files).pack(side="left", padx=2)
            ttk.Button(br, text="+Folder", command=self._add_folder).pack(side="left", padx=2)
            ttk.Button(br, text="Remove", command=self._rm).pack(side="left", padx=2)
            ttk.Button(br, text="Clear", command=self._clr).pack(side="left", padx=2)
            self.fc = ttk.Label(br, text="0 files"); self.fc.pack(side="right")
            self.fp = ttk.Label(ff, text="—", foreground="#ef4444", font=("Consolas", 9))
            self.fp.pack(padx=8, pady=(0,6), anchor="w")

            # Keep name option
            kf = ttk.Frame(mf); kf.pack(fill="x", padx=12, pady=4)
            self.keep_name = tk.BooleanVar(value=False)
            ttk.Checkbutton(kf, text="Keep original filename (don't rename)",
                variable=self.keep_name, command=self._on_keep_change).pack(side="left")

            # Search
            sf = ttk.LabelFrame(mf, text="Manga Search"); sf.pack(fill="x", **p)
            sr = ttk.Frame(sf); sr.pack(fill="x", padx=8, pady=6)
            self.sq = tk.StringVar()
            ttk.Entry(sr, textvariable=self.sq, width=28).pack(side="left", padx=(0,6))
            ttk.Button(sr, text="Search", style="Blue.TButton", command=self._search).pack(side="left", padx=2)
            ttk.Button(sr, text="Auto", style="Red.TButton", command=self._auto).pack(side="left", padx=2)
            self.ss = ttk.Label(sf, text=""); self.ss.pack(anchor="w", padx=8)
            rlf = ttk.Frame(sf); rlf.pack(fill="x", padx=8, pady=(0,6))
            self.rlb = tk.Listbox(rlf, bg="#15151d", fg="#3b82f6", selectbackground="#1e1e2a",
                font=("Consolas", 9), height=4, borderwidth=0)
            self.rlb.pack(fill="x"); self.rlb.bind("<<ListboxSelect>>", self._on_rsel)
            self.mi = ttk.Label(sf, text="", foreground="#ef4444", font=("Consolas", 9))
            self.mi.pack(padx=8, pady=(0,6), anchor="w")

            # Naming
            nf = ttk.LabelFrame(mf, text="Naming"); nf.pack(fill="x", **p)
            self.nf_var = tk.StringVar(value=DEFAULT_FORMAT)
            self.nf_entry = ttk.Entry(nf, textvariable=self.nf_var, width=70, font=("Consolas", 9))
            self.nf_entry.pack(fill="x", padx=8, pady=(6,4))
            vf = ttk.Frame(nf); vf.pack(fill="x", padx=8)
            for v in AVAILABLE_VARIABLES:
                tk.Button(vf, text=v, bg="#15151d", fg="#3b82f6", font=("Consolas", 7),
                    borderwidth=0, padx=2, command=lambda var=v: self.nf_var.set(self.nf_var.get()+var)
                ).pack(side="left", padx=1)
            pf2 = ttk.Frame(nf); pf2.pack(fill="x", padx=8, pady=(4,6))
            ttk.Label(pf2, text="Preview:").pack(side="left")
            self.pv = ttk.Label(pf2, text="—", foreground="#ef4444", font=("Consolas", 9))
            self.pv.pack(side="left", padx=6)
            self.nf_var.trace_add("write", lambda *_: self._preview())

            # Overrides
            mof = ttk.LabelFrame(mf, text="Overrides"); mof.pack(fill="x", **p)
            mg = ttk.Frame(mof); mg.pack(fill="x", padx=8, pady=6)
            self.mt = tk.StringVar(); self.ma = tk.StringVar()
            self.mvt = tk.StringVar(); self.md = tk.StringVar()
            for i, (l, v) in enumerate([("Title:", self.mt), ("Author:", self.ma),
                ("Vol.Title:", self.mvt), ("Date:", self.md)]):
                r, c = i//2, (i%2)*2
                ttk.Label(mg, text=l).grid(row=r, column=c, sticky="w")
                ttk.Entry(mg, textvariable=v, width=22).grid(row=r, column=c+1, sticky="ew", padx=(4,12), pady=2)
                v.trace_add("write", lambda *_: self._preview())
            mg.columnconfigure(1, weight=1); mg.columnconfigure(3, weight=1)

            # Settings
            of = ttk.LabelFrame(mf, text="Settings"); of.pack(fill="x", **p)
            og = ttk.Frame(of); og.pack(fill="x", padx=8, pady=6)
            ttk.Label(og, text="Output:").grid(row=0, column=0, sticky="w")
            self.od = tk.StringVar()
            ttk.Entry(og, textvariable=self.od, width=30).grid(row=0, column=1, padx=6, sticky="ew")
            ttk.Button(og, text="Browse", command=lambda: self.od.set(filedialog.askdirectory() or self.od.get())).grid(row=0, column=2)
            ttk.Label(og, text="Format:").grid(row=1, column=0, sticky="w", pady=(6,0))
            self.ofmt = tk.StringVar(value="pdf")
            ff3 = ttk.Frame(og); ff3.grid(row=1, column=1, sticky="w", padx=6, pady=(6,0))
            ttk.Radiobutton(ff3, text="PDF", variable=self.ofmt, value="pdf").pack(side="left", padx=(0,8))
            ttk.Radiobutton(ff3, text="EPUB", variable=self.ofmt, value="epub").pack(side="left")
            ttk.Label(og, text="Engine:").grid(row=2, column=0, sticky="w", pady=(4,0))
            self.eng = tk.StringVar(value="img2pdf" if HAS_IMG2PDF else "reportlab")
            ttk.Combobox(og, textvariable=self.eng, values=["img2pdf","reportlab"], state="readonly", width=12).grid(row=2, column=1, sticky="w", padx=6, pady=(4,0))
            ttk.Label(og, text="Size:").grid(row=3, column=0, sticky="w", pady=(4,0))
            self.psz = tk.StringVar(value="Auto")
            ttk.Combobox(og, textvariable=self.psz, values=list(PAGE_SIZES.keys()), state="readonly", width=12).grid(row=3, column=1, sticky="w", padx=6, pady=(4,0))
            ttk.Label(og, text="Workers:").grid(row=4, column=0, sticky="w", pady=(4,0))
            self.wk = tk.IntVar(value=4)
            tk.Spinbox(og, from_=1, to=16, textvariable=self.wk, width=4, bg="#1e1e2a", fg="#e0e0ec").grid(row=4, column=1, sticky="w", padx=6, pady=(4,0))
            ttk.Label(og, text="Quality:").grid(row=5, column=0, sticky="w", pady=(4,0))
            self.ql = tk.IntVar(value=85)
            qf = ttk.Frame(og); qf.grid(row=5, column=1, sticky="w", padx=6, pady=(4,0))
            self.qll = ttk.Label(qf, text="85", width=3); self.qll.pack(side="right")
            ttk.Scale(qf, from_=1, to=100, variable=self.ql, length=160,
                command=lambda v: self.qll.config(text=str(int(float(v))))).pack(side="left")
            og.columnconfigure(1, weight=1)

            # Progress
            prf = ttk.LabelFrame(mf, text="Progress"); prf.pack(fill="x", **p)
            self.prg = tk.DoubleVar()
            ttk.Progressbar(prf, variable=self.prg, maximum=100).pack(fill="x", padx=8, pady=(8,4))
            self.st = tk.StringVar(value="Ready")
            ttk.Label(prf, textvariable=self.st, font=("Segoe UI", 9)).pack(padx=8, pady=(0,6))

            # Log
            lgf = ttk.LabelFrame(mf, text="Log"); lgf.pack(fill="both", expand=True, **p)
            self.lg = tk.Text(lgf, height=7, bg="#0a0a0f", fg="#3b82f6",
                font=("Consolas", 9), state="disabled", borderwidth=0)
            self.lg.pack(fill="both", expand=True, padx=6, pady=6)
            self.lg.tag_configure("err", foreground="#ef4444")
            self.lg.tag_configure("ok", foreground="#10b981")
            self.lg.tag_configure("info", foreground="#3b82f6")
            self.lg.tag_configure("warn", foreground="#f59e0b")

            # Actions
            af = ttk.Frame(mf); af.pack(fill="x", padx=12, pady=(4,14))
            self.cb = ttk.Button(af, text="Convert All", style="Red.TButton", command=self._start)
            self.cb.pack(side="left", ipadx=16, ipady=4)
            self.dry = ttk.Button(af, text="Dry Run", style="Blue.TButton", command=self._dry_run)
            self.dry.pack(side="left", padx=8, ipadx=8, ipady=4)
            ttk.Button(af, text="Cancel", command=self._cancel).pack(side="left", padx=4)
            ttk.Button(af, text="Web UI", command=self._web).pack(side="right")

        def _on_keep_change(self):
            if self.keep_name.get():
                self.nf_var.set(KEEP_ORIGINAL)
                self.nf_entry.config(state="disabled")
            else:
                self.nf_var.set(DEFAULT_FORMAT)
                self.nf_entry.config(state="normal")
            self._preview()

        def _log(self, m, tag=""):
            self.lg.config(state="normal")
            self.lg.insert("end", m + "\n", tag)
            self.lg.see("end"); self.lg.config(state="disabled")

        def _add_files(self):
            for p in filedialog.askopenfilenames(filetypes=[("CBZ","*.cbz")]):
                if p not in self._files: self._files.append(p)
            self._rfr()

        def _add_folder(self):
            d = filedialog.askdirectory()
            if d:
                for f in sorted(Path(d).rglob("*.cbz"), key=lambda x: natural_sort_key(x.name)):
                    if str(f) not in self._files: self._files.append(str(f))
            self._rfr()

        def _rm(self):
            for i in reversed(self.flb.curselection()): self._files.pop(i)
            self._rfr()
        def _clr(self): self._files.clear(); self._rfr()
        def _rfr(self):
            self.flb.delete(0, "end")
            for f in self._files: self.flb.insert("end", os.path.basename(f))
            self.fc.config(text=f"{len(self._files)} files")

        def _on_fsel(self, _):
            sel = self.flb.curselection()
            if not sel: return
            p = parse_filename(self._files[sel[0]])
            self.sq.set(p.manga_name)
            self.fp.config(text=f"vol={p.volume or '?'} ch={p.chapter or '?'} [{p.source_pattern}]")
            self._preview()

        def _search(self):
            q = self.sq.get().strip()
            if not q: return
            self.ss.config(text="Searching..."); self.root.update()
            def do():
                try:
                    r = self._resolver.api.search_manga(q)
                    self.root.after(0, self._show_res, r)
                except Exception as e:
                    self.root.after(0, self.ss.config, {"text": f"Error: {e}"})
            threading.Thread(target=do, daemon=True).start()

        def _auto(self):
            sel = self.flb.curselection()
            idx = sel[0] if sel else (0 if self._files else -1)
            if idx < 0: return
            self.ss.config(text="Detecting..."); self.root.update()
            def do():
                try:
                    parsed, results = self._resolver.auto_detect(self._files[idx],
                        log_cb=lambda m: self.root.after(0, self._log, m, "info"))
                    self.root.after(0, self.sq.set, parsed.manga_name)
                    if results: self.root.after(0, self._show_res, results)
                    else: self.root.after(0, self.ss.config, {"text": "No results"})
                except Exception as e:
                    self.root.after(0, self.ss.config, {"text": f"Error: {e}"})
            threading.Thread(target=do, daemon=True).start()

        def _show_res(self, results):
            self._search_results = results; self.rlb.delete(0, "end")
            for r in results:
                self.rlb.insert("end", f"[{r.source}] {r.title} ({r.year or '?'}) — {', '.join(r.authors[:2]) or '?'}")
            self.ss.config(text=f"{len(results)} results")

        def _on_rsel(self, _):
            sel = self.rlb.curselection()
            if not sel: return
            m = self._search_results[sel[0]]
            self._selected_manga = m
            self.mt.set(m.title_english or m.title)
            self.ma.set(", ".join(m.authors[:2]) or "")
            self.mi.config(text=f"✔ [{m.source}] {m.title} | {', '.join(m.authors[:2])}")
            self._preview()

        def _preview(self):
            if self.keep_name.get():
                if self._files:
                    sel = self.flb.curselection()
                    idx = sel[0] if sel else 0
                    self.pv.config(text=Path(self._files[idx]).stem)
                else:
                    self.pv.config(text="—")
                return
            sel = self.flb.curselection()
            idx = sel[0] if sel else (0 if self._files else -1)
            if idx < 0: self.pv.config(text="—"); return
            p = parse_filename(self._files[idx])
            meta = FullMetadata(parsed=p)
            meta.manga_title_english = self.mt.get()
            meta.manga_title = self.mt.get()
            meta.parsed.manga_name = self.mt.get() or p.manga_name
            meta.authors = [a.strip() for a in self.ma.get().split(",") if a.strip()]
            meta.volume_title = self.mvt.get()
            meta.release_date = self.md.get()
            self.pv.config(text=format_output_name(meta, self.nf_var.get()) or "—")

        def _build_jobs(self):
            out_dir = self.od.get().strip() or os.getcwd()
            os.makedirs(out_dir, exist_ok=True)
            fmt = self.ofmt.get()
            jobs = []
            for i, cbz in enumerate(self._files):
                if self.keep_name.get():
                    meta = FullMetadata(parsed=parse_filename(cbz))
                    out_name = Path(cbz).stem
                else:
                    meta = self._resolver.resolve_file(
                        cbz, self._selected_manga, self.mt.get(), self.ma.get(),
                        self.mvt.get(), self.md.get(),
                        log_cb=lambda m: self.root.after(0, self._log, f"  {m}", "info"))
                    out_name = format_output_name(meta, self.nf_var.get())
                out_path = os.path.join(out_dir, f"{out_name}.{fmt}")
                jobs.append((Job(id=i, filename=os.path.basename(cbz),
                    input_path=cbz, output_path=out_path,
                    dry_run_output=os.path.basename(out_path)), meta))
            return jobs

        def _dry_run(self):
            if not self._files: return
            self._log("\n=== DRY RUN ===", "warn")
            def do():
                jobs = self._build_jobs()
                for j, meta in jobs:
                    self.root.after(0, self._log, f"  {j.filename} → {j.dry_run_output}", "info")
                self.root.after(0, self._log, f"{len(jobs)} files would be converted\n", "warn")
            threading.Thread(target=do, daemon=True).start()

        def _cancel(self):
            if self._pool: self._pool.cancel(); self._log("Cancelling...", "err")

        def _web(self):
            def s():
                from web_dashboard import run_web_dashboard
                run_web_dashboard(port=5000)
            threading.Thread(target=s, daemon=True).start()
            self.root.after(1500, lambda: __import__("webbrowser").open("http://localhost:5000"))

        def _start(self):
            if not self._files or self._running: return
            self._running = True
            self.cb.config(state="disabled")
            self.dry.config(state="disabled")
            threading.Thread(target=self._convert, daemon=True).start()

        def _convert(self):
            fmt = self.ofmt.get(); engine = self.eng.get()
            size = self.psz.get(); quality = self.ql.get(); workers = self.wk.get()

            self.root.after(0, self._log, f"\nResolving metadata for {len(self._files)} files...", "info")
            jobs = self._build_jobs()
            if not jobs:
                self.root.after(0, self._log, "No valid jobs", "err"); self._finish(); return

            self.root.after(0, self._log, f"Starting: {len(jobs)} files, {workers} workers\n", "info")
            self._pool = WorkerPool(max_workers=workers)

            def on_update(job):
                total = len(jobs)
                done = sum(1 for j, _ in jobs if j.status in (JobStatus.DONE, JobStatus.FAILED))
                self.root.after(0, self.prg.set, done / total * 100)
                if job.status == JobStatus.RUNNING:
                    pg = f"{job.pages_done}/{job.pages_total}" if job.pages_total else "..."
                    self.root.after(0, self.st.set, f"W{job.worker_id}: {job.filename} ({pg})")
                elif job.status == JobStatus.DONE:
                    self.root.after(0, self._log, f"  ✓ {job.filename} → {os.path.basename(job.output_path)} ({job.elapsed:.1f}s)", "ok")
                elif job.status == JobStatus.FAILED:
                    self.root.after(0, self._log, f"  ✗ {job.filename}: {job.error}", "err")

            self._pool.on_job_update = on_update

            def task_fn(job, progress_cb, log_cb, cancel):
                if cancel.is_set(): return
                meta = next((m for j, m in jobs if j.id == job.id), None)
                convert_cbz(job.input_path, job.output_path, fmt, engine, size, quality,
                    meta.display_title if meta else None,
                    meta.author_str if meta else "Unknown", progress_cb, log_cb)

            job_list = [j for j, _ in jobs]
            self._pool.run_jobs(job_list, task_fn, sequential=(workers <= 1))

            done = sum(1 for j in job_list if j.status == JobStatus.DONE)
            failed = sum(1 for j in job_list if j.status == JobStatus.FAILED)
            msg = f"Done! {done} ok, {failed} failed"
            self.root.after(0, self.prg.set, 100)
            self.root.after(0, self.st.set, msg)
            self.root.after(0, self._log, f"\n{msg}\n", "ok" if not failed else "warn")
            self.root.after(0, messagebox.showinfo, "Done", msg)
            self._finish()

        def _finish(self):
            self._running = False; self._pool = None
            self.root.after(0, self.cb.config, {"state": "normal"})
            self.root.after(0, self.dry.config, {"state": "normal"})

    root = tk.Tk(); GUI(root); root.mainloop()


def main():
    if len(sys.argv) == 1 and HAS_TK: run_gui()
    elif len(sys.argv) == 1: print("No args. Use --help, --gui, or --web")
    elif "--gui" in sys.argv: run_gui()
    elif "--web" in sys.argv:
        from web_dashboard import run_web_dashboard
        port = 5000
        for i, a in enumerate(sys.argv):
            if a == "--web-port" and i+1 < len(sys.argv): port = int(sys.argv[i+1])
        run_web_dashboard(port=port)
    else: run_cli()


if __name__ == "__main__":
    main()