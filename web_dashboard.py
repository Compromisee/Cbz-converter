"""Self-contained web dashboard — single HTML file, no separate static files."""

import os
import sys
import json
import threading
import tempfile
import uuid
from pathlib import Path

try:
    from flask import Flask, request, jsonify, send_file, Response
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

from metadata import (
    parse_filename, format_output_name, MetadataResolver,
    FullMetadata, AVAILABLE_VARIABLES, DEFAULT_FORMAT,
)
from api_client import MangaResult


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CBZ Converter</title>
<link href="https://fonts.googleapis.com/icon?family=Material+Icons+Round" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

:root {
  --bg: #0a0a0f;
  --dark: #15151d;
  --dark-2: #1c1c26;
  --light: #f4f5f8;
  --red: #ef4444;
  --red-d: #dc2626;
  --blue: #3b82f6;
  --blue-d: #2563eb;
  --green: #10b981;
  --yellow: #f59e0b;
  --text: #e5e7eb;
  --text-2: #9ca3af;
  --text-d: #1f2937;
  --text-d-2: #6b7280;
  --border: #27272f;
  --border-l: #e5e7eb;
  --radius: 18px;
  --radius-sm: 10px;
}

body {
  font-family: 'Inter', -apple-system, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

.dashboard {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 8px 12px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-icon {
  font-size: 32px;
  color: var(--blue);
}

.brand-name {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.3px;
}

.grid-row {
  display: grid;
  gap: 16px;
  grid-template-columns: 1.4fr 1fr;
}

.stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card {
  border-radius: var(--radius);
  padding: 24px;
  position: relative;
  overflow: hidden;
}

.card-dark { background: var(--dark); color: var(--text); }
.card-light { background: var(--light); color: var(--text-d); }
.card-red { background: var(--red); color: #fff; }
.card-blue { background: var(--blue); color: #fff; }

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 18px;
  gap: 12px;
}

.card-head-light {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
}

.card-title {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.2px;
  color: var(--text);
}

.card-title-dark {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-d);
  letter-spacing: -0.2px;
}

.card-title-light {
  font-size: 15px;
  font-weight: 700;
  color: #fff;
}

.card-sub {
  font-size: 12px;
  color: var(--text-2);
  margin-top: 2px;
  font-weight: 500;
}

.card-sub-dark {
  font-size: 12px;
  color: var(--text-d-2);
  margin-top: 2px;
  font-weight: 500;
}

.card-sub-light {
  font-size: 11px;
  color: rgba(255,255,255,0.85);
  font-weight: 500;
}

.card-titles { flex: 1; }

.icon-circle {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(255,255,255,0.18);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.icon-circle .material-icons-round {
  font-size: 20px;
  color: #fff;
}

.card-actions { display: flex; gap: 6px; }

.icon-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--dark-2);
  border: none;
  color: var(--text);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.icon-btn:hover {
  background: var(--blue);
  color: #fff;
  transform: scale(1.05);
}

.icon-btn-danger:hover { background: var(--red); }
.icon-btn .material-icons-round { font-size: 18px; }

.big-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 28px;
  border: none;
  border-radius: 14px;
  font-family: inherit;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s;
  letter-spacing: -0.2px;
}

.big-btn:hover { transform: translateY(-1px); filter: brightness(1.1); }
.big-btn:active { transform: scale(0.98); }
.big-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.big-btn-red { background: #fff; color: var(--red); }

.big-btn-blue {
  background: rgba(255,255,255,0.2);
  color: #fff;
  border: 2px solid rgba(255,255,255,0.3);
}

.big-btn .material-icons-round { font-size: 20px; }

.pill-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border: 1px solid rgba(255,255,255,0.3);
  background: rgba(255,255,255,0.12);
  color: #fff;
  border-radius: 100px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  transition: all 0.12s;
  font-family: inherit;
}

.pill-btn:hover { background: rgba(255,255,255,0.22); }
.pill-btn .material-icons-round { font-size: 14px; }

.search-btn {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: #fff;
  color: var(--red);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.12s;
  flex-shrink: 0;
}

.search-btn:hover { transform: scale(1.05); }
.search-btn .material-icons-round { font-size: 18px; }

.dark-input,
.format-input {
  width: 100%;
  padding: 9px 12px;
  background: var(--dark-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text);
  font-family: inherit;
  font-size: 13px;
  outline: none;
  transition: all 0.15s;
}

.dark-input:focus,
.format-input:focus {
  border-color: var(--blue);
  box-shadow: 0 0 0 3px rgba(59,130,246,0.15);
}

.format-input {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
}

/* === Dropdown arrow fix === */
select.dark-input,
.setting select.dark-input {
  -webkit-appearance: none !important;
  -moz-appearance: none !important;
  appearance: none !important;
}
select.dark-input::-ms-expand {
  display: none !important;
}
select.dark-input option {
  background: var(--dark-2);
  color: var(--text);
}
.setting select.dark-input option {
  background: var(--blue-d);
  color: #fff;
}

input[type="range"] {
  width: 100%;
  height: 6px;
  border-radius: 3px;
  background: var(--dark-2);
  outline: none;
  -webkit-appearance: none;
}

input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--blue);
  cursor: pointer;
}

input[type="range"]::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--blue);
  cursor: pointer;
  border: none;
}

label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-2);
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.file-list {
  background: var(--dark-2);
  border-radius: 12px;
  max-height: 280px;
  overflow-y: auto;
  margin-bottom: 14px;
  border: 1px solid var(--border);
}

.file-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  transition: background 0.1s;
}

.file-item:last-child { border: none; }
.file-item:hover { background: rgba(255,255,255,0.03); }

.file-item.selected {
  background: rgba(59,130,246,0.1);
  border-left: 3px solid var(--blue);
}

.file-item .file-icon { color: var(--text-2); font-size: 16px; }

.file-item .file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-item .vol-badge {
  background: var(--red);
  color: #fff;
  padding: 2px 8px;
  border-radius: 100px;
  font-size: 10px;
  font-weight: 700;
}

.file-item .ch-badge {
  background: var(--blue);
  color: #fff;
  padding: 2px 8px;
  border-radius: 100px;
  font-size: 10px;
  font-weight: 700;
}

.file-item .file-size {
  color: var(--text-2);
  font-size: 10px;
}

.file-item .file-close {
  cursor: pointer;
  color: var(--text-2);
  font-size: 16px;
  transition: color 0.1s;
}

.file-item .file-close:hover { color: var(--red); }

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: var(--text-2);
  text-align: center;
}

.empty .material-icons-round {
  font-size: 36px;
  margin-bottom: 8px;
  opacity: 0.4;
}

.empty p { font-size: 12px; }

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 4px;
  gap: 16px;
}

.metric {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-2);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.metric span {
  font-size: 32px;
  font-weight: 800;
  letter-spacing: -1.5px;
  color: var(--text);
}

.metric-blue span { color: var(--blue); }

.search-input-wrap {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.search-input-wrap input {
  flex: 1;
  background: rgba(255,255,255,0.15);
  border: 1px solid rgba(255,255,255,0.2);
  color: #fff;
}

.search-input-wrap input::placeholder { color: rgba(255,255,255,0.6); }

.search-input-wrap input:focus {
  border-color: #fff;
  box-shadow: 0 0 0 3px rgba(255,255,255,0.15);
}

.search-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.search-meta {
  font-size: 11px;
  color: rgba(255,255,255,0.85);
  font-weight: 500;
}

.search-results {
  background: rgba(0,0,0,0.25);
  border-radius: 10px;
  max-height: 200px;
  overflow-y: auto;
  margin-top: 8px;
}

.result-item {
  padding: 10px 14px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  cursor: pointer;
  transition: background 0.1s;
}

.result-item:last-child { border: none; }
.result-item:hover { background: rgba(255,255,255,0.05); }
.result-item.selected { background: rgba(255,255,255,0.12); }

.result-title {
  font-size: 13px;
  font-weight: 600;
  color: #fff;
}

.result-meta {
  font-size: 11px;
  color: rgba(255,255,255,0.7);
  margin-top: 2px;
}

.api-tag {
  display: inline-block;
  padding: 1px 6px;
  background: rgba(255,255,255,0.2);
  border-radius: 4px;
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  margin-right: 6px;
  letter-spacing: 0.3px;
}

.selected-manga {
  margin-top: 10px;
  padding: 10px 14px;
  background: rgba(0,0,0,0.25);
  border-radius: 10px;
  border-left: 3px solid #fff;
  font-size: 12px;
  color: #fff;
}

.settings-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.setting label {
  color: rgba(255,255,255,0.85);
  margin-bottom: 4px;
}

.setting .dark-input {
  background: rgba(255,255,255,0.15);
  border-color: rgba(255,255,255,0.2);
  color: #fff;
}

.setting .dark-input:focus { border-color: #fff; }
.setting-full { grid-column: span 2; }
.setting input[type="range"] { background: rgba(0,0,0,0.25); }
.setting input[type="range"]::-webkit-slider-thumb { background: #fff; }

.toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-d);
}

.toggle input { display: none; }

.toggle-slider {
  width: 36px;
  height: 20px;
  background: var(--text-d-2);
  border-radius: 100px;
  position: relative;
  transition: background 0.2s;
}

.toggle-slider::after {
  content: '';
  position: absolute;
  width: 16px;
  height: 16px;
  background: #fff;
  border-radius: 50%;
  top: 2px;
  left: 2px;
  transition: left 0.2s;
}

.toggle input:checked + .toggle-slider { background: var(--blue); }
.toggle input:checked + .toggle-slider::after { left: 18px; }

.naming-section { margin-bottom: 16px; }

.format-input {
  background: var(--dark);
  color: var(--text);
  border-color: var(--border);
  margin-bottom: 10px;
}

.format-input:disabled { opacity: 0.5; }

.var-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.var-tag {
  display: inline-block;
  padding: 3px 8px;
  background: var(--dark);
  color: var(--blue);
  border-radius: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  cursor: pointer;
  border: 1px solid var(--border);
  transition: all 0.12s;
}

.var-tag:hover {
  background: var(--blue);
  color: #fff;
  border-color: var(--blue);
}

.preview-section {
  padding-top: 12px;
  border-top: 1px solid var(--border-l);
}

.preview-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-d-2);
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.preview-box {
  background: var(--dark);
  color: var(--green);
  padding: 12px 14px;
  border-radius: 10px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  word-break: break-all;
  min-height: 40px;
}

.meta-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.card-action {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 120px;
}

.action-content { width: 100%; }

.action-icons {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.progress-stats {
  display: flex;
  gap: 8px;
}

.stat-pill {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 100px;
  font-size: 11px;
  font-weight: 700;
}

.stat-pill span {
  margin-right: 4px;
  font-size: 13px;
  font-weight: 800;
}

.stat-blue { background: rgba(59,130,246,0.15); color: var(--blue); }
.stat-red { background: rgba(239,68,68,0.15); color: var(--red); }

.progress-track {
  height: 10px;
  background: var(--dark-2);
  border-radius: 100px;
  overflow: hidden;
  margin: 16px 0 10px;
}

.progress-fill {
  height: 100%;
  width: 0%;
  background: linear-gradient(90deg, var(--blue), var(--red));
  border-radius: 100px;
  transition: width 0.3s;
}

.progress-meta {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-2);
  font-family: 'JetBrains Mono', monospace;
}

#progress-current {
  color: var(--blue);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 70%;
}

.dl-icon {
  font-size: 28px;
  color: var(--blue);
}

.dl-list {
  display: grid;
  gap: 8px;
}

.dl-link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: var(--dark);
  color: var(--text);
  text-decoration: none;
  border-radius: 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  border: 1px solid var(--border);
  transition: all 0.15s;
}

.dl-link:hover {
  background: var(--blue);
  color: #fff;
  border-color: var(--blue);
  transform: translateX(4px);
}

.dl-link .material-icons-round { font-size: 18px; }

.dl-link .dl-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dl-link .dl-size {
  font-size: 10px;
  color: var(--text-2);
  background: var(--dark-2);
  padding: 2px 6px;
  border-radius: 100px;
}

.dl-link:hover .dl-size {
  background: rgba(255,255,255,0.2);
  color: #fff;
}

.log {
  background: #000;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--green);
  min-height: 200px;
  max-height: 280px;
  overflow-y: auto;
  white-space: pre-wrap;
  line-height: 1.6;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: 100px;
  font-size: 12px;
  font-weight: 600;
}

.badge .material-icons-round { font-size: 14px; }
.badge-ready { background: rgba(16,185,129,0.15); color: var(--green); }
.badge-working { background: rgba(245,158,11,0.15); color: var(--yellow); }
.badge-error { background: rgba(239,68,68,0.15); color: var(--red); }

.hidden { display: none !important; }

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 100px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-2); }

@media (max-width: 1000px) {
  .grid-row { grid-template-columns: 1fr; }
}

@media (max-width: 600px) {
  .dashboard { padding: 12px; gap: 12px; }
  .card { padding: 18px; border-radius: 14px; }
  .meta-fields, .settings-grid { grid-template-columns: 1fr; }
}
</style>
</head>
<body>

<div class="dashboard">

  <header class="header">
    <div class="brand">
      <span class="material-icons-round brand-icon">auto_stories</span>
      <span class="brand-name">CBZ Converter</span>
    </div>
    <span id="status-badge" class="badge badge-ready">
      <span class="material-icons-round">check_circle</span>Ready
    </span>
  </header>

  <!-- Top row: Files (large dark) + stack (search red, settings blue) -->
  <div class="grid-row">

    <div class="card card-dark">
      <div class="card-head">
        <div>
          <h3 class="card-title">Input Files</h3>
          <p class="card-sub">Drop or browse CBZ archives</p>
        </div>
        <div class="card-actions">
          <button class="icon-btn" onclick="document.getElementById('file-input').click()" title="Add files">
            <span class="material-icons-round">add</span>
          </button>
          <button class="icon-btn icon-btn-danger" onclick="clearFiles()" title="Clear all">
            <span class="material-icons-round">delete</span>
          </button>
        </div>
      </div>
      <input type="file" id="file-input" accept=".cbz" multiple style="display:none">
      <div class="file-list" id="file-list">
        <div class="empty">
          <span class="material-icons-round">cloud_upload</span>
          <p>Drop .cbz files here</p>
        </div>
      </div>
      <div class="card-footer">
        <div class="metric">files <span id="file-count">0</span></div>
        <div class="metric metric-blue">volumes <span id="vol-count">0</span></div>
      </div>
    </div>

    <div class="stack">

      <div class="card card-red">
        <div class="card-head-light">
          <div class="icon-circle">
            <span class="material-icons-round">search</span>
          </div>
          <div class="card-titles">
            <h3 class="card-title-light">Manga Lookup</h3>
            <p class="card-sub-light">MangaDex · MAL · AniList · Kitsu</p>
          </div>
        </div>
        <div class="search-input-wrap">
          <input type="text" id="search-input" placeholder="Search manga..." class="dark-input">
          <button class="search-btn" onclick="doSearch()">
            <span class="material-icons-round">arrow_forward</span>
          </button>
        </div>
        <div class="search-actions">
          <button class="pill-btn" onclick="autoDetect()">
            <span class="material-icons-round">auto_fix_high</span>Auto detect
          </button>
          <span id="search-status" class="search-meta"></span>
        </div>
        <div id="search-results" class="search-results hidden"></div>
        <div id="manga-info" class="selected-manga hidden"></div>
      </div>

      <div class="card card-blue">
        <div class="card-head-light">
          <div class="icon-circle">
            <span class="material-icons-round">tune</span>
          </div>
          <div class="card-titles">
            <h3 class="card-title-light">Settings</h3>
            <p class="card-sub-light">Format · Engine · Workers</p>
          </div>
        </div>
        <div class="settings-grid">
          <div class="setting">
            <label>Format</label>
            <select id="format-select" class="dark-input">
              <option value="pdf">PDF</option>
              <option value="epub">EPUB</option>
            </select>
          </div>
          <div class="setting">
            <label>Engine</label>
            <select id="engine-select" class="dark-input">
              <option value="img2pdf">img2pdf</option>
              <option value="reportlab">reportlab</option>
            </select>
          </div>
          <div class="setting">
            <label>Page Size</label>
            <select id="size-select" class="dark-input">
              <option value="Auto">Auto-detect</option>
              <option value="A4">A4</option>
              <option value="Letter">Letter</option>
              <option value="A5">A5</option>
            </select>
          </div>
          <div class="setting">
            <label>Workers</label>
            <select id="workers-select" class="dark-input">
              <option value="1">1</option>
              <option value="2">2</option>
              <option value="4" selected>4</option>
              <option value="6">6</option>
              <option value="8">8</option>
            </select>
          </div>
          <div class="setting setting-full">
            <label>Output Location</label>
            <select id="output-mode" class="dark-input">
              <option value="same_folder" selected>Same folder as source (in /OutputFiles)</option>
              <option value="custom">Custom path...</option>
            </select>
          </div>
          <div class="setting setting-full" id="custom-path-wrap" style="display:none">
            <label>Custom Output Path</label>
            <input type="text" id="output-path" class="dark-input" placeholder="/path/to/output">
          </div>
          <div class="setting setting-full">
            <label>Quality: <span id="quality-label">85</span></label>
            <input type="range" min="1" max="100" value="85" id="quality-input">
          </div>
        </div>
      </div>

    </div>
  </div>

  <!-- Naming + Overrides -->
  <div class="grid-row">

    <div class="card card-light">
      <div class="card-head">
        <div>
          <h3 class="card-title-dark">Output Naming</h3>
          <p class="card-sub-dark">Customize file names — or keep originals</p>
        </div>
        <label class="toggle">
          <input type="checkbox" id="keep-name">
          <span class="toggle-slider"></span>
          <span class="toggle-label">Keep name</span>
        </label>
      </div>

      <div class="naming-section">
        <input type="text" id="name-format" class="format-input"
          value="{manga_name} Vol.{volume} - Ch.{chapter} [{volume_title}] ({date})">
        <div class="var-tags" id="var-tags"></div>
      </div>

      <div class="preview-section">
        <div class="preview-label">Preview</div>
        <div class="preview-box" id="preview">—</div>
      </div>
    </div>

    <div class="card card-dark">
      <div class="card-head">
        <div>
          <h3 class="card-title">Overrides</h3>
          <p class="card-sub">Optional manual values</p>
        </div>
      </div>
      <div class="meta-fields">
        <div>
          <label>Title</label>
          <input type="text" id="m-title" class="dark-input">
        </div>
        <div>
          <label>Author</label>
          <input type="text" id="m-author" class="dark-input">
        </div>
        <div>
          <label>Vol. Title</label>
          <input type="text" id="m-vtitle" class="dark-input">
        </div>
        <div>
          <label>Date</label>
          <input type="text" id="m-date" class="dark-input">
        </div>
      </div>
    </div>

  </div>

  <!-- Action + Progress -->
  <div class="grid-row">

    <div class="card card-red card-action">
      <div class="action-content">
        <div class="action-icons">
          <button class="big-btn big-btn-red" onclick="startConvert()" id="convert-btn">
            <span class="material-icons-round">bolt</span>
            <span>Convert</span>
          </button>
          <button class="big-btn big-btn-blue" onclick="dryRun()" id="dry-btn">
            <span class="material-icons-round">visibility</span>
            <span>Dry Run</span>
          </button>
        </div>
      </div>
    </div>

    <div class="card card-dark">
      <div class="card-head">
        <div>
          <h3 class="card-title">Progress</h3>
          <p class="card-sub" id="progress-status">Idle</p>
        </div>
        <div class="progress-stats">
          <span class="stat-pill stat-blue"><span id="p-done">0</span> done</span>
          <span class="stat-pill stat-red"><span id="p-failed">0</span> failed</span>
        </div>
      </div>
      <div class="progress-track">
        <div class="progress-fill" id="progress-bar"></div>
      </div>
      <div class="progress-meta">
        <span id="progress-current">—</span>
        <span id="progress-pct">0%</span>
      </div>
    </div>

  </div>

  <!-- Downloads + Log -->
  <div class="grid-row">

    <div class="card card-light hidden" id="downloads-card">
      <div class="card-head">
        <div>
          <h3 class="card-title-dark">Downloads</h3>
          <p class="card-sub-dark">Click to save</p>
        </div>
        <span class="material-icons-round dl-icon">download</span>
      </div>
      <div class="dl-list" id="dl-list"></div>
    </div>

    <div class="card card-dark">
      <div class="card-head">
        <div>
          <h3 class="card-title">Activity Log</h3>
        </div>
        <button class="icon-btn" onclick="clearLog()" title="Clear log">
          <span class="material-icons-round">refresh</span>
        </button>
      </div>
      <div class="log" id="log">Waiting for activity...</div>
    </div>

  </div>

</div>

<script>
let files = [];
let searchResults = [];
let selectedManga = null;
let selectedIdx = 0;
let currentSession = null;
let pollInterval = null;
let VARIABLES = {};

document.addEventListener('DOMContentLoaded', async () => {
  try {
    const r = await fetch('/api/variables');
    VARIABLES = await r.json();
    renderVarTags();
  } catch (e) { console.error('Failed to load variables', e); }

  document.getElementById('file-input').addEventListener('change', e => handleFiles(e.target.files));

  const fl = document.getElementById('file-list');
  fl.addEventListener('dragover', e => { e.preventDefault(); fl.style.borderColor = 'var(--blue)'; });
  fl.addEventListener('dragleave', () => fl.style.borderColor = '');
  fl.addEventListener('drop', e => {
    e.preventDefault();
    fl.style.borderColor = '';
    handleFiles(e.dataTransfer.files);
  });

  document.getElementById('quality-input').addEventListener('input', e => {
    document.getElementById('quality-label').textContent = e.target.value;
  });

  document.getElementById('keep-name').addEventListener('change', e => {
    const fi = document.getElementById('name-format');
    if (e.target.checked) {
      fi.dataset.prev = fi.value;
      fi.value = '{original_filename}';
      fi.disabled = true;
    } else {
      fi.value = fi.dataset.prev || '{manga_name} Vol.{volume} - Ch.{chapter} [{volume_title}] ({date})';
      fi.disabled = false;
    }
    updatePreview();
  });

  document.getElementById('name-format').addEventListener('input', updatePreview);
  ['m-title', 'm-author', 'm-vtitle', 'm-date'].forEach(id => {
    document.getElementById(id).addEventListener('input', updatePreview);
  });
  document.getElementById('search-input').addEventListener('keypress', e => {
    if (e.key === 'Enter') doSearch();
  });

  updatePreview();
});

function renderVarTags() {
  const c = document.getElementById('var-tags');
  c.innerHTML = '';
  Object.entries(VARIABLES).forEach(([k, v]) => {
    const t = document.createElement('span');
    t.className = 'var-tag';
    t.textContent = k;
    t.title = v;
    t.onclick = () => {
      const fi = document.getElementById('name-format');
      if (!fi.disabled) {
        fi.value += k;
        updatePreview();
      }
    };
    c.appendChild(t);
  });
}

function handleFiles(fl) {
  for (let f of fl) {
    if (f.name.toLowerCase().endsWith('.cbz') && !files.find(x => x.name === f.name)) {
      files.push(f);
    }
  }
  renderFiles();
  if (files.length > 0 && selectedIdx >= files.length) selectedIdx = 0;
  if (files.length > 0) selectFile(selectedIdx);
}

function clearFiles() {
  files = [];
  selectedIdx = 0;
  renderFiles();
  updatePreview();
}

function removeFile(i) {
  files.splice(i, 1);
  if (selectedIdx >= files.length) selectedIdx = Math.max(0, files.length - 1);
  renderFiles();
  if (files.length > 0) selectFile(selectedIdx);
  else updatePreview();
}

async function renderFiles() {
  document.getElementById('file-count').textContent = files.length;

  const el = document.getElementById('file-list');
  if (!files.length) {
    el.innerHTML = '<div class="empty"><span class="material-icons-round">cloud_upload</span><p>Drop .cbz files here</p></div>';
    document.getElementById('vol-count').textContent = '0';
    return;
  }

  let parsed = [];
  try {
    parsed = await Promise.all(
      files.map(f => fetch('/api/parse?filename=' + encodeURIComponent(f.name)).then(r => r.json()))
    );
  } catch (e) {
    parsed = files.map(() => ({}));
  }

  const volumes = new Set();
  parsed.forEach(p => { if (p.volume) volumes.add(p.volume); });
  document.getElementById('vol-count').textContent = volumes.size;

  el.innerHTML = files.map((f, i) => {
    const p = parsed[i] || {};
    const sizeMB = (f.size / 1024 / 1024).toFixed(1);
    return '<div class="file-item' + (i === selectedIdx ? ' selected' : '') + '" onclick="selectFile(' + i + ')">' +
      '<span class="material-icons-round file-icon">description</span>' +
      '<span class="file-name">' + esc(f.name) + '</span>' +
      (p.volume ? '<span class="vol-badge">v' + p.volume + '</span>' : '') +
      (p.chapter ? '<span class="ch-badge">c' + p.chapter + '</span>' : '') +
      '<span class="file-size">' + sizeMB + 'MB</span>' +
      '<span class="material-icons-round file-close" onclick="event.stopPropagation();removeFile(' + i + ')">close</span>' +
      '</div>';
  }).join('');
}

async function selectFile(i) {
  selectedIdx = i;
  await renderFiles();
  try {
    const r = await fetch('/api/parse?filename=' + encodeURIComponent(files[i].name));
    const d = await r.json();
    document.getElementById('search-input').value = d.manga_name || '';
    updatePreview();
  } catch (e) {}
}

async function doSearch() {
  const q = document.getElementById('search-input').value.trim();
  if (!q) return;
  setBadge('working', 'Searching...');
  document.getElementById('search-status').textContent = 'Searching all APIs...';

  try {
    const r = await fetch('/api/search?q=' + encodeURIComponent(q));
    const d = await r.json();
    searchResults = d.results || [];
    showResults();
    document.getElementById('search-status').textContent = searchResults.length + ' results';
    setBadge('ready', 'Ready');
  } catch (e) {
    setBadge('error', 'Error');
    document.getElementById('search-status').textContent = 'Search failed';
  }
}

async function autoDetect() {
  if (!files.length) {
    appendLog('Add a file first');
    return;
  }
  setBadge('working', 'Detecting...');
  document.getElementById('search-status').textContent = 'Auto-detecting...';

  try {
    const r = await fetch('/api/auto-detect?filename=' + encodeURIComponent(files[selectedIdx].name));
    const d = await r.json();
    document.getElementById('search-input').value = d.parsed.manga_name || '';

    if (d.results && d.results.length) {
      searchResults = d.results;
      showResults();
      document.getElementById('search-status').textContent = d.results.length + ' results';
    } else {
      document.getElementById('search-status').textContent = 'No results';
    }
    if (d.log) appendLog(d.log);
    setBadge('ready', 'Ready');
  } catch (e) {
    setBadge('error', 'Error');
  }
}

function showResults() {
  const el = document.getElementById('search-results');
  el.classList.remove('hidden');
  el.innerHTML = searchResults.map((r, i) => {
    const sources = (r.sources_merged && r.sources_merged.length) ? r.sources_merged : [r.source || 'API'];
    const tags = sources.map(s => '<span class="api-tag">' + esc(s) + '</span>').join('');
    return '<div class="result-item" onclick="pickResult(' + i + ')" id="res-' + i + '">' +
      '<div class="result-title">' + tags + esc(r.title) + '</div>' +
      '<div class="result-meta">' + esc((r.authors || []).join(', ') || '?') +
      ' · ' + (r.year || '?') + ' · ⭐' + (r.score || '?') + ' · ' + (r.status || '?') + '</div>' +
      '</div>';
  }).join('');
}

async function pickResult(i) {
  document.querySelectorAll('.result-item').forEach(el => el.classList.remove('selected'));
  const el = document.getElementById('res-' + i);
  if (el) el.classList.add('selected');

  selectedManga = searchResults[i];
  document.getElementById('m-title').value = selectedManga.title_english || selectedManga.title || '';
  document.getElementById('m-author').value = (selectedManga.authors || []).join(', ');
  if (selectedManga.year) document.getElementById('m-date').value = String(selectedManga.year);

  const sources = (selectedManga.sources_merged || [selectedManga.source]).join(', ');
  const info = document.getElementById('manga-info');
  info.innerHTML = '<b>' + esc(selectedManga.title) + '</b><br>' +
    '<span style="opacity:0.8">' + esc((selectedManga.authors || []).join(', ')) +
    ' · ' + (selectedManga.year || '?') + ' · ⭐' + (selectedManga.score || '?') +
    ' · ' + esc(sources) + '</span>';
  info.classList.remove('hidden');

  updatePreview();
}

async function updatePreview() {
  if (!files.length) {
    document.getElementById('preview').textContent = '—';
    return;
  }

  const f = files[selectedIdx];
  if (!f) return;

  try {
    const r = await fetch('/api/preview-file', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: f.name,
        name_format: document.getElementById('name-format').value,
        title: document.getElementById('m-title').value,
        author: document.getElementById('m-author').value,
        volume_title: document.getElementById('m-vtitle').value,
        date: document.getElementById('m-date').value,
        keep_name: document.getElementById('keep-name').checked,
      })
    });
    const d = await r.json();
    document.getElementById('preview').textContent = d.preview || '—';
  } catch (e) {
    document.getElementById('preview').textContent = '—';
  }
}

function buildFormData() {
  const fd = new FormData();
  files.forEach(f => fd.append('files', f));
  fd.append('format', document.getElementById('format-select').value);
  fd.append('engine', document.getElementById('engine-select').value);
  fd.append('page_size', document.getElementById('size-select').value);
  fd.append('quality', document.getElementById('quality-input').value);
  fd.append('workers', document.getElementById('workers-select').value);
  fd.append('name_format', document.getElementById('name-format').value);
  fd.append('keep_name', document.getElementById('keep-name').checked);
  fd.append('title', document.getElementById('m-title').value);
  fd.append('author', document.getElementById('m-author').value);
  fd.append('volume_title', document.getElementById('m-vtitle').value);
  fd.append('date', document.getElementById('m-date').value);
  if (selectedManga) fd.append('manga_json', JSON.stringify(selectedManga));
  return fd;
}

async function dryRun() {
  if (!files.length) {
    appendLog('Add files first');
    return;
  }
  setBadge('working', 'Dry run...');

  try {
    const r = await fetch('/api/dry-run', { method: 'POST', body: buildFormData() });
    const d = await r.json();

    let log = '\n═════════ DRY RUN ═════════\n';
    if (d.log) log += d.log + '\n';
    log += '\n';
    d.results.forEach(r => {
      log += r.input + '\n  → ' + r.output + '\n';
      const dt = [];
      if (r.vol) dt.push('vol=' + r.vol);
      if (r.ch) dt.push('ch=' + r.ch);
      if (r.vtitle) dt.push('"' + r.vtitle + '"');
      if (r.date) dt.push('date=' + r.date);
      if (dt.length) log += '    ' + dt.join(' | ') + '\n';
      log += '\n';
    });
    log += d.results.length + ' files would be converted\n═══════════════════════════';
    appendLog(log);
    setBadge('ready', 'Done');
  } catch (e) {
    setBadge('error', 'Error');
    appendLog('ERROR: ' + e.message);
  }
}

async function startConvert() {
  if (!files.length) {
    appendLog('Add files first');
    return;
  }

  const btn = document.getElementById('convert-btn');
  const dryBtn = document.getElementById('dry-btn');
  btn.disabled = true;
  dryBtn.disabled = true;

  setBadge('working', 'Converting...');
  document.getElementById('progress-status').textContent = 'Uploading...';
  document.getElementById('progress-bar').style.width = '5%';
  document.getElementById('downloads-card').classList.add('hidden');
  document.getElementById('p-done').textContent = '0';
  document.getElementById('p-failed').textContent = '0';

  appendLog('\n═══ Starting conversion ═══');

  try {
    const r = await fetch('/api/convert', { method: 'POST', body: buildFormData() });
    const d = await r.json();

    if (d.session_id) {
      currentSession = d.session_id;
      pollStatus();
    } else {
      btn.disabled = false;
      dryBtn.disabled = false;
      setBadge('error', 'Failed');
      appendLog('ERROR: ' + (d.error || 'Unknown error'));
    }
  } catch (e) {
    btn.disabled = false;
    dryBtn.disabled = false;
    setBadge('error', 'Error');
    appendLog('ERROR: ' + e.message);
  }
}

function pollStatus() {
  if (pollInterval) clearInterval(pollInterval);
  let lastLogLen = 0;

  pollInterval = setInterval(async () => {
    if (!currentSession) {
      clearInterval(pollInterval);
      return;
    }

    try {
      const r = await fetch('/api/status/' + currentSession);
      if (!r.ok) {
        clearInterval(pollInterval);
        return;
      }
      const s = await r.json();

      const pct = Math.round(s.progress * 100);
      document.getElementById('progress-bar').style.width = pct + '%';
      document.getElementById('progress-pct').textContent = pct + '%';
      document.getElementById('p-done').textContent = s.done;
      document.getElementById('p-failed').textContent = s.failed;
      document.getElementById('progress-current').textContent = s.current || '—';
      document.getElementById('progress-status').textContent =
        s.complete ? 'Complete' : 'Processing ' + (s.done + s.failed) + ' / ' + s.total;

      if (s.log && s.log.length > lastLogLen) {
        appendLog(s.log.substring(lastLogLen), false);
        lastLogLen = s.log.length;
      }

      if (s.downloads && s.downloads.length) {
        const dl = document.getElementById('dl-list');
        dl.innerHTML = s.downloads.map(f =>
          '<a class="dl-link" href="/download/' + encodeURIComponent(f.filename) + '" download>' +
          '<span class="material-icons-round">download</span>' +
          '<span class="dl-name">' + esc(f.display_name) + '</span>' +
          '<span class="dl-size">' + f.size_mb + 'MB</span></a>'
        ).join('');
        document.getElementById('downloads-card').classList.remove('hidden');
      }

      if (s.complete) {
        clearInterval(pollInterval);
        currentSession = null;
        document.getElementById('convert-btn').disabled = false;
        document.getElementById('dry-btn').disabled = false;
        setBadge(s.failed === 0 ? 'ready' : 'error',
                 s.failed === 0 ? s.done + ' done!' : s.failed + ' failed');
        appendLog('\n═══ Done: ' + s.done + ' ok, ' + s.failed + ' failed ═══');
      }
    } catch (e) {
      console.error(e);
    }
  }, 800);
}

function setBadge(type, text) {
  const el = document.getElementById('status-badge');
  el.className = 'badge badge-' + type;
  const icons = { ready: 'check_circle', working: 'autorenew', error: 'error' };
  el.innerHTML = '<span class="material-icons-round">' + icons[type] + '</span>' + text;
}

function appendLog(text, addNewline) {
  if (addNewline === undefined) addNewline = true;
  const el = document.getElementById('log');
  if (el.textContent === 'Waiting for activity...') el.textContent = '';
  el.textContent += (addNewline ? '\n' : '') + text;
  el.scrollTop = el.scrollHeight;
}

function clearLog() {
  document.getElementById('log').textContent = 'Waiting for activity...';
}

function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}
</script>

</body>
</html>"""


def run_web_dashboard(port=5000):
    if not HAS_FLASK:
        print("Flask required: pip install flask")
        sys.exit(1)

    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1GB

    resolver = MetadataResolver()
    out_dir = os.path.join(tempfile.gettempdir(), "cbz_out")
    up_dir = os.path.join(tempfile.gettempdir(), "cbz_up")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(up_dir, exist_ok=True)

    JOBS = {}
    JOBS_LOCK = threading.Lock()

    @app.route("/")
    def index():
        return Response(HTML_PAGE, mimetype="text/html")

    @app.route("/api/variables")
    def api_vars():
        return jsonify(AVAILABLE_VARIABLES)

    @app.route("/api/parse")
    def api_parse():
        p = parse_filename(request.args.get("filename", ""))
        return jsonify({
            "manga_name": p.manga_name, "volume": p.volume,
            "chapter": p.chapter, "group": p.group,
            "pattern": p.source_pattern,
            "is_volume_only": p.is_volume_only,
        })

    @app.route("/api/search")
    def api_search():
        q = request.args.get("q", "").strip()
        if not q:
            return jsonify({"results": []})
        try:
            results = resolver.api.search_manga(q, limit=10)
            return jsonify({"results": [r.to_dict() for r in results]})
        except Exception as e:
            return jsonify({"results": [], "error": str(e)})

    @app.route("/api/auto-detect")
    def api_auto():
        logs = []
        parsed, results = resolver.auto_detect(
            request.args.get("filename", ""), log_cb=logs.append)
        return jsonify({
            "parsed": {
                "manga_name": parsed.manga_name,
                "volume": parsed.volume,
                "chapter": parsed.chapter,
                "is_volume_only": parsed.is_volume_only,
            },
            "results": [r.to_dict() for r in results],
            "log": "\n".join(logs),
        })

    @app.route("/api/preview-file", methods=["POST"])
    def api_pf():
        d = request.json or {}
        fname = d.get("filename", "")

        if d.get("keep_name"):
            return jsonify({"preview": Path(fname).stem})

        p = parse_filename(fname)
        meta = FullMetadata(parsed=p)
        t = d.get("title", "")
        meta.manga_title = t or p.manga_name
        meta.manga_title_english = t
        meta.parsed.manga_name = t or p.manga_name
        meta.authors = [a.strip() for a in d.get("author", "").split(",") if a.strip()]
        meta.volume_title = d.get("volume_title", "")
        meta.release_date = d.get("date", "")
        return jsonify({
            "preview": format_output_name(meta, d.get("name_format", DEFAULT_FORMAT))
        })

    @app.route("/api/dry-run", methods=["POST"])
    def _resolve_output_dir(output_mode: str, output_path: str, source_filename: str = "") -> str:
        """
        Resolve where to put the output file.
        - same_folder: <source_dir>/OutputFiles
        - custom: user-specified path
        - fallback: temp output dir
        """
        if output_mode == "custom" and output_path.strip():
            path = os.path.abspath(os.path.expanduser(output_path.strip()))
            os.makedirs(path, exist_ok=True)
            return path

        # Default: same_folder mode → put in /OutputFiles next to source
        # Browser uploads don't have full source path, so we use the persistent default
        # output_dir but try to create an OutputFiles structure
        return ""  # signals "use default with subfolder"

    # Replace the existing api_dry route:

    @app.route("/api/dry-run", methods=["POST"])
    def api_dry():
        uploaded = request.files.getlist("files")
        fmt = request.form.get("format", "pdf")
        nf = request.form.get("name_format", DEFAULT_FORMAT)
        keep_name = request.form.get("keep_name") == "true"
        t_ov = request.form.get("title", "")
        a_ov = request.form.get("author", "")
        vt_ov = request.form.get("volume_title", "")
        d_ov = request.form.get("date", "")
        output_mode = request.form.get("output_mode", "same_folder")
        output_path = request.form.get("output_path", "")

        sel = None
        mj = request.form.get("manga_json", "")
        if mj:
            try:
                sel = MangaResult.from_dict(json.loads(mj))
            except Exception:
                pass

        # Determine output directory
        if output_mode == "custom" and output_path.strip():
            target_dir = os.path.abspath(os.path.expanduser(output_path.strip()))
        else:
            target_dir = os.path.join(out_dir, "OutputFiles")

        logs = []
        logs.append(f"Output directory: {target_dir}")
        results = []
        for uf in uploaded:
            fn = uf.filename or "?.cbz"
            if keep_name:
                p = parse_filename(fn)
                out_name = Path(fn).stem
                results.append({
                    "input": fn,
                    "output": out_name + "." + fmt,
                    "output_path": os.path.join(target_dir, out_name + "." + fmt),
                    "vol": p.volume, "ch": p.chapter,
                    "vtitle": "", "date": "",
                })
            else:
                meta = resolver.resolve_file(
                    fn, sel, t_ov, a_ov, vt_ov, d_ov, log_cb=logs.append)
                out = format_output_name(meta, nf) or Path(fn).stem
                results.append({
                    "input": fn,
                    "output": out + "." + fmt,
                    "output_path": os.path.join(target_dir, out + "." + fmt),
                    "vol": meta.parsed.volume,
                    "ch": meta.chapter_range or meta.parsed.chapter,
                    "vtitle": meta.volume_title,
                    "date": meta.release_date,
                })

        return jsonify({"results": results, "log": "\n".join(logs)})

    # Replace the existing api_conv route:

    @app.route("/api/convert", methods=["POST"])
    def api_conv():
        from converter import convert_cbz
        from workers import WorkerPool, Job, JobStatus

        uploaded = request.files.getlist("files")
        if not uploaded:
            return jsonify({"success": False, "errors": ["No files"], "downloads": []})

        fmt = request.form.get("format", "pdf")
        engine = request.form.get("engine", "img2pdf")
        ps = request.form.get("page_size", "Auto")
        q = int(request.form.get("quality", "85"))
        nf = request.form.get("name_format", DEFAULT_FORMAT)
        keep_name = request.form.get("keep_name") == "true"
        workers = int(request.form.get("workers", "4"))
        t_ov = request.form.get("title", "")
        a_ov = request.form.get("author", "")
        vt_ov = request.form.get("volume_title", "")
        d_ov = request.form.get("date", "")
        output_mode = request.form.get("output_mode", "same_folder")
        output_path = request.form.get("output_path", "")

        # Resolve target output directory
        if output_mode == "custom" and output_path.strip():
            try:
                target_dir = os.path.abspath(os.path.expanduser(output_path.strip()))
                os.makedirs(target_dir, exist_ok=True)
            except Exception as e:
                return jsonify({
                    "success": False,
                    "errors": [f"Cannot create output dir: {e}"],
                    "downloads": [],
                })
        else:
            # same_folder mode → since browser uploads don't have source paths,
            # fall back to a persistent /OutputFiles folder in the system output dir
            target_dir = os.path.join(out_dir, "OutputFiles")
            os.makedirs(target_dir, exist_ok=True)

        session_id = str(uuid.uuid4())[:8]

        sel = None
        mj = request.form.get("manga_json", "")
        if mj:
            try:
                sel = MangaResult.from_dict(json.loads(mj))
            except Exception:
                pass

        logs = []
        logs.append(f"Output directory: {target_dir}")
        jobs_data = []
        for i, uf in enumerate(uploaded):
            fn = uf.filename or "?.cbz"
            tmp = os.path.join(up_dir, session_id + "_" + str(i) + "_" + fn)
            uf.save(tmp)

            if keep_name:
                meta = FullMetadata(parsed=parse_filename(fn))
                out_name = Path(fn).stem
            else:
                meta = resolver.resolve_file(
                    fn, sel, t_ov, a_ov, vt_ov, d_ov,
                    log_cb=lambda m: logs.append("  " + m))
                out_name = format_output_name(meta, nf) or Path(fn).stem

            out_fn = out_name + "." + fmt
            out_path_full = os.path.join(target_dir, out_fn)
            jobs_data.append({
                "id": i, "fn": fn, "tmp": tmp,
                "out": out_path_full, "out_fn": out_fn, "meta": meta,
            })
            logs.append("[" + str(i + 1) + "] " + fn + " → " + out_fn)

        with JOBS_LOCK:
            JOBS[session_id] = {
                "total": len(jobs_data), "done": 0, "failed": 0,
                "current": "", "log": logs.copy(),
                "downloads": [], "errors": [], "complete": False,
                "output_dir": target_dir,
            }

        def run_conversion():
            pool = WorkerPool(max_workers=workers)

            def task_fn(job, progress_cb, log_cb, cancel):
                if cancel.is_set():
                    return
                jd = next((d for d in jobs_data if d["id"] == job.id), None)
                if not jd:
                    return

                with JOBS_LOCK:
                    JOBS[session_id]["current"] = jd["fn"]

                convert_cbz(
                    jd["tmp"], jd["out"], fmt, engine, ps, q,
                    jd["meta"].display_title, jd["meta"].author_str,
                    progress_cb, log_cb,
                )

                if os.path.isfile(jd["out"]):
                    sz = os.path.getsize(jd["out"]) / 1024 / 1024
                    log_cb("✓ " + jd["out_fn"] + " (" + ("%.1f" % sz) + "MB)")
                    with JOBS_LOCK:
                        JOBS[session_id]["downloads"].append({
                            "filename": jd["out_fn"],
                            "display_name": jd["out_fn"],
                            "size_mb": round(sz, 1),
                            "output_dir": target_dir,
                        })

            def on_update(job):
                with JOBS_LOCK:
                    s = JOBS[session_id]
                    if job.status == JobStatus.DONE:
                        s["done"] += 1
                    elif job.status == JobStatus.FAILED:
                        s["failed"] += 1
                        s["errors"].append(job.filename + ": " + job.error)

            def on_log(msg, color=""):
                with JOBS_LOCK:
                    JOBS[session_id]["log"].append(msg)

            pool.on_job_update = on_update
            pool.on_log = on_log

            job_list = [
                Job(id=jd["id"], filename=jd["fn"],
                    input_path=jd["tmp"], output_path=jd["out"])
                for jd in jobs_data
            ]

            pool.run_jobs(job_list, task_fn, sequential=(workers <= 1))

            for jd in jobs_data:
                try:
                    os.remove(jd["tmp"])
                except Exception:
                    pass

            with JOBS_LOCK:
                JOBS[session_id]["complete"] = True
                JOBS[session_id]["current"] = ""

        threading.Thread(target=run_conversion, daemon=True).start()
        return jsonify({"session_id": session_id, "started": True})

    # Replace api_status to include output_dir:

    @app.route("/api/status/<session_id>")
    def api_status(session_id):
        with JOBS_LOCK:
            s = JOBS.get(session_id)
            if not s:
                return jsonify({"error": "session not found"}), 404
            return jsonify({
                "total": s["total"],
                "done": s["done"],
                "failed": s["failed"],
                "current": s["current"],
                "log": "\n".join(s["log"][-100:]),
                "downloads": s["downloads"],
                "errors": s["errors"],
                "complete": s["complete"],
                "progress": (s["done"] + s["failed"]) / s["total"] if s["total"] else 0,
                "output_dir": s.get("output_dir", ""),
            })

    # Replace dl() route to search any subdirectory:

    @app.route("/download/<path:fn>")
    def dl(fn):
        # Search in standard out_dir AND OutputFiles subdir AND any custom locations
        candidates = [
            os.path.join(out_dir, fn),
            os.path.join(out_dir, "OutputFiles", fn),
        ]

        # Also check active job output dirs
        with JOBS_LOCK:
            for s in JOBS.values():
                od = s.get("output_dir", "")
                if od:
                    candidates.append(os.path.join(od, fn))

        for fp in candidates:
            if os.path.isfile(fp):
                return send_file(fp, as_attachment=True, download_name=fn)

        return jsonify({"error": "not found"}), 404

    print("\n  CBZ Converter Dashboard")
    print("  URL:    http://localhost:" + str(port))
    print("  Output: " + out_dir + "\n")

    import webbrowser
    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:" + str(port))).start()
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    run_web_dashboard()