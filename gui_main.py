#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube & Universal Scraper Video Downloader PRO v5.0
(PyQt6/PyQt5 + yt-dlp + Interactive Visual Video Selector + Disguised Stream Unpacker)

Képes:
1. YouTube és 1000+ ismert videómegosztó letöltésére (4K/1080p/MP3/stb.)
2. Átirányított / álcázott URL-ek (?em=..., Base64 paraméterek, több beágyazott lejátszó)
   esetén mindegyik lehetséges videót (borítóképpel, címmel, hosszal) kinyerni, és ha
   több eltérő videó van az oldalon, egy Vizuális Videóválasztó Ablakban (borítóképpel!)
   felajánlani a felhasználónak, hogy melyiket szeretné letölteni!
3. Álcázott videómegosztó klónok automatikus feloldására:
   - StreamHG / Ghbrisk / VidHide / Filemoon / StreamWish (eval(p,a,c,k,e,d) JWPlayer)
   - DoodStream / Playmogo / DS2Play (/pass_md5/... + makePlay() dinamikus token)
   - .image / .txt / .jpg kiterjesztésnek álcázott HLS (.m3u8) töredékek összefűzésére.
4. Teljes Weboldal / Sorozat / Galéria Scraperre (Batch Scraper) pipálható listával.
"""

import os
import sys
import html
import re
import time
import json
import base64
import random
import string
import shutil
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime

# Ensure bundled yt_dlp is importable first
APP_LIB_DIR = Path(__file__).resolve().parent
if str(APP_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(APP_LIB_DIR))

import yt_dlp
import extreme_resolvers

try:
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl
    from PyQt6.QtGui import QIcon, QPixmap, QFont, QColor, QDesktopServices
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QGridLayout, QLabel, QLineEdit, QPushButton, QComboBox,
        QCheckBox, QProgressBar, QFileDialog, QTextEdit, QTabWidget,
        QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QMessageBox,
        QGroupBox, QSplitter, QAbstractItemView, QSpinBox, QDialog,
        QScrollArea
    )
    QT_VER = 6
    CHECKED_STATE = Qt.CheckState.Checked
    UNCHECKED_STATE = Qt.CheckState.Unchecked
except ImportError:
    from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl
    from PyQt5.QtGui import QIcon, QPixmap, QFont, QColor, QDesktopServices
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QGridLayout, QLabel, QLineEdit, QPushButton, QComboBox,
        QCheckBox, QProgressBar, QFileDialog, QTextEdit, QTabWidget,
        QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QMessageBox,
        QGroupBox, QSplitter, QAbstractItemView, QSpinBox, QDialog,
        QScrollArea
    )
    QT_VER = 5
    CHECKED_STATE = Qt.Checked
    UNCHECKED_STATE = Qt.Unchecked

APP_VERSION = "2026.10.26-10"
APP_RELEASE_TAG = "v10.0"

ANSI_ESCAPE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def clean_ansi(text: str) -> str:
    if not text:
        return ""
    return ANSI_ESCAPE_RE.sub('', str(text)).strip()


def format_bytes(size) -> str:
    if size is None or size <= 0:
        return "Ismeretlen"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def format_duration(seconds) -> str:
    if not seconds:
        return "--:--"
    try:
        seconds = int(float(seconds))
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"
    except Exception:
        return str(seconds)


def unpack_dean_edwards(source: str) -> str:
    """
    Kicsomagolja az elrejtett 'eval(function(p,a,c,k,e,d)...)' JavaScript blokkokat.
    Támogatja a payloadon belüli maszkolt idézőjeleket (\\') is!
    """
    unpacked_chunks = []
    pattern = re.compile(
        r"\}\s*\(\s*'((?:\\.|[^'\\])*)'\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*'((?:\\.|[^'\\])*)'\.split\('\|'\)",
        re.DOTALL
    )
    for match in pattern.finditer(source):
        payload, radix_s, count_s, symtab_s = match.groups()
        radix = int(radix_s)
        count = int(count_s)
        symtab = symtab_s.split('|')

        def _base_encode(num: int, b: int) -> str:
            digits = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
            if num < b:
                return digits[num] if num < len(digits) else ""
            return _base_encode(num // b, b) + digits[num % b]

        result = payload
        for i in range(count - 1, -1, -1):
            if i < len(symtab) and symtab[i]:
                token = _base_encode(i, radix)
                val = symtab[i]
                result = re.sub(r'\b' + re.escape(token) + r'\b', lambda _, v=val: v, result)
        unpacked_chunks.append(result.replace(r"\'", "'").replace(r'\/', '/'))
    return "\n".join(unpacked_chunks)


def fetch_url_text(target_url: str, referer: str = "", timeout: int = 12) -> tuple:
    headers = {
        "User-Agent": DEFAULT_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "hu-HU,hu;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(target_url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        return raw.decode("utf-8", errors="ignore"), resp.url


def fetch_thumbnail_bytes(thumb_url: str, referer: str = "") -> bytes:
    if not thumb_url:
        return b""
    try:
        headers = {"User-Agent": DEFAULT_UA}
        if referer:
            headers["Referer"] = referer
        req = urllib.request.Request(thumb_url, headers=headers)
        with urllib.request.urlopen(req, timeout=6) as resp:
            return resp.read()
    except Exception:
        return b""


def extract_html_title(html: str, fallback: str = "Videó") -> str:
    bad_titles = {'x-leak', 'video', 'embed', 'player', 'not found', '404', 'error'}
    og_match = re.search(
        r'<meta[^>]+(?:property|name)=["\'](?:og:title|twitter:title)["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.IGNORECASE
    )
    if og_match:
        t = re.sub(r'\s+', ' ', og_match.group(1)).strip()
        if t and t.lower() not in bad_titles:
            return t
    t_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if t_match:
        t = re.sub(r'\s+', ' ', t_match.group(1)).strip()
        if t and t.lower() not in bad_titles:
            return t
    for h1_m in re.finditer(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL):
        t = re.sub(r'<[^>]+>', ' ', h1_m.group(1))
        t = re.sub(r'\s+', ' ', t).strip()
        if len(t) > 3 and t.lower() not in bad_titles:
            return t
    return fallback


def extract_html_thumbnail_and_duration(html: str, unpacked_js: str = "", base_url: str = "") -> tuple:
    """Kinyeri a videó borítóképét (thumbnail URL) és hosszát (másodperc vagy perc:mp)."""
    thumb_url = ""
    duration_str = ""

    # 1. Check unpacked JWPlayer / player config for image:"..." and duration:"..."
    if unpacked_js:
        img_m = re.search(r'image\s*:\s*["\'](https?://[^"\']+)["\']', unpacked_js, re.IGNORECASE)
        if img_m:
            thumb_url = img_m.group(1)
        dur_m = re.search(r'duration\s*:\s*["\']?(\d+(?:\.\d+)?)["\']?', unpacked_js, re.IGNORECASE)
        if dur_m:
            duration_str = format_duration(dur_m.group(1))

    # 2. Check HTML meta og:image / twitter:image / poster / vplayer img
    if not thumb_url:
        og_img = re.search(
            r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.IGNORECASE
        )
        if og_img:
            thumb_url = urllib.parse.urljoin(base_url, og_img.group(1))

    if not thumb_url:
        vp_img = re.search(r'id=["\']vplayer["\'][^>]*>.*?<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE | re.DOTALL)
        if vp_img:
            thumb_url = urllib.parse.urljoin(base_url, vp_img.group(1))

    if not duration_str:
        time_m = re.search(r'ico_time\.svg["\']\s*/>\s*(\d{1,2}:\d{2}(?::\d{2})?)', html, re.IGNORECASE)
        if time_m:
            duration_str = time_m.group(1)

    return thumb_url, duration_str


def resolve_disguised_embed(embed_url: str, parent_referer: str = "", extra_referers: list = None,
                            prefix_tag: str = "", base_priority: int = 1, log_fn=None) -> list:
    """
    Feloldja az álcázott videómegosztó lejátszókat ÉS a közvetlen bináris/HLS streameket
    (FetchV / Cat-Catch / StreamHG / Ghbrisk / VidHide / Filemoon / DoodStream / Playmogo / GoFile):
    Visszaadja a közvetlenül letölthető .mp4 / .m3u8 streamek listáját borítóképpel, fájlmérettel és hosszal!
    """
    # 0. FetchV-stílusú közvetlen médiafolyam próba (pl. store*.gofile.io/download/direct/...mp4, közvetlen .m3u8/.mp4)
    direct_stream_items = extreme_resolvers.probe_direct_media_stream(
        embed_url,
        referer=parent_referer or embed_url,
        extra_referers=extra_referers,
        prefix_tag=prefix_tag,
        base_priority=base_priority,
        log_fn=log_fn
    )
    if direct_stream_items:
        return direct_stream_items

    results = []
    try:
        html, final_embed = fetch_url_text(embed_url, referer=parent_referer or embed_url)
    except Exception as e:
        if log_fn:
            log_fn(f"[FELOLDÓ] Nem sikerült betölteni ({embed_url}): {e}")
        return results

    title = extract_html_title(html, fallback="Beágyazott_Videó")
    for suffix in [" - DoodStream", " - StreamHG", " - VidHide", " - Filemoon"]:
        if title.endswith(suffix):
            title = title[:-len(suffix)].strip()

    unpacked = extreme_resolvers.deobfuscate_all_js(html, log_fn=log_fn)
    thumb_url, duration_str = extract_html_thumbnail_and_duration(html, unpacked, final_embed)
    thumb_bytes = fetch_thumbnail_bytes(thumb_url, referer=final_embed) if thumb_url else b""

    tag_str = f"{prefix_tag} " if prefix_tag else ""
    host_name = urllib.parse.urlparse(final_embed).netloc

    # 0.5. Pornhub / Redtube / YouPorn / Aylo Network beágyazott és közvetlen feloldó
    if any(k in final_embed.lower() for k in ['pornhub.', 'redtube.', 'youporn.', 'phncdn.']) or 'mediaDefinitions' in html or 'flashvars_' in html:
        ph_items = extreme_resolvers.resolve_pornhub(html, final_embed, log_fn=log_fn)
        if ph_items:
            ph_thumb_bytes = b""
            if ph_items[0].get('thumb_url'):
                ph_thumb_bytes = fetch_thumbnail_bytes(ph_items[0]['thumb_url'], referer=final_embed)
            for it in ph_items:
                if ph_thumb_bytes:
                    it['thumb_bytes'] = ph_thumb_bytes
                if prefix_tag:
                    it['display_title'] = f"{prefix_tag} {it['title']}".strip()
                    it['label'] = f"[{prefix_tag}{it.get('type','Stream')}] {it['title'][:50]}"
            return ph_items

    # 0.6. XVideos / XNXX html5player beágyazott és közvetlen feloldó
    if any(k in final_embed.lower() for k in ['xvideos.', 'xnxx.']) or 'html5player.setVideoHLS' in html:
        xv_items = extreme_resolvers.resolve_xvideos(html, final_embed, log_fn=log_fn)
        if xv_items:
            xv_thumb_bytes = b""
            if xv_items[0].get('thumb_url'):
                xv_thumb_bytes = fetch_thumbnail_bytes(xv_items[0]['thumb_url'], referer=final_embed)
            for it in xv_items:
                if xv_thumb_bytes:
                    it['thumb_bytes'] = xv_thumb_bytes
                if prefix_tag:
                    it['display_title'] = f"{prefix_tag} {it['title']}".strip()
                    it['label'] = f"[{prefix_tag}{it.get('type','Stream')}] {it['title'][:50]}"
            return xv_items

    # 1. DoodStream / Playmogo / DS2Play / MyVidPlay klónok (/pass_md5/... + makePlay())
    m_dood = re.search(r"\$\.get\(['\"](/pass_md5/[^'\"]+)['\"]", html)
    if m_dood:
        try:
            pass_path = m_dood.group(1)
            token = pass_path.rstrip('/').split('/')[-1]
            pass_url = urllib.parse.urljoin(final_embed, pass_path)
            if log_fn:
                log_fn(f"[FELOLDÓ] 🔓 DoodStream/Playmogo álcázott token feloldása: {pass_url}")
            prefix_data, _ = fetch_url_text(pass_url, referer=final_embed)
            prefix_data = prefix_data.strip()
            if prefix_data.startswith("http"):
                rand10 = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
                mp4_url = f"{prefix_data}{rand10}?token={token}&expiry={int(time.time() * 1000)}"
                results.append({
                    'title': title,
                    'display_title': f"{tag_str}{title}".strip(),
                    'url': mp4_url,
                    'type': f"MP4 Közvetlen Stream ({host_name})",
                    'origin_desc': prefix_tag or f"Beágyazott lejátszó ({host_name})",
                    'duration': duration_str or "Ismeretlen",
                    'thumb_url': thumb_url,
                    'thumb_bytes': thumb_bytes,
                    'referer': final_embed,
                    'embed_source': final_embed,
                    'embed_parent_ref': parent_referer or embed_url,
                    'video_group_id': final_embed,
                    'priority': base_priority,
                    'label': f"[{tag_str}MP4 - {host_name}] {title[:55]}"
                })
        except Exception as e:
            if log_fn:
                log_fn(f"[FELOLDÓ] DoodStream pass_md5 hiba: {e}")

    # 2. StreamHG / Ghbrisk / Filemoon / VidHide / JWPlayer eval(function(p,a,c,k,e,d)...)
    # A lejátszó saját prioritása: links.hls4 (TikTok CDN PNG-álcázott 1080p) || links.hls2 (premilkyway)
    if unpacked:
        for idx_k, (key, stype_desc, prio_offset) in enumerate([
            ('hls4', f"HLS 1080p Valódi Stream (.m3u8/PNG-TS - {host_name})", 0),
            ('hls2', f"HLS 1080p Tartalék Stream (.m3u8 - {host_name})", 2),
        ]):
            km = re.search(r'"' + key + r'"\s*:\s*"([^"]+)"', unpacked)
            if km:
                raw_u = km.group(1).strip()
                full_u = urllib.parse.urljoin(final_embed, raw_u)
                results.append({
                    'title': title,
                    'display_title': f"{tag_str}{title}".strip() if idx_k == 0 else f"{tag_str}{title} (Tartalék sáv)".strip(),
                    'url': full_u,
                    'type': stype_desc,
                    'origin_desc': prefix_tag or f"Beágyazott lejátszó ({host_name})",
                    'duration': duration_str or "Ismeretlen",
                    'thumb_url': thumb_url,
                    'thumb_bytes': thumb_bytes if idx_k == 0 else b"",
                    'referer': final_embed,
                    'embed_source': final_embed,
                    'embed_parent_ref': parent_referer or embed_url,
                    'video_group_id': final_embed,
                    'is_backup_stream': idx_k > 0,
                    'priority': base_priority + prio_offset,
                    'label': f"[{tag_str}{stype_desc}] {title[:50]}"
                })

        # 3. Mixdrop MDCore.wurl
        mix_u = extreme_resolvers.resolve_mixdrop(unpacked, final_embed, log_fn=log_fn)
        if mix_u:
            results.append({
                'title': title,
                'display_title': f"{tag_str}{title}".strip(),
                'url': mix_u,
                'type': f"Mixdrop Stream ({host_name})",
                'origin_desc': prefix_tag or f"Mixdrop ({host_name})",
                'duration': duration_str or "Ismeretlen",
                'thumb_url': thumb_url,
                'thumb_bytes': thumb_bytes,
                'referer': final_embed,
                'embed_source': final_embed,
                'embed_parent_ref': parent_referer or embed_url,
                'video_group_id': final_embed,
                'priority': base_priority,
                'label': f"[{tag_str}Mixdrop] {title[:55]}"
            })

    # 4. VOE.sx LUT + ROT13 + Base64
    voe_u = extreme_resolvers.resolve_voe_payload(html, final_embed, fetch_url_text, log_fn=log_fn)
    if voe_u:
        results.append({
            'title': title,
            'display_title': f"{tag_str}{title}".strip(),
            'url': voe_u,
            'type': f"VOE HLS Stream ({host_name})",
            'origin_desc': prefix_tag or f"VOE ({host_name})",
            'duration': duration_str or "Ismeretlen",
            'thumb_url': thumb_url,
            'thumb_bytes': thumb_bytes,
            'referer': final_embed,
            'embed_source': final_embed,
            'embed_parent_ref': parent_referer or embed_url,
            'video_group_id': final_embed,
            'priority': base_priority,
            'label': f"[{tag_str}VOE Stream] {title[:55]}"
        })

    # 5. Streamtape dynamic token
    st_u = extreme_resolvers.resolve_streamtape(html, final_embed, log_fn=log_fn)
    if st_u:
        results.append({
            'title': title,
            'display_title': f"{tag_str}{title}".strip(),
            'url': st_u,
            'type': f"Streamtape MP4 ({host_name})",
            'origin_desc': prefix_tag or f"Streamtape ({host_name})",
            'duration': duration_str or "Ismeretlen",
            'thumb_url': thumb_url,
            'thumb_bytes': thumb_bytes,
            'referer': final_embed,
            'embed_source': final_embed,
            'embed_parent_ref': parent_referer or embed_url,
            'video_group_id': final_embed,
            'priority': base_priority,
            'label': f"[{tag_str}Streamtape MP4] {title[:55]}"
        })

    # 6. TurboVidPlay / Emturbovid intermediate urlPlay resolver
    tv_u = extreme_resolvers.resolve_turbovidplay(html, final_embed, fetch_url_text, log_fn=log_fn)
    if tv_u:
        results.append({
            'title': title,
            'display_title': f"{tag_str}{title}".strip(),
            'url': tv_u,
            'type': f"TurboVid HLS Stream ({host_name})",
            'origin_desc': prefix_tag or f"TurboVid ({host_name})",
            'duration': duration_str or "Ismeretlen",
            'thumb_url': thumb_url,
            'thumb_bytes': thumb_bytes,
            'referer': final_embed,
            'embed_source': final_embed,
            'embed_parent_ref': parent_referer or embed_url,
            'video_group_id': final_embed,
            'priority': base_priority,
            'label': f"[{tag_str}TurboVid HLS] {title[:55]}"
        })

    # 7. FileMoon / Byse / F16Px AES-256-GCM encrypted API (/api/videos/{code}/embed/playback)
    if not results:
        fm_u = extreme_resolvers.resolve_filemoon_f16px_aesgcm(final_embed, log_fn=log_fn)
        if fm_u:
            results.append({
                'title': title,
                'display_title': f"{tag_str}{title}".strip(),
                'url': fm_u,
                'type': f"AES-GCM HLS Stream ({host_name})",
                'origin_desc': prefix_tag or f"AES-GCM Lejátszó ({host_name})",
                'duration': duration_str or "Ismeretlen",
                'thumb_url': thumb_url,
                'thumb_bytes': thumb_bytes,
                'referer': final_embed,
                'embed_source': final_embed,
                'embed_parent_ref': parent_referer or embed_url,
                'video_group_id': final_embed,
                'priority': base_priority,
                'label': f"[{tag_str}AES-GCM HLS] {title[:55]}"
            })

    # 8. Generic player sources (Uqload, Vidoza, Vidmoly, Lulustream, Supervideo, Flowplayer, JWPlayer)
    if not results:
        gen_urls = extreme_resolvers.scrape_generic_player_sources(html + "\n" + unpacked, final_embed)
        for idx_g, gu in enumerate(gen_urls):
            stype_g = "HLS Stream (.m3u8)" if ".m3u8" in gu.lower() else "Közvetlen Videó (.mp4)"
            results.append({
                'title': title,
                'display_title': f"{tag_str}{title}".strip(),
                'url': gu,
                'type': f"{stype_g} ({host_name})",
                'origin_desc': prefix_tag or f"Lejátszó ({host_name})",
                'duration': duration_str or "Ismeretlen",
                'thumb_url': thumb_url,
                'thumb_bytes': thumb_bytes if idx_g == 0 else b"",
                'referer': final_embed,
                'embed_source': final_embed if idx_g == 0 else '',
                'embed_parent_ref': parent_referer or embed_url,
                'video_group_id': final_embed,
                'is_backup_stream': idx_g > 0,
                'priority': base_priority + idx_g,
                'label': f"[{tag_str}{stype_g}] {title[:50]}"
            })

    return results


class VideoSelectorDialog(QDialog):
    """
    Vizuális Videóválasztó Ablak:
    Ha egy oldalon több különböző videót talál a Scraper (pl. egy ?em= paraméterben
    átadott videót ÉS a háttéroldal saját videóját), borítóképpel, címmel, hosszal és
    forrással egymás mellett/alatt megmutatja őket, hogy a felhasználó 1 kattintással
    kiválaszthassa a valódit!
    """
    def __init__(self, primary_candidates: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🎬 Több videót találtam az oldalon — Melyiket szeretnéd letölteni?")
        self.resize(820, 520)
        self.selected_item = None
        self.download_immediately = False
        self.download_all = False

        self.setStyleSheet("""
            QDialog {
                background-color: #11131a;
                color: #f3f4f6;
            }
            QFrame#videoCard {
                background-color: #1a1e2b;
                border: 2px solid #2e364f;
                border-radius: 12px;
                padding: 10px;
            }
            QFrame#videoCard:hover {
                border: 2px solid #60a5fa;
                background-color: #202637;
            }
            QPushButton#dlNowBtn {
                background-color: #e11d48;
                border: 1px solid #f43f5e;
                border-radius: 8px;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                padding: 9px 18px;
            }
            QPushButton#dlNowBtn:hover {
                background-color: #be123c;
            }
            QPushButton#selectOnlyBtn {
                background-color: #2563eb;
                border: 1px solid #3b82f6;
                border-radius: 8px;
                color: #ffffff;
                font-weight: 600;
                padding: 8px 14px;
            }
            QPushButton#selectOnlyBtn:hover {
                background-color: #1d4ed8;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel(
            "🔍 <b>Az oldalon több különböző videó található!</b><br>"
            "<span style='color:#9ca3af; font-size:12px;'>"
            "Válaszd ki a borítókép és cím alapján, hogy melyik a keresett valódi videó:"
            "</span>"
        )
        header.setStyleSheet("font-size: 15px; color: #f8fafc;")
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background-color: transparent;")
        container = QWidget()
        cards_layout = QVBoxLayout(container)
        cards_layout.setSpacing(12)

        for idx, cand in enumerate(primary_candidates, 1):
            card = QFrame()
            card.setObjectName("videoCard")
            row = QHBoxLayout(card)
            row.setSpacing(14)

            # Thumbnail image
            thumb_lbl = QLabel()
            thumb_lbl.setFixedSize(220, 124)
            thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb_lbl.setStyleSheet(
                "background-color: #0d0f14; border: 1px solid #374151; border-radius: 8px; color: #6b7280;"
            )
            t_bytes = cand.get('thumb_bytes', b'')
            if not t_bytes and cand.get('thumb_url'):
                t_bytes = fetch_thumbnail_bytes(cand['thumb_url'], referer=cand.get('referer', ''))
                if t_bytes:
                    cand['thumb_bytes'] = t_bytes
            if t_bytes:
                pix = QPixmap()
                if pix.loadFromData(t_bytes):
                    thumb_lbl.setPixmap(
                        pix.scaled(220, 124, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    )
            else:
                thumb_lbl.setText(f"🎬 Videó #{idx}\n(Nincs borítókép)")
            row.addWidget(thumb_lbl)

            # Metadata column
            info_col = QVBoxLayout()
            title_lbl = QLabel(f"#{idx}: {cand.get('title', 'Videó')}")
            title_lbl.setWordWrap(True)
            title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")

            origin_lbl = QLabel(f"📍 Forrás helye: {cand.get('origin_desc', '-')}")
            origin_lbl.setStyleSheet("color: #a78bfa; font-weight: 600; font-size: 12px;")

            meta_lbl = QLabel(
                f"⏱ Hossz: {cand.get('duration', '--:--')}   |   🎞 Típus: {cand.get('type', '-')}"
            )
            meta_lbl.setStyleSheet("color: #93c5fd; font-size: 12px;")

            url_lbl = QLabel(f"🔗 Lejátszó: {cand.get('referer', cand.get('url', ''))[:75]}")
            url_lbl.setStyleSheet("color: #6b7280; font-size: 11px;")

            info_col.addWidget(title_lbl)
            info_col.addWidget(origin_lbl)
            info_col.addWidget(meta_lbl)
            info_col.addWidget(url_lbl)
            info_col.addStretch()

            btn_row = QHBoxLayout()
            dl_btn = QPushButton("⬇️ Ezt töltöm le most!")
            dl_btn.setObjectName("dlNowBtn")
            dl_btn.clicked.connect(lambda _=False, c=cand: self._choose(c, download_now=True))

            sel_btn = QPushButton("🎯 Csak kiválasztom")
            sel_btn.setObjectName("selectOnlyBtn")
            sel_btn.clicked.connect(lambda _=False, c=cand: self._choose(c, download_now=False))

            btn_row.addWidget(dl_btn)
            btn_row.addWidget(sel_btn)
            btn_row.addStretch()
            info_col.addLayout(btn_row)

            row.addLayout(info_col, 1)
            cards_layout.addWidget(card)

        cards_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        # Bottom bar
        bottom_row = QHBoxLayout()
        both_btn = QPushButton(f"📦 Mind a(z) {len(primary_candidates)} videó letöltése egymás után")
        both_btn.clicked.connect(self._choose_all)
        cancel_btn = QPushButton("Mégse")
        cancel_btn.clicked.connect(self.reject)

        bottom_row.addWidget(both_btn)
        bottom_row.addStretch()
        bottom_row.addWidget(cancel_btn)
        layout.addLayout(bottom_row)

    def _choose(self, item: dict, download_now: bool):
        self.selected_item = item
        self.download_immediately = download_now
        self.accept()

    def _choose_all(self):
        self.download_all = True
        self.accept()


class DeepStreamScannerWorker(QThread):
    """
    Mély Stream- és Weboldal Scraper Motor v5.0:
    - Ha az URL-ben ?em=... / ?embed=... paraméter van, először a ?em= paraméterben
      lévő videót fejti vissza (#1: ?em= Beágyazott Videó), majd a tiszta főoldal
      alapértelmezett videóját is (#2: Főoldal Háttérvideó), borítóképekkel és hosszal!
    """
    streams_found = pyqtSignal(list, str)
    log_msg = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, url: str, browser_cookies: str = "", use_headless: bool = True,
                 crawl_subpages: bool = False, max_subpages: int = 12):
        super().__init__()
        self.url = url
        self.browser_cookies = browser_cookies
        self.use_headless = use_headless
        self.crawl_subpages = crawl_subpages
        self.max_subpages = max_subpages
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def _dump_dom_headless(self, target_url: str) -> str:
        for bin_name in ["chromium", "google-chrome"]:
            bin_path = shutil.which(bin_name)
            if bin_path:
                try:
                    self.log_msg.emit(f"[SCRAPER] Dinamikus JS DOM kiértékelés ({bin_name} headless): {target_url}")
                    proc = subprocess.run(
                        [
                            bin_path, "--headless", "--disable-gpu", "--no-sandbox",
                            "--virtual-time-budget=4500", "--dump-dom", target_url
                        ],
                        capture_output=True, text=True, timeout=15
                    )
                    if proc.stdout:
                        return proc.stdout
                except Exception as e:
                    self.log_msg.emit(f"[SCRAPER] Headless böngésző figyelmeztetés: {e}")
        return ""

    def _extract_media_from_text(self, text: str, base_url: str, referer_url: str,
                                 context_title: str = "", prefix_tag: str = "", base_priority: int = 2) -> list:
        results = []
        seen = set()

        normalized = text.replace(r'\/', '/')

        unpacked = extreme_resolvers.deobfuscate_all_js(text, log_fn=self.log_msg.emit)
        if unpacked:
            normalized += "\n" + unpacked

        for b64_match in re.findall(r'(aHR0cHM6Ly[A-Za-z0-9+/=]{12,260})', normalized):
            try:
                decoded = base64.b64decode(b64_match + "===").decode("utf-8", errors="ignore")
                if decoded.startswith("http"):
                    normalized += f'\n"{decoded}"\n'
            except Exception:
                pass

        for atob_match in re.findall(r'atob\(\s*["\']([A-Za-z0-9+/=]{16,300})["\']\s*\)', normalized):
            try:
                decoded = base64.b64decode(atob_match + "===").decode("utf-8", errors="ignore")
                if "http" in decoded or ".m3u8" in decoded or ".mp4" in decoded:
                    normalized += f'\n"{decoded}"\n'
            except Exception:
                pass

        tag_str = f"{prefix_tag} " if prefix_tag else ""

        media_regex = re.compile(
            r'''(https?://[^\s"'<>\\]+?\.(?:m3u8|mpd|mp4|webm|m4v|mkv)(?:\?[^\s"'<>\\]*)?)''',
            re.IGNORECASE
        )
        for m in media_regex.finditer(normalized):
            candidate = html.unescape(m.group(1).rstrip('",;\')]'))
            if candidate in seen:
                continue
            if any(bad in candidate.lower() for bad in ['sprite', 'thumb', 'preview.mp4', '.gif', 'blank.mp4']):
                continue
            seen.add(candidate)
            low = candidate.lower()
            if '.m3u8' in low:
                stype = f"HLS Darabolt (.m3u8)"
                prio = base_priority
            elif '.mpd' in low:
                stype = f"DASH Darabolt (.mpd)"
                prio = base_priority + 1
            else:
                stype = f"Közvetlen Videó (.mp4/.webm)"
                prio = base_priority

            title = context_title or os.path.basename(urllib.parse.urlparse(candidate).path) or 'Stream'
            results.append({
                'title': title,
                'display_title': f"{tag_str}{title}".strip(),
                'url': candidate,
                'type': stype,
                'origin_desc': prefix_tag or base_url,
                'duration': '--:--',
                'thumb_bytes': b'',
                'referer': referer_url,
                'video_group_id': candidate,
                'priority': prio,
                'label': f"[{tag_str}{stype}] {title[:45]} — {candidate[:65]}"
            })

        return results

    def _extract_iframes(self, html: str, base_url: str) -> tuple:
        iframes = []
        seen = set()
        hidden_ifs, allowed_refs = extreme_resolvers.extract_hidden_ember_and_redirect_domains(html, base_url)
        for h_if in hidden_ifs:
            if h_if not in seen:
                seen.add(h_if)
                iframes.append(h_if)

        for m in re.finditer(r'<iframe[^>]+(?:src|data-src|data-lazy-src)=["\']([^"\']+)["\']', html, re.IGNORECASE):
            raw_src = m.group(1).strip()
            if not raw_src or raw_src.startswith(('javascript:', 'about:', 'data:', '<#', '#')):
                continue
            full_src = urllib.parse.urljoin(base_url, raw_src)
            if any(ad in full_src.lower() for ad in [
                'doubleclick', 'googlesyndication', 'facebook.com/plugins',
                'googletagmanager', 'google.com/recaptcha', 'disqus.com', 'vitting.org'
            ]):
                continue
            if full_src not in seen:
                seen.add(full_src)
                iframes.append(full_src)
        return iframes, allowed_refs

    def _extract_candidate_video_subpages(self, html: str, base_url: str) -> list:
        parsed_base = urllib.parse.urlparse(base_url)
        base_domain = parsed_base.netloc
        subpages = []
        seen = {base_url}

        video_link_keywords = (
            'video', 'watch', 'episode', 'epizod', 'resz', 'part', 'film',
            'movie', 'play', 'stream', 'embed', 'kurs', 'lesson', 'lecke', 'media'
        )
        ignore_ext = ('.jpg', '.jpeg', '.png', '.gif', '.svg', '.css', '.js', '.pdf', '.zip', '.ico')

        for m in re.finditer(r'<a[^>]+href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL):
            href, anchor_html = m.groups()
            full_url = urllib.parse.urljoin(base_url, href.strip())
            parsed = urllib.parse.urlparse(full_url)
            if parsed.netloc != base_domain:
                continue
            if parsed.path.lower().endswith(ignore_ext):
                continue
            if full_url in seen:
                continue

            anchor_text = re.sub(r'<[^>]+>', ' ', anchor_html)
            anchor_text = re.sub(r'\s+', ' ', anchor_text).strip()
            path_low = parsed.path.lower() + "?" + parsed.query.lower()

            if any(k in path_low for k in video_link_keywords) or (
                len(parsed.path.strip('/').split('/')) >= 2 and re.search(r'\d', parsed.path)
            ):
                seen.add(full_url)
                subpages.append((full_url, anchor_text or parsed.path.strip('/')))

        return subpages[:self.max_subpages]

    def _scan_single_page(self, target_url: str, parent_referer: str,
                          depth_label: str = "Főoldal", prefix_tag: str = "", base_priority: int = 1,
                          extra_referers: list = None) -> tuple:
        discovered = []
        page_title = target_url

        direct_embed_items = resolve_disguised_embed(
            target_url, parent_referer=parent_referer, extra_referers=extra_referers,
            prefix_tag=prefix_tag, base_priority=base_priority, log_fn=self.log_msg.emit
        )
        if direct_embed_items:
            discovered.extend(direct_embed_items)
            page_title = direct_embed_items[0].get('title', target_url)
            # If target_url was already a direct binary/HLS stream (like GoFile .mp4), don't fetch it as HTML!
            if any(it.get('is_direct_binary') or '.m3u8' in it.get('url', '').lower() for it in direct_embed_items):
                if any(ext in target_url.lower() for ext in ['.mp4', '.m3u8', '.m3u', '.mpd', '.webm', '/download/direct/', 'gofile.io']):
                    return discovered, page_title, ""

        html = ""
        try:
            html, _ = fetch_url_text(target_url, referer=parent_referer)
            page_title = extract_html_title(html, fallback=page_title)
            _, page_dur = extract_html_thumbnail_and_duration(html, "", target_url)
        except Exception as e:
            page_dur = ""
            self.log_msg.emit(f"[SCRAPER] ({depth_label}) HTML letöltési figyelmeztetés: {e}")

        iframes, allowed_refs = self._extract_iframes(html, target_url) if html else ([], [])
        merged_refs = list(extra_referers or [])
        for ar in allowed_refs:
            if ar not in merged_refs:
                merged_refs.append(ar)

        for idx, iframe_url in enumerate(iframes[:8], 1):
            if self._cancelled:
                break
            self.log_msg.emit(f"[SCRAPER] ({depth_label}) Iframe #{idx} feloldása: {iframe_url}")

            resolved_from_iframe = resolve_disguised_embed(
                iframe_url, parent_referer=target_url, extra_referers=merged_refs,
                prefix_tag=prefix_tag, base_priority=base_priority, log_fn=self.log_msg.emit
            )
            if resolved_from_iframe:
                for r_it in resolved_from_iframe:
                    if page_dur and r_it.get('duration') in ('', 'Ismeretlen', '--:--'):
                        r_it['duration'] = page_dur
                    if page_title and r_it.get('title', '').startswith(('Beágyazott_Videó', 'Közvetlen_Stream_')):
                        r_it['title'] = page_title
                        r_it['display_title'] = f"{prefix_tag} {page_title}".strip() if prefix_tag else page_title
                discovered.extend(resolved_from_iframe)
            else:
                try:
                    iframe_html, _ = fetch_url_text(iframe_url, referer=target_url)
                    if_title = extract_html_title(iframe_html, fallback=page_title)
                    sub_media = self._extract_media_from_text(
                        iframe_html, iframe_url, iframe_url, if_title,
                        prefix_tag=prefix_tag, base_priority=base_priority
                    )
                    if sub_media:
                        discovered.extend(sub_media)
                except Exception as e:
                    self.log_msg.emit(f"[SCRAPER] Iframe olvasási figyelmeztetés: {e}")

        if html and not discovered:
            discovered.extend(
                self._extract_media_from_text(
                    html, target_url, target_url, page_title,
                    prefix_tag=prefix_tag, base_priority=base_priority + 2
                )
            )

        return discovered, page_title, html

    def run(self):
        try:
            self.log_msg.emit(f"[SCRAPER] 🕸️ Weboldal és Álcázott Stream Scraper {APP_RELEASE_TAG} indítása: {self.url}")
            all_discovered = []
            page_title = "Felfedezett_Videó"

            parsed = urllib.parse.urlparse(self.url)
            q_params = urllib.parse.parse_qs(parsed.query)
            has_redirect_param = any(k in q_params for k in ['em', 'embed', 'player', 'url', 'src', 'video', 'link'])

            if has_redirect_param and parsed.path and parsed.path != '/':
                clean_canonical_url = urllib.parse.urlunparse(
                    (parsed.scheme, parsed.netloc, parsed.path, '', '', '')
                )
                self.log_msg.emit(
                    f"[SCRAPER] 🔍 Beágyazott paraméter észlelve az URL-ben (?{parsed.query[:45]}...)!"
                )
                # 1. Directly decode Base64 or plain URL from query params (e.g. ?em=aHR0cHM6Ly9...)
                # so even if &t=... timestamp expired on the wrapper site, we directly extract the real embed!
                direct_param_urls = []
                for k in ['em', 'embed', 'player', 'url', 'src', 'video', 'link']:
                    for val in q_params.get(k, []):
                        val = val.strip()
                        if val.startswith(('http://', 'https://')):
                            direct_param_urls.append(val)
                        else:
                            try:
                                dec = base64.b64decode(val + "===").decode("utf-8", errors="ignore").strip()
                                if dec.startswith(('http://', 'https://')):
                                    direct_param_urls.append(dec)
                            except Exception:
                                pass

                param_items = []
                for d_url in direct_param_urls:
                    self.log_msg.emit(f"[SCRAPER] 🔓 1. Videó (közvetlenül az ?em= paraméterből dekódolva): {d_url}")
                    p_sub, p_title, _ = self._scan_single_page(
                        d_url, clean_canonical_url,
                        depth_label="?em= Dekódolt Videó", prefix_tag="🎯 [1. Videó (?em= link)]", base_priority=0
                    )
                    param_items.extend(p_sub)

                if not param_items:
                    p_sub, p_title, root_html = self._scan_single_page(
                        self.url, clean_canonical_url,
                        depth_label="?em= Fő Videó", prefix_tag="🎯 [1. Videó (?em= link)]", base_priority=0
                    )
                    param_items.extend(p_sub)
                else:
                    root_html = ""

                all_discovered.extend(param_items)

                self.log_msg.emit(
                    f"[SCRAPER] 📄 2. Videó (a háttéroldal saját videójának feloldása): {clean_canonical_url}"
                )
                canon_items, canon_title, canon_html = self._scan_single_page(
                    clean_canonical_url, clean_canonical_url,
                    depth_label="Háttéroldal Videó", prefix_tag="📄 [2. Videó (Háttéroldal)]", base_priority=1
                )
                if not root_html:
                    root_html = canon_html
                if param_items:
                    page_title = param_items[0].get('title', canon_title)
                elif canon_title:
                    page_title = canon_title
                all_discovered.extend(canon_items)
            else:
                root_items, page_title, root_html = self._scan_single_page(
                    self.url, self.url, "Főoldal", prefix_tag="", base_priority=0
                )
                all_discovered.extend(root_items)

            has_manifest = any(d['priority'] <= 3 for d in all_discovered)
            if not has_manifest and self.use_headless and not self._cancelled:
                dom_html = self._dump_dom_headless(self.url)
                if dom_html:
                    dom_title = extract_html_title(dom_html, fallback=page_title)
                    all_discovered.extend(self._extract_media_from_text(dom_html, self.url, self.url, dom_title))
                    dom_ifs, dom_refs = self._extract_iframes(dom_html, self.url)
                    for iframe_url in dom_ifs[:5]:
                        if self._cancelled:
                            break
                        res_if = resolve_disguised_embed(
                            iframe_url, parent_referer=self.url, extra_referers=dom_refs, log_fn=self.log_msg.emit
                        )
                        if res_if:
                            all_discovered.extend(res_if)

            if self.crawl_subpages and root_html and not self._cancelled:
                subpages = self._extract_candidate_video_subpages(root_html, self.url)
                self.log_msg.emit(
                    f"[SCRAPER] Mély aloldal-bejárás: {len(subpages)} db videó/epizód aloldal vizsgálata..."
                )
                for i, (sub_url, sub_anchor) in enumerate(subpages, 1):
                    if self._cancelled:
                        break
                    self.log_msg.emit(f"[SCRAPER] Aloldal ({i}/{len(subpages)}): {sub_anchor} ({sub_url})")
                    sub_items, _, _ = self._scan_single_page(
                        sub_url, self.url, f"Aloldal #{i}", prefix_tag=f"[Epizód #{i}]", base_priority=2
                    )
                    all_discovered.extend(sub_items)

            unique = {}
            for item in sorted(all_discovered, key=lambda x: x.get('priority', 9)):
                if item['url'] not in unique:
                    unique[item['url']] = item

            final_list = list(unique.values())
            if final_list:
                self.log_msg.emit(f"[SCRAPER] ✅ Összesen {len(final_list)} db videóstream kigyűjtve!")
                self.streams_found.emit(final_list, page_title)
            else:
                self.failed.emit(
                    "Nem található közvetlen .m3u8 / .mpd / .mp4 stream vagy feloldható lejátszó.\n"
                    "Tipp: Kapcsold be a Böngésző Sütiket (Firefox/Chrome) vagy a 'Mély aloldal-bejárás' opciót!"
                )
        except Exception as e:
            self.failed.emit(clean_ansi(str(e)))


class InfoFetchWorker(QThread):
    finished_ok = pyqtSignal(dict, bytes)
    failed = pyqtSignal(str)
    log_msg = pyqtSignal(str)

    def __init__(self, url: str, allow_playlist: bool = False, referer: str = "", browser_cookies: str = ""):
        super().__init__()
        self.url = url
        self.allow_playlist = allow_playlist
        self.referer = referer
        self.browser_cookies = browser_cookies

    def _build_synthetic_info(self, resolved_items: list) -> dict:
        best = resolved_items[0]
        title = best.get('title', 'Videó')
        thumb = best.get('thumb_url', '')
        duration_str = best.get('duration', '')
        dur_sec = None
        if duration_str and duration_str not in ('--:--', 'Ismeretlen'):
            parts = [int(p) for p in duration_str.split(':') if p.isdigit()]
            if len(parts) == 2:
                dur_sec = parts[0] * 60 + parts[1]
            elif len(parts) == 3:
                dur_sec = parts[0] * 3600 + parts[1] * 60 + parts[2]

        formats = []
        for idx, it in enumerate(resolved_items):
            u = it.get('url', '')
            stype = it.get('type', '')
            height = None
            hm = re.search(r'(\d{3,4})p?', stype)
            if hm:
                height = int(hm.group(1))
            ext = 'mp4'
            proto = 'm3u8' if '.m3u8' in u.lower() else 'https'
            fmt_id = f"{height}p" if height else f"sáv_{idx+1}"
            formats.append({
                'format_id': fmt_id,
                'url': u,
                'ext': ext,
                'height': height,
                'resolution': f"{height}p" if height else 'Standard',
                'vcodec': 'h264',
                'acodec': 'aac',
                'protocol': proto,
                'http_headers': {'Referer': it.get('referer', self.url)}
            })

        return {
            'title': title,
            'id': best.get('video_group_id', 'stream'),
            'uploader': urllib.parse.urlparse(self.url).netloc,
            'webpage_url': self.url,
            'duration': dur_sec,
            'thumbnail': thumb,
            'formats': formats,
            '_is_synthetic': True,
            '_resolved_items': resolved_items,
        }

    def run(self):
        try:
            self.log_msg.emit(f"[INFO] Adatok lekérése: {self.url}")
            headers = {'User-Agent': DEFAULT_UA}
            if self.referer:
                headers['Referer'] = self.referer

            # Gyorsítósáv speciális videómegosztókhoz (ahol a natív yt-dlp 410 Gone vagy blokkolt)
            low = self.url.lower()
            if any(k in low for k in ['pornhub.', 'phncdn.', 'xvideos.', 'xnxx.', 'youporn.', 'redtube.', 'spankbang.']):
                self.log_msg.emit(f"[INFO] Speciális videómegosztó észlelve, közvetlen feloldó aktiválása...")
                direct_resolved = resolve_disguised_embed(self.url, parent_referer=self.referer, log_fn=self.log_msg.emit)
                if direct_resolved:
                    synth_info = self._build_synthetic_info(direct_resolved)
                    thumb_b = direct_resolved[0].get('thumb_bytes') or b""
                    ref_for_thumb = direct_resolved[0].get('referer') or self.referer or self.url
                    if not thumb_b and direct_resolved[0].get('thumb_url'):
                        thumb_b = fetch_thumbnail_bytes(direct_resolved[0]['thumb_url'], referer=ref_for_thumb)
                    self.finished_ok.emit(synth_info, thumb_b)
                    return

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'noplaylist': not self.allow_playlist,
                'extract_flat': 'in_playlist',
                'http_headers': headers,
            }
            if self.browser_cookies:
                ydl_opts['cookiesfrombrowser'] = (self.browser_cookies,)

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)

            if not info:
                self.failed.emit("Nem sikerült információt kinyerni a megadott URL-ből.")
                return

            thumb_bytes = b""
            thumb_url = info.get('thumbnail')
            if not thumb_url and info.get('thumbnails'):
                thumb_url = info['thumbnails'][-1].get('url')

            if thumb_url:
                thumb_bytes = fetch_thumbnail_bytes(thumb_url, referer=self.referer)

            self.finished_ok.emit(info, thumb_bytes)
        except Exception as e:
            err_str = clean_ansi(str(e))
            # Fallback: ha a yt-dlp elhasalt (410, 404, blokkolás), próbáljuk meg a resolve_disguised_embed-del
            try:
                self.log_msg.emit(f"[INFO] yt-dlp hiba ({err_str[:60]}), alternatív beágyazott feloldó indítása...")
                direct_resolved = resolve_disguised_embed(self.url, parent_referer=self.referer, log_fn=self.log_msg.emit)
                if direct_resolved:
                    synth_info = self._build_synthetic_info(direct_resolved)
                    thumb_b = direct_resolved[0].get('thumb_bytes') or b""
                    ref_for_thumb = direct_resolved[0].get('referer') or self.referer or self.url
                    if not thumb_b and direct_resolved[0].get('thumb_url'):
                        thumb_b = fetch_thumbnail_bytes(direct_resolved[0]['thumb_url'], referer=ref_for_thumb)
                    self.finished_ok.emit(synth_info, thumb_b)
                    return
            except Exception:
                pass
            self.failed.emit(err_str)


class DownloadWorker(QThread):
    progress_updated = pyqtSignal(float, str, str, str, str)
    log_msg = pyqtSignal(str)
    item_finished = pyqtSignal(bool, str, str, str)
    batch_finished = pyqtSignal(int, int)

    def __init__(self, queue_items: list, options: dict):
        super().__init__()
        self.queue_items = queue_items
        self.options = options
        self._cancelled = False
        self.last_filepath = ""
        self._current_idx = 1
        self._total_items = len(queue_items)

    def cancel(self):
        self._cancelled = True

    def _progress_hook(self, d: dict):
        if self._cancelled:
            raise yt_dlp.utils.DownloadCancelled("A felhasználó megszakította a letöltést.")

        status = d.get('status', '')
        filename = d.get('filename', '')
        if filename:
            self.last_filepath = filename

        prefix = f"[{self._current_idx}/{self._total_items}] " if self._total_items > 1 else ""

        if status == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            frag_idx = d.get('fragment_index')
            frag_cnt = d.get('fragment_count')

            if total > 0:
                pct = (downloaded / total) * 100.0
            elif frag_idx and frag_cnt and frag_cnt > 0:
                pct = (frag_idx / frag_cnt) * 100.0
            else:
                pct_str = clean_ansi(d.get('_percent_str', '0%')).replace('%', '').strip()
                try:
                    pct = float(pct_str)
                except ValueError:
                    pct = 0.0

            speed = clean_ansi(d.get('_speed_str', '') or format_bytes(d.get('speed')) + '/s')
            eta = clean_ansi(d.get('_eta_str', '') or '--:--')
            size_info = f"{format_bytes(downloaded)} / {format_bytes(total)}" if total else format_bytes(downloaded)

            if frag_idx and frag_cnt:
                stage_msg = f"{prefix}Darabolt stream — Töredék: {frag_idx} / {frag_cnt} ({pct:.1f}%)"
            else:
                stage_msg = f"{prefix}Letöltés folyamatban..."

            self.progress_updated.emit(pct, speed, eta, size_info, stage_msg)

        elif status == 'finished':
            self.progress_updated.emit(100.0, "-", "00:00", "-", f"{prefix}Töredékek összefűzése (FFmpeg)...")
            self.log_msg.emit(f"[OK] {prefix}Sáv/töredékek letöltve: {os.path.basename(filename)}")

    def _postprocessor_hook(self, d: dict):
        if self._cancelled:
            raise yt_dlp.utils.DownloadCancelled("A felhasználó megszakította a letöltést.")
        status = d.get('status', '')
        pp = d.get('postprocessor', 'FFmpeg')
        info_dict = d.get('info_dict', {})
        filepath = info_dict.get('filepath') or info_dict.get('_filename')
        if filepath:
            self.last_filepath = filepath
        prefix = f"[{self._current_idx}/{self._total_items}] " if self._total_items > 1 else ""
        if status == 'started':
            self.progress_updated.emit(100.0, "-", "-", "-", f"{prefix}Összefűzés / konvertálás ({pp})...")

    def _ffmpeg_direct_fallback(self, stream_url: str, out_dir: str, container: str, referer: str, title_hint: str) -> str:
        safe_name = re.sub(r'[^\w\-_\. ]', '_', title_hint or "Stream_Video").strip()[:95]
        ext = container if container in ('mp4', 'mkv', 'webm', 'mp3', 'm4a') else 'mp4'
        out_file = os.path.join(out_dir, f"{safe_name}.{ext}")
        if os.path.exists(out_file):
            safe_ts = datetime.now().strftime("%H%M%S")
            out_file = os.path.join(out_dir, f"{safe_name}_{safe_ts}.{ext}")

        # 1. Check first if the HLS segments have fake PNG/GIF/BMP/JPEG headers (e.g. 1x1 PNG on TikTok CDN)
        # Because standard FFmpeg gets tricked into muxing a 4-second 1x1 PNG video without returning an error!
        if extreme_resolvers.probe_hls_needs_header_strip(stream_url, referer=referer):
            self.log_msg.emit(
                "[EXTREME-HLS] 🛡️ Álcázott képfejléces (1x1 PNG / TikTok-CDN -> 0x47 MPEG-TS) szegmensek észlelve! "
                "N_m3u8DL-RE fejléc-tisztító indítása..."
            )
            return extreme_resolvers.download_disguised_hls_with_header_strip(
                stream_url, out_file, referer=referer,
                max_workers=int(self.options.get('concurrent_fragments', 8)),
                progress_cb=lambda pct, spd, eta, sz, stg: self.progress_updated.emit(pct, spd, eta, sz, stg),
                log_fn=self.log_msg.emit,
                cancel_check_fn=lambda: self._cancelled
            )

        headers_str = f"User-Agent: {DEFAULT_UA}\r\n"
        if referer:
            headers_str += f"Referer: {referer}\r\n"
            parsed = urllib.parse.urlparse(referer)
            if parsed.scheme and parsed.netloc:
                headers_str += f"Origin: {parsed.scheme}://{parsed.netloc}\r\n"

        cmd = [
            "ffmpeg", "-y",
            "-headers", headers_str,
            "-allowed_extensions", "ALL",
            "-protocol_whitelist", "file,http,https,tcp,tls,crypto,data",
            "-i", stream_url
        ]
        if ext in ('mp3', 'm4a'):
            cmd += ["-vn", "-acodec", "libmp3lame" if ext == "mp3" else "aac", out_file]
        else:
            cmd += ["-c", "copy", "-bsf:a", "aac_adtstoasc", out_file]

        self.log_msg.emit(f"[FFMPEG-DIRECT] Álcázott/darabolt stream összefűzése: {out_file}")
        self.progress_updated.emit(50.0, "FFmpeg Stream", "--:--", "Folyamatos", "FFmpeg közvetlen HLS/DASH összefűzés...")

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0 and os.path.exists(out_file):
            return out_file

        # N_m3u8DL-RE ImageHeaderUtil fallback: if FFmpeg failed, strip fake headers and remux
        self.log_msg.emit("[EXTREME-HLS] FFmpeg hiba után N_m3u8DL-RE képfejléc-tisztító (PNG/GIF/BMP/JPG -> 0x47 TS) indítása...")
        return extreme_resolvers.download_disguised_hls_with_header_strip(
            stream_url, out_file, referer=referer,
            max_workers=int(self.options.get('concurrent_fragments', 8)),
            progress_cb=lambda pct, spd, eta, sz, stg: self.progress_updated.emit(pct, spd, eta, sz, stg),
            log_fn=self.log_msg.emit,
            cancel_check_fn=lambda: self._cancelled
        )

    def _download_single(self, item: dict) -> tuple:
        url = item['url']
        referer = item.get('referer') or self.options.get('referer', '').strip()
        title_hint = item.get('title_hint', '').strip()
        embed_source = item.get('embed_source', '').strip()
        embed_parent_ref = item.get('embed_parent_ref', '').strip()
        backup_urls = []

        if embed_source:
            self.log_msg.emit(f"[FRISSÍTÉS] Dinamikus stream-token frissítése innen: {embed_source}")
            fresh_list = resolve_disguised_embed(
                embed_source, parent_referer=embed_parent_ref or referer, log_fn=self.log_msg.emit
            )
            if fresh_list:
                best_fresh = fresh_list[0]
                url = best_fresh['url']
                referer = best_fresh.get('referer') or embed_source
                if not title_hint:
                    title_hint = best_fresh.get('title', '')
                backup_urls = [f['url'] for f in fresh_list[1:] if f.get('url')]

        out_dir = self.options['output_dir']
        os.makedirs(out_dir, exist_ok=True)

        mode = self.options['mode']
        quality = self.options['quality']
        container = self.options['container']
        custom_fmt = self.options.get('custom_format_id')
        browser_cookies = self.options.get('browser_cookies', '').strip()
        concurrent_frags = int(self.options.get('concurrent_fragments', 8))

        # 0. Check upfront if this is a direct binary MP4/WebM stream (e.g. store*.gofile.io/download/direct/...)
        low_url = url.lower()
        if (
            item.get('is_direct_binary')
            or "gofile.io" in low_url
            or "/download/direct/" in low_url
        ) and mode != 'audio_only':
            safe_name = re.sub(r'[^\w\-_\. ]', '_', title_hint or "Direct_Video").strip()[:95]
            ext = container if container in ('mp4', 'mkv', 'webm') else 'mp4'
            out_file = os.path.join(out_dir, f"{safe_name}.{ext}")
            if os.path.exists(out_file):
                safe_ts = datetime.now().strftime("%H%M%S")
                out_file = os.path.join(out_dir, f"{safe_name}_{safe_ts}.{ext}")
            out_file = extreme_resolvers.download_direct_media_stream(
                url, out_file, referer=referer,
                progress_cb=lambda pct, spd, eta, sz, stg: self.progress_updated.emit(pct, spd, eta, sz, stg),
                log_fn=self.log_msg.emit,
                cancel_check_fn=lambda: self._cancelled
            )
            return True, title_hint or os.path.basename(out_file), out_file

        # Check upfront if this HLS stream uses disguised PNG/GIF/BMP/JPEG headers (like ghbrisk /stream/ TikTok CDN)
        # If we let yt-dlp/FFmpeg touch it directly, FFmpeg sees the 70-byte 1x1 PNG header and creates a 4s 1x1 dummy video!
        if any(x in low_url for x in ['.m3u8', '.m3u', '/stream/', 'master.txt']) and mode != 'audio_only':
            if extreme_resolvers.probe_hls_needs_header_strip(url, referer=referer):
                self.log_msg.emit(
                    f"[EXTREME-HLS] 🛡️ Képfejléccel (1x1 PNG) álcázott 1080p HLS szegmensek észlelve: {url[:75]}..."
                )
                out_file = self._ffmpeg_direct_fallback(url, out_dir, container, referer, title_hint or "Videó")
                return True, title_hint or os.path.basename(out_file), out_file

        headers = {'User-Agent': DEFAULT_UA}
        if referer:
            headers['Referer'] = referer
            parsed = urllib.parse.urlparse(referer)
            if parsed.scheme and parsed.netloc:
                headers['Origin'] = f"{parsed.scheme}://{parsed.netloc}"

        self.last_filepath = ""
        clean_title_prefix = re.sub(r'[^\w\-_\. ]', '_', title_hint).strip()[:110] if title_hint else "%(title).120B"
        outtmpl = (
            os.path.join(out_dir, f"{clean_title_prefix}.%(ext)s")
            if title_hint and not self.options.get('playlist', False)
            else os.path.join(out_dir, '%(title).140B.%(ext)s')
        )

        ydl_opts = {
            'outtmpl': outtmpl,
            'noplaylist': not self.options.get('playlist', False),
            'progress_hooks': [self._progress_hook],
            'postprocessor_hooks': [self._postprocessor_hook],
            'retries': 10,
            'fragment_retries': 10,
            'concurrent_fragment_downloads': concurrent_frags,
            'hls_use_mpegts': False,
            'http_headers': headers,
            'ignoreerrors': self.options.get('playlist', False),
        }

        if browser_cookies:
            ydl_opts['cookiesfrombrowser'] = (browser_cookies,)

        postprocessors = []
        if custom_fmt and self._total_items == 1:
            if mode == 'video_audio':
                ydl_opts['format'] = f"{custom_fmt}+bestaudio/best"
                ydl_opts['merge_output_format'] = container
            else:
                ydl_opts['format'] = custom_fmt
        else:
            if mode == 'audio_only':
                ydl_opts['format'] = 'bestaudio/best'
                postprocessors.append({
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': container,
                    'preferredquality': '320' if container == 'mp3' else '0',
                })
            elif mode == 'video_only':
                if quality == 'best':
                    ydl_opts['format'] = f"bestvideo[ext={container}]/bestvideo/best"
                else:
                    ydl_opts['format'] = f"bestvideo[height<={quality}][ext={container}]/bestvideo[height<={quality}]/best"
            else:
                if quality == 'best':
                    ydl_opts['format'] = 'bestvideo+bestaudio/best'
                else:
                    ydl_opts['format'] = f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best"
                ydl_opts['merge_output_format'] = container

        if self.options.get('subtitles'):
            ydl_opts['writesubtitles'] = True
            ydl_opts['writeautomaticsub'] = True
            ydl_opts['subtitleslangs'] = ['hu', 'en']
            if mode != 'audio_only':
                postprocessors.append({'key': 'FFmpegEmbedSubtitle'})

        if self.options.get('embed_thumbnail'):
            ydl_opts['writethumbnail'] = True
            postprocessors.append({'key': 'EmbedThumbnail'})

        if self.options.get('embed_metadata'):
            postprocessors.append({'key': 'FFmpegMetadata', 'add_metadata': True})

        if postprocessors:
            ydl_opts['postprocessors'] = postprocessors

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = title_hint or (info.get('title') if isinstance(info, dict) else None) or 'Videó'
                if isinstance(info, dict) and not self.last_filepath:
                    self.last_filepath = ydl.prepare_filename(info)
            return True, title, self.last_filepath or out_dir
        except yt_dlp.utils.DownloadCancelled:
            raise
        except Exception as e:
            err_str = clean_ansi(str(e))
            if not embed_source and (
                "Unsupported URL" in err_str or
                "HTTP Error 410" in err_str or
                "HTTP Error 404" in err_str or
                "HTTP Error 470" in err_str or
                "Unable to download webpage" in err_str or
                not any(ext in url.lower() for ext in ['.mp4', '.m3u8', '.mpd', '.webm', '.mkv'])
            ):
                self.log_msg.emit(f"[AUTO-FELOLDÓ] yt-dlp hiba ({err_str[:60]}), álcázott lejátszó feloldása: {url}")
                resolved = resolve_disguised_embed(url, parent_referer=referer, log_fn=self.log_msg.emit)
                if resolved:
                    best = resolved[0]
                    if custom_fmt:
                        for r_it in resolved:
                            if custom_fmt.lower() in r_it.get('type', '').lower() or custom_fmt in r_it.get('label', ''):
                                best = r_it
                                break
                    item_retry = {
                        'url': best['url'],
                        'referer': best.get('referer', url),
                        'title_hint': title_hint or best.get('title', 'Videó'),
                        'embed_source': ''
                    }
                    return self._download_single(item_retry)

            if any(x in url.lower() for x in ['.m3u8', '.mpd', '.mp4', '.webm', '/stream/', 'master.txt']):
                for candidate_u in [url] + backup_urls:
                    try:
                        self.log_msg.emit(f"[FALLBACK] Közvetlen FFmpeg/HLS letöltő indítása: {candidate_u[:75]}...")
                        out_file = self._ffmpeg_direct_fallback(candidate_u, out_dir, container, referer, title_hint)
                        return True, title_hint or os.path.basename(out_file), out_file
                    except Exception as sub_e:
                        self.log_msg.emit(f"[FIGYELMEZTETÉS] Sáv sikertelen ({sub_e}), váltás tartalék sávra...")
            raise e

    def run(self):
        ok_count = 0
        fail_count = 0
        fmt_upper = self.options['container'].upper()

        for idx, item in enumerate(self.queue_items, 1):
            if self._cancelled:
                break
            self._current_idx = idx
            url = item['url']
            self.log_msg.emit(f"[LETÖLTÉS {idx}/{self._total_items}] Indítás: {url}")
            try:
                success, title, fpath = self._download_single(item)
                if success:
                    ok_count += 1
                    self.item_finished.emit(True, title, fmt_upper, fpath)
            except yt_dlp.utils.DownloadCancelled:
                self.log_msg.emit("[MEGSZAKÍTVA] A letöltést a felhasználó leállította.")
                break
            except Exception as e:
                fail_count += 1
                err_c = clean_ansi(str(e))
                self.log_msg.emit(f"[HIBA {idx}/{self._total_items}] {err_c}")
                self.item_finished.emit(False, f"Hiba: {err_c[:120]}", fmt_upper, url)

        self.batch_finished.emit(ok_count, fail_count)


class YouTubeDownloaderWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(
            f"YouTube & Univerzális Videóletöltő PRO {APP_RELEASE_TAG} (Kiadás: {APP_VERSION} | yt-dlp {yt_dlp.version.__version__})"
        )
        self.resize(1120, 860)

        icon_path = self._find_icon()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        self.info_worker = None
        self.scanner_worker = None
        self.download_worker = None
        self.current_info = None
        self.scraped_items = []
        self._last_scraped_root_url = ""

        self.default_download_dir = self._get_default_download_dir()

        self._apply_dark_theme()
        self._build_ui()

    def _find_icon(self) -> str:
        candidates = [
            str(APP_LIB_DIR / "icon.png"),
            "/usr/share/pixmaps/youtube-downloader-gui.png",
            "/usr/share/icons/hicolor/256x256/apps/youtube-downloader-gui.png",
            "/data/youtube downloader/ytDownloader-main/resources/icon.png",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return ""

    def _get_default_download_dir(self) -> str:
        home = Path.home()
        for folder in ["Letöltések", "Downloads", "Videók", "Videos"]:
            candidate = home / folder
            if candidate.is_dir():
                return str(candidate)
        return str(home)

    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #11131a;
                color: #e5e7eb;
                font-family: 'Segoe UI', 'Noto Sans', 'DejaVu Sans', sans-serif;
                font-size: 13px;
            }
            QGroupBox {
                background-color: #181b24;
                border: 1px solid #282d3e;
                border-radius: 10px;
                margin-top: 10px;
                padding: 10px;
                font-weight: bold;
                color: #f3f4f6;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
                color: #60a5fa;
            }
            QLineEdit, QComboBox, QSpinBox {
                background-color: #202431;
                border: 1px solid #32384d;
                border-radius: 7px;
                padding: 7px 11px;
                color: #f9fafb;
                selection-background-color: #3b82f6;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border: 1px solid #3b82f6;
            }
            QPushButton {
                background-color: #262b3c;
                border: 1px solid #374151;
                border-radius: 7px;
                padding: 8px 14px;
                font-weight: 600;
                color: #f3f4f6;
            }
            QPushButton:hover {
                background-color: #32394f;
                border-color: #4b5563;
            }
            QPushButton#primaryBtn {
                background-color: #e11d48;
                border: 1px solid #f43f5e;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
            }
            QPushButton#primaryBtn:hover {
                background-color: #be123c;
            }
            QPushButton#primaryBtn:disabled {
                background-color: #4b232d;
                border-color: #4b232d;
                color: #9ca3af;
            }
            QPushButton#actionBtn {
                background-color: #2563eb;
                border: 1px solid #3b82f6;
                color: #ffffff;
            }
            QPushButton#actionBtn:hover {
                background-color: #1d4ed8;
            }
            QPushButton#hunterBtn {
                background-color: #7c3aed;
                border: 1px solid #8b5cf6;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton#hunterBtn:hover {
                background-color: #6d28d9;
            }
            QProgressBar {
                background-color: #1f2433;
                border: 1px solid #32384d;
                border-radius: 8px;
                text-align: center;
                height: 24px;
                font-weight: bold;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 #2563eb, stop:0.5 #7c3aed, stop:1 #e11d48);
                border-radius: 7px;
            }
            QTabWidget::pane {
                border: 1px solid #282d3e;
                border-radius: 8px;
                background-color: #181b24;
            }
            QTabBar::tab {
                background-color: #181b24;
                border: 1px solid #282d3e;
                padding: 8px 16px;
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                margin-right: 4px;
                color: #9ca3af;
            }
            QTabBar::tab:selected {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: bold;
            }
            QTableWidget, QTextEdit {
                background-color: #141720;
                border: 1px solid #282d3e;
                border-radius: 6px;
                color: #d1d5db;
                gridline-color: #282d3e;
            }
            QHeaderView::section {
                background-color: #202431;
                color: #93c5fd;
                padding: 6px;
                border: 1px solid #282d3e;
                font-weight: bold;
            }
            QCheckBox {
                spacing: 8px;
            }
        """)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(10)

        header_frame = QFrame()
        header_frame.setStyleSheet(
            "background-color: #181b24; border: 1px solid #282d3e; border-radius: 10px; padding: 6px 10px;"
        )
        header_layout = QHBoxLayout(header_frame)
        title_lbl = QLabel(f"🕸️ YouTube & Univerzális Videóletöltő PRO {APP_RELEASE_TAG}")
        title_lbl.setStyleSheet("font-size: 17px; font-weight: bold; color: #f8fafc; border: none;")
        ver_lbl = QLabel(
            f"Kiadás: {APP_VERSION}  |  Borítóképes Előnézet  |  Pornhub, XVideos, GoFile, StreamHG, DoodStream"
        )
        ver_lbl.setStyleSheet("font-size: 12px; color: #a78bfa; border: none;")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        header_layout.addWidget(ver_lbl)
        main_layout.addWidget(header_frame)

        # 1. URL & Scraper Input Bar
        url_group = QGroupBox("1. Céloldal / Videó URL & Álcázott Stream Scraper")
        url_vbox = QVBoxLayout(url_group)

        url_row1 = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "Illeszd be bármely videóoldal (YouTube, xleak, DoodStream, Playmogo, Ghbrisk, StreamHG, stb.) linkjét..."
        )
        self.url_input.returnPressed.connect(self.start_deep_stream_hunt)

        self.paste_btn = QPushButton("📋 Beillesztés")
        self.paste_btn.clicked.connect(self.paste_from_clipboard)

        self.fetch_btn = QPushButton("🔍 Normál Elemzés")
        self.fetch_btn.setObjectName("actionBtn")
        self.fetch_btn.clicked.connect(self.fetch_video_info)

        self.hunter_btn = QPushButton("🕸️ Oldal Lekaparása & Videó Kiválasztása")
        self.hunter_btn.setObjectName("hunterBtn")
        self.hunter_btn.clicked.connect(self.start_deep_stream_hunt)

        url_row1.addWidget(self.url_input, 1)
        url_row1.addWidget(self.paste_btn)
        url_row1.addWidget(self.fetch_btn)
        url_row1.addWidget(self.hunter_btn)
        url_vbox.addLayout(url_row1)

        hunter_row = QHBoxLayout()
        hunter_row.addWidget(QLabel("🎯 Kiválasztott stream:"))
        self.discovered_combo = QComboBox()
        self.discovered_combo.addItem("Eredeti főoldal URL használata", None)
        self.discovered_combo.currentIndexChanged.connect(self._on_discovered_stream_selected)
        hunter_row.addWidget(self.discovered_combo, 2)

        self.choose_dialog_btn = QPushButton("🎬 Videóválasztó ablak megnyitása")
        self.choose_dialog_btn.clicked.connect(self._reopen_video_selector_dialog)
        self.choose_dialog_btn.setEnabled(False)
        hunter_row.addWidget(self.choose_dialog_btn)

        self.chk_crawl_subpages = QCheckBox("Mély aloldal-bejárás")
        hunter_row.addWidget(self.chk_crawl_subpages)

        hunter_row.addWidget(QLabel("🍪 Sütik:"))
        self.cookie_combo = QComboBox()
        self.cookie_combo.addItem("Nincs", "")
        self.cookie_combo.addItem("Firefox", "firefox")
        self.cookie_combo.addItem("Chrome", "chrome")
        self.cookie_combo.addItem("Chromium", "chromium")
        self.cookie_combo.addItem("Brave", "brave")
        hunter_row.addWidget(self.cookie_combo)

        hunter_row.addWidget(QLabel("🔗 Referer:"))
        self.referer_input = QLineEdit()
        self.referer_input.setPlaceholderText("Automatikus")
        self.referer_input.setMaximumWidth(150)
        hunter_row.addWidget(self.referer_input)

        url_vbox.addLayout(hunter_row)
        main_layout.addWidget(url_group)

        # Middle section: Preview Card + Download Settings
        mid_layout = QHBoxLayout()

        preview_group = QGroupBox("Kiválasztott Videó Előnézete")
        preview_layout = QVBoxLayout(preview_group)
        self.thumb_label = QLabel(
            "Nincs betöltött előnézet\n\n"
            "Illeszd be a linket és kattints az\n"
            "'🕸️ Oldal Lekaparása & Videó Kiválasztása' gombra!\n"
            "Ha több videó van az oldalon, borítóképes\n"
            "választóablakban döntheted el, melyiket töltse le!"
        )
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setMinimumSize(300, 165)
        self.thumb_label.setMaximumSize(340, 185)
        self.thumb_label.setStyleSheet(
            "background-color: #101218; border: 1px dashed #374151; border-radius: 8px; color: #9ca3af; padding: 8px;"
        )

        self.video_title_lbl = QLabel("Cím: -")
        self.video_title_lbl.setWordWrap(True)
        self.video_title_lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #f3f4f6;")

        self.video_meta_lbl = QLabel("Forrás: -  |  Hossz: --:--")
        self.video_meta_lbl.setStyleSheet("color: #9ca3af; font-size: 12px;")

        preview_layout.addWidget(self.thumb_label, alignment=Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.video_title_lbl)
        preview_layout.addWidget(self.video_meta_lbl)
        preview_layout.addStretch()
        mid_layout.addWidget(preview_group, 2)

        # Right: Format & Fragment Settings
        settings_group = QGroupBox("2. Letöltési, Formátum és Töredék-Összefűzési Beállítások")
        settings_grid = QGridLayout(settings_group)
        settings_grid.setVerticalSpacing(8)
        settings_grid.setHorizontalSpacing(12)

        settings_grid.addWidget(QLabel("Letöltés típusa:"), 0, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("🎬 Videó + Hang (Összefűzött teljes videó)", "video_audio")
        self.mode_combo.addItem("🎵 Csak Hang (MP3 / Audio konvertálás)", "audio_only")
        self.mode_combo.addItem("🔇 Csak Videó (néma videósáv)", "video_only")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        settings_grid.addWidget(self.mode_combo, 0, 1, 1, 2)

        settings_grid.addWidget(QLabel("Felbontás / Minőség:"), 1, 0)
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("⭐ Legjobb elérhető minőség (Auto)", "best")
        self.quality_combo.addItem("4K Ultra HD (2160p)", "2160")
        self.quality_combo.addItem("2K QHD (1440p)", "1440")
        self.quality_combo.addItem("Full HD (1080p)", "1080")
        self.quality_combo.addItem("HD (720p)", "720")
        self.quality_combo.addItem("SD (480p)", "480")
        self.quality_combo.addItem("Kis méret (360p)", "360")
        settings_grid.addWidget(self.quality_combo, 1, 1)

        frag_box = QHBoxLayout()
        frag_box.addWidget(QLabel("⚡ Töredék szálak:"))
        self.frag_combo = QComboBox()
        self.frag_combo.addItem("8x párhuzamos (Ajánlott)", 8)
        self.frag_combo.addItem("16x párhuzamos (Turbó .m3u8/.ts)", 16)
        self.frag_combo.addItem("4x párhuzamos", 4)
        self.frag_combo.addItem("1x szekvenciális", 1)
        frag_box.addWidget(self.frag_combo)
        settings_grid.addLayout(frag_box, 1, 2)

        settings_grid.addWidget(QLabel("Kimeneti formátum:"), 2, 0)
        self.container_combo = QComboBox()
        self._populate_containers("video_audio")
        settings_grid.addWidget(self.container_combo, 2, 1, 1, 2)

        settings_grid.addWidget(QLabel("Specifikus sáv:"), 3, 0)
        self.stream_combo = QComboBox()
        self.stream_combo.addItem("Automatikus kiválasztás a fenti beállítások alapján", "")
        settings_grid.addWidget(self.stream_combo, 3, 1, 1, 2)

        opts_layout = QHBoxLayout()
        self.chk_playlist = QCheckBox("Lejátszási lista")
        self.chk_subs = QCheckBox("Feliratok (HU/EN)")
        self.chk_thumb = QCheckBox("Borítókép beágyazás")
        self.chk_meta = QCheckBox("Metaadatok")
        self.chk_meta.setChecked(True)
        self.chk_headless = QCheckBox("Headless JS DOM")
        self.chk_headless.setChecked(True)

        opts_layout.addWidget(self.chk_playlist)
        opts_layout.addWidget(self.chk_subs)
        opts_layout.addWidget(self.chk_thumb)
        opts_layout.addWidget(self.chk_meta)
        opts_layout.addWidget(self.chk_headless)
        settings_grid.addLayout(opts_layout, 4, 0, 1, 3)

        settings_grid.addWidget(QLabel("Mentés helye:"), 5, 0)
        self.dir_input = QLineEdit(self.default_download_dir)
        self.browse_btn = QPushButton("📁 Tallózás")
        self.browse_btn.clicked.connect(self.choose_directory)
        self.open_dir_btn = QPushButton("📂 Mappa")
        self.open_dir_btn.clicked.connect(self.open_output_directory)

        dir_btn_layout = QHBoxLayout()
        dir_btn_layout.addWidget(self.browse_btn)
        dir_btn_layout.addWidget(self.open_dir_btn)

        settings_grid.addWidget(self.dir_input, 5, 1)
        settings_grid.addLayout(dir_btn_layout, 5, 2)

        mid_layout.addWidget(settings_group, 3)
        main_layout.addLayout(mid_layout)

        # Progress and Action Controls
        prog_group = QGroupBox("3. Töredék-Letöltés, Összefűzés Állapota és Vezérlés")
        prog_layout = QVBoxLayout(prog_group)

        status_row = QHBoxLayout()
        self.status_lbl = QLabel("Állapot: Készenlétben")
        self.status_lbl.setStyleSheet("font-weight: bold; color: #93c5fd;")
        self.stats_lbl = QLabel("Sebesség: -  |  Hátralévő idő: -  |  Méret: -")
        self.stats_lbl.setStyleSheet("color: #9ca3af;")
        status_row.addWidget(self.status_lbl)
        status_row.addStretch()
        status_row.addWidget(self.stats_lbl)
        prog_layout.addLayout(status_row)

        ctrl_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.download_btn = QPushButton("⬇️ Kiválasztott Videó Letöltése")
        self.download_btn.setObjectName("primaryBtn")
        self.download_btn.clicked.connect(self.start_download)

        self.batch_btn = QPushButton("📦 Pipált Scraper-Találatok Csoportos Letöltése")
        self.batch_btn.setObjectName("hunterBtn")
        self.batch_btn.clicked.connect(self.start_batch_scraped_download)

        self.cancel_btn = QPushButton("✖ Megszakítás")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_download)

        ctrl_row.addWidget(self.progress_bar, 1)
        ctrl_row.addWidget(self.download_btn)
        ctrl_row.addWidget(self.batch_btn)
        ctrl_row.addWidget(self.cancel_btn)
        prog_layout.addLayout(ctrl_row)
        main_layout.addWidget(prog_group)

        # Bottom Tabs
        self.tabs = QTabWidget()

        scraper_tab = QWidget()
        scraper_vbox = QVBoxLayout(scraper_tab)
        scraper_vbox.setContentsMargins(6, 6, 6, 6)

        sel_bar = QHBoxLayout()
        btn_open_visual = QPushButton("🎬 Vizuális (Borítóképes) Videóválasztó Ablak Megnyitása")
        btn_open_visual.setObjectName("actionBtn")
        btn_open_visual.clicked.connect(self._reopen_video_selector_dialog)
        btn_sel_all = QPushButton("☑️ Összes kijelölése")
        btn_sel_all.clicked.connect(lambda: self._set_scraper_checks(all_items=True))
        btn_sel_none = QPushButton("☐ Kijelölés törlése")
        btn_sel_none.clicked.connect(lambda: self._set_scraper_checks(all_items=False))
        sel_bar.addWidget(btn_open_visual)
        sel_bar.addWidget(btn_sel_all)
        sel_bar.addWidget(btn_sel_none)
        sel_bar.addStretch()
        scraper_vbox.addLayout(sel_bar)

        self.scraper_table = QTableWidget(0, 4)
        self.scraper_table.setHorizontalHeaderLabels(["Kijelölve / Videó Címe", "Stream Típusa", "Hossz / Forrás", "Feloldott Stream URL"])
        self.scraper_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.scraper_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.scraper_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.scraper_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.scraper_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.scraper_table.cellClicked.connect(self._on_scraper_row_clicked)
        scraper_vbox.addWidget(self.scraper_table)

        self.history_table = QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels(["Időpont", "Cím / Eredmény", "Formátum", "Elérési út"])
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.cellDoubleClicked.connect(self._open_history_item)

        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setFont(QFont("Monospace", 10))

        self.tabs.addTab(scraper_tab, "🕸️ Scraper Találatok (Kattints egy sorra az előnézethez!)")
        self.tabs.addTab(self.history_table, "📜 Letöltési Előzmények (dupla kattintás = megnyitás)")
        self.tabs.addTab(self.log_console, "🖥 Részletes Napló (Scraper, Feloldó, yt-dlp & FFmpeg)")
        main_layout.addWidget(self.tabs, 1)

        self.append_log(
            f"PRO {APP_RELEASE_TAG} (Kiadás: {APP_VERSION}) elindult: Borítóképes előnézet, Vizuális Videóválasztó és Univerzális Feloldók aktívak!"
        )

    def _populate_containers(self, mode: str):
        self.container_combo.clear()
        if mode == "audio_only":
            self.container_combo.addItem("MP3 (320 kbps - univerzális)", "mp3")
            self.container_combo.addItem("M4A (AAC - kiváló minőség)", "m4a")
            self.container_combo.addItem("OPUS (legjobb tömörítés)", "opus")
            self.container_combo.addItem("FLAC (veszteségmentes)", "flac")
            self.container_combo.addItem("WAV (tömörítetlen PCM)", "wav")
        else:
            self.container_combo.addItem("MP4 (Összefűzött H.264/MP4 - ajánlott darabolt streamekhez)", "mp4")
            self.container_combo.addItem("MKV (Matroska - bármilyen kodekhez)", "mkv")
            self.container_combo.addItem("WEBM (VP9 / AV1)", "webm")

    def _on_mode_changed(self):
        mode = self.mode_combo.currentData()
        self.quality_combo.setEnabled(mode != "audio_only")
        self._populate_containers(mode)

    def append_log(self, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_console.append(f"[{ts}] {text}")

    def paste_from_clipboard(self):
        cb = QApplication.clipboard()
        text = cb.text().strip()
        if text:
            self.url_input.setText(text)
            self.discovered_combo.clear()
            self.discovered_combo.addItem("Eredeti főoldal URL használata", None)
            self.start_deep_stream_hunt()

    def choose_directory(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Mentési mappa kiválasztása", self.dir_input.text()
        )
        if folder:
            self.dir_input.setText(folder)

    def open_output_directory(self):
        folder = self.dir_input.text().strip()
        if os.path.isdir(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        else:
            QMessageBox.warning(self, "Mappa nem található", f"A megadott mappa még nem létezik:\n{folder}")

    def _update_preview_from_item(self, data: dict):
        if not isinstance(data, dict):
            return
        ref = data.get('referer', '')
        if ref:
            self.referer_input.setText(ref)
        self.video_title_lbl.setText(f"🎯 {data.get('display_title') or data.get('title', 'Videó')}")
        self.video_meta_lbl.setText(
            f"Hossz: {data.get('duration', '--:--')}  |  {data.get('type', '')}"
        )
        t_bytes = data.get('thumb_bytes', b'')
        if not t_bytes and data.get('thumb_url'):
            ref_for_thumb = ref or self.referer_input.text().strip() or self.url_input.text().strip()
            t_bytes = fetch_thumbnail_bytes(data['thumb_url'], referer=ref_for_thumb)
            if t_bytes:
                data['thumb_bytes'] = t_bytes
        if not t_bytes and getattr(self, 'current_thumb_bytes', None):
            t_bytes = self.current_thumb_bytes

        if t_bytes:
            pix = QPixmap()
            if pix.loadFromData(t_bytes):
                w = max(self.thumb_label.width(), 320)
                h = max(self.thumb_label.height(), 180)
                self.thumb_label.setPixmap(
                    pix.scaled(
                        w, h,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                )
                return
        self.thumb_label.setText(
            f"✅ Kiválasztva:\n{data.get('title', '')[:55]}\n\n({data.get('type', '')})"
        )

    def _on_discovered_stream_selected(self):
        data = self.discovered_combo.currentData()
        if isinstance(data, dict):
            self._update_preview_from_item(data)
            self.status_lbl.setText(f"Állapot: Kiválasztva -> {data.get('title', '')[:55]}")

    def _on_scraper_row_clicked(self, row: int, _col: int):
        it = self.scraper_table.item(row, 0)
        if it:
            data = it.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, dict):
                self._update_preview_from_item(data)
                # Also sync combo box
                for i in range(self.discovered_combo.count()):
                    cdata = self.discovered_combo.itemData(i)
                    if isinstance(cdata, dict) and cdata.get('url') == data.get('url'):
                        self.discovered_combo.setCurrentIndex(i)
                        break

    def _set_scraper_checks(self, all_items: bool):
        state = CHECKED_STATE if all_items else UNCHECKED_STATE
        for r in range(self.scraper_table.rowCount()):
            it = self.scraper_table.item(r, 0)
            if it:
                it.setCheckState(state)

    def _get_distinct_primary_videos(self, streams: list) -> list:
        """Kiszűri az eltérő videókat (hogy a tartalék hls4 sáv ne duplázza ugyanazt a videót a választóban)."""
        primary = []
        seen_groups = set()
        for s in streams:
            if s.get('is_backup_stream'):
                continue
            grp = s.get('video_group_id') or s.get('title') or s.get('url')
            if grp not in seen_groups:
                seen_groups.add(grp)
                primary.append(s)
        return primary

    def _reopen_video_selector_dialog(self):
        primary = self._get_distinct_primary_videos(self.scraped_items)
        if not primary:
            QMessageBox.information(self, "Nincs betöltött lista", "Először kattints az '🕸️ Oldal Lekaparása' gombra!")
            return
        self._show_video_selector(primary)

    def _show_video_selector(self, primary_candidates: list):
        dlg = VideoSelectorDialog(primary_candidates, self)
        if dlg.exec():
            if dlg.download_all:
                # Check all primary candidates in scraper table and start batch download
                primary_urls = {c['url'] for c in primary_candidates}
                for r in range(self.scraper_table.rowCount()):
                    it = self.scraper_table.item(r, 0)
                    if it:
                        d = it.data(Qt.ItemDataRole.UserRole) or {}
                        it.setCheckState(CHECKED_STATE if d.get('url') in primary_urls else UNCHECKED_STATE)
                self.start_batch_scraped_download()
            elif dlg.selected_item:
                chosen = dlg.selected_item
                # Select chosen in combo and table
                for i in range(self.discovered_combo.count()):
                    cdata = self.discovered_combo.itemData(i)
                    if isinstance(cdata, dict) and cdata.get('url') == chosen.get('url'):
                        self.discovered_combo.setCurrentIndex(i)
                        break
                for r in range(self.scraper_table.rowCount()):
                    it = self.scraper_table.item(r, 0)
                    if it:
                        d = it.data(Qt.ItemDataRole.UserRole) or {}
                        it.setCheckState(CHECKED_STATE if d.get('url') == chosen.get('url') else UNCHECKED_STATE)
                self._update_preview_from_item(chosen)
                if dlg.download_immediately:
                    self.start_download()

    def start_deep_stream_hunt(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Hiányzó URL", "Kérlek adj meg egy weboldal URL-t a Scraper indításához!")
            return

        if self.scanner_worker and self.scanner_worker.isRunning():
            return

        self.hunter_btn.setEnabled(False)
        self.status_lbl.setText("Állapot: 🕸️ Scraper fut (Összes lehetséges videó és borítókép kinyerése)...")
        self.tabs.setCurrentIndex(2)

        self.scanner_worker = DeepStreamScannerWorker(
            url,
            browser_cookies=self.cookie_combo.currentData(),
            use_headless=self.chk_headless.isChecked(),
            crawl_subpages=self.chk_crawl_subpages.isChecked()
        )
        self.scanner_worker.log_msg.connect(self.append_log)
        self.scanner_worker.streams_found.connect(self._on_streams_found)
        self.scanner_worker.failed.connect(self._on_stream_hunt_failed)
        self.scanner_worker.start()

    def _on_streams_found(self, streams: list, page_title: str):
        self.hunter_btn.setEnabled(True)
        self.scraped_items = streams
        self._last_scraped_root_url = self.url_input.text().strip()
        self.choose_dialog_btn.setEnabled(len(streams) > 0)

        self.discovered_combo.clear()
        self.discovered_combo.addItem("Eredeti főoldal URL használata", None)

        self.scraper_table.setRowCount(0)
        for idx, s in enumerate(streams):
            self.discovered_combo.addItem(s['label'], s)

            row = self.scraper_table.rowCount()
            self.scraper_table.insertRow(row)

            chk_item = QTableWidgetItem(s.get('display_title') or s.get('title') or f"Stream #{idx + 1}")
            chk_item.setFlags(chk_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            chk_item.setCheckState(CHECKED_STATE if idx == 0 else UNCHECKED_STATE)
            chk_item.setData(Qt.ItemDataRole.UserRole, s)

            dur_origin = f"⏱ {s.get('duration', '--:--')} | {s.get('origin_desc', '')}"
            self.scraper_table.setItem(row, 0, chk_item)
            self.scraper_table.setItem(row, 1, QTableWidgetItem(s.get('type', '')))
            self.scraper_table.setItem(row, 2, QTableWidgetItem(dur_origin))
            self.scraper_table.setItem(row, 3, QTableWidgetItem(s.get('url', '')))

        self.tabs.setCurrentIndex(0)

        if len(streams) > 0:
            self.discovered_combo.setCurrentIndex(1)
            self._update_preview_from_item(streams[0])
            self.status_lbl.setText(f"Állapot: 🎯 {len(streams)} db stream feloldva!")

            # If multiple distinct videos were found on the page, automatically pop up the Visual Selector Dialog!
            primary_candidates = self._get_distinct_primary_videos(streams)
            if len(primary_candidates) >= 2:
                self.append_log(
                    f"[VÁLASZTÓ] {len(primary_candidates)} különböző videó található az oldalon — Vizuális Videóválasztó megnyitása!"
                )
                self._show_video_selector(primary_candidates)

    def _on_stream_hunt_failed(self, err: str):
        self.hunter_btn.setEnabled(True)
        self.status_lbl.setText("Állapot: Scraper befejeződött")
        self.append_log(f"[SCRAPER] {err}")
        QMessageBox.information(self, "Scraper eredmény", err)

    def _needs_smart_scraper_first(self, raw_url: str) -> bool:
        low = raw_url.lower()
        return any(k in low for k in [
            'em=', 'embed=', 'tickzoo.', 'xleak.', 'capistock.', 'ghbrisk.',
            'playmogo.', 'gofile.io', 'streamhg.', 'vidhide.', 'filemoon.', 'dood',
            'pornhub.', 'phncdn.', 'xvideos.', 'xnxx.', 'youporn.', 'redtube.', 'spankbang.'
        ])

    def fetch_video_info(self, target_override: str = "", referer_override: str = ""):
        raw_url = self.url_input.text().strip()
        disc = self.discovered_combo.currentData()
        if not target_override and not isinstance(disc, dict) and self._needs_smart_scraper_first(raw_url):
            self.append_log(
                "[OKOS-ELEMZÉS] Álcázott/beágyazott videóoldal észlelve — automatikus Scraper és Feloldó indítása..."
            )
            self.start_deep_stream_hunt()
            return

        url = target_override if isinstance(target_override, str) and target_override else self._get_effective_url()
        if not url:
            QMessageBox.warning(self, "Hiányzó URL", "Kérlek adj meg egy YouTube vagy videó URL-t!")
            return

        if self.info_worker and self.info_worker.isRunning():
            return

        referer = referer_override or self.referer_input.text().strip() or self.url_input.text().strip()

        self.fetch_btn.setEnabled(False)
        self.status_lbl.setText("Állapot: Videó és töredéksávok lekérése...")
        self.thumb_label.setText("Adatok és előnézet betöltése...")

        self.info_worker = InfoFetchWorker(
            url,
            allow_playlist=self.chk_playlist.isChecked(),
            referer=referer,
            browser_cookies=self.cookie_combo.currentData()
        )
        self.info_worker.log_msg.connect(self.append_log)
        self.info_worker.finished_ok.connect(self._on_info_fetched)
        self.info_worker.failed.connect(self._on_info_failed)
        self.info_worker.start()

    def _get_effective_url(self) -> str:
        disc = self.discovered_combo.currentData()
        if isinstance(disc, dict) and disc.get('url'):
            return disc['url']
        return self.url_input.text().strip()

    def _on_info_fetched(self, info: dict, thumb_bytes: bytes):
        self.fetch_btn.setEnabled(True)
        self.current_info = info

        title = info.get('title', 'Ismeretlen cím')
        uploader = info.get('uploader') or info.get('channel') or info.get('webpage_url_domain') or 'Stream'
        duration = format_duration(info.get('duration'))

        if info.get('_type') == 'playlist' or 'entries' in info:
            entries = list(info.get('entries') or [])
            self.video_title_lbl.setText(f"📑 Lista / Sorozat: {title}")
            self.video_meta_lbl.setText(f"Forrás: {uploader}  |  Videók száma: {len(entries)} db")
            self.chk_playlist.setChecked(True)
        else:
            self.video_title_lbl.setText(title)
            self.video_meta_lbl.setText(f"Forrás: {uploader}  |  Hossz: {duration}")

        self.current_thumb_bytes = thumb_bytes
        if thumb_bytes:
            pix = QPixmap()
            if pix.loadFromData(thumb_bytes):
                w = max(self.thumb_label.width(), 320)
                h = max(self.thumb_label.height(), 180)
                scaled = pix.scaled(
                    w, h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.thumb_label.setPixmap(scaled)
        else:
            self.thumb_label.setText(f"✅ Stream elemzés kész!\n\n{title[:60]}")

        self.stream_combo.clear()
        self.stream_combo.addItem("Automatikus kiválasztás a fenti beállítások alapján", "")
        formats = info.get('formats') or []
        for f in reversed(formats):
            fmt_id = f.get('format_id')
            ext = f.get('ext', '')
            proto = f.get('protocol', '')
            res = f.get('resolution') or (f"{f.get('height')}p" if f.get('height') else 'audio')
            vcodec = f.get('vcodec', 'none')
            acodec = f.get('acodec', 'none')
            fsize = format_bytes(f.get('filesize') or f.get('filesize_approx'))
            if vcodec != 'none' or acodec != 'none':
                kind = "Videó+Hang" if (vcodec != 'none' and acodec != 'none') else ("Videó" if vcodec != 'none' else "Hang")
                frag_tag = " [HLS/DASH Darabolt]" if any(p in proto for p in ['m3u8', 'dash']) else ""
                label = f"[{fmt_id}] {res} ({ext}){frag_tag} - {kind} - {fsize}"
                self.stream_combo.addItem(label, fmt_id)

        self.status_lbl.setText("Állapot: ✅ Videó és sávok elemzése kész. Készen áll a letöltésre!")
        self.append_log(f"[OK] Betöltve: {title} ({len(formats)} elérhető sáv)")

        if info.get('_is_synthetic') and info.get('_resolved_items'):
            self.discovered_combo.clear()
            self.discovered_combo.addItem("🌐 Eredeti oldal URL", "")
            for it in info['_resolved_items']:
                if thumb_bytes and not it.get('thumb_bytes'):
                    it['thumb_bytes'] = thumb_bytes
                self.discovered_combo.addItem(it['label'], it)
            if self.discovered_combo.count() > 1:
                self.discovered_combo.setCurrentIndex(1)

    def _on_info_failed(self, err: str):
        self.fetch_btn.setEnabled(True)
        self.status_lbl.setText("Állapot: Normál elemzés nem talált közvetlen videót — automatikus Scraper indítás...")
        self.append_log(f"[INFO-FIGYELMEZTETÉS] {err}")
        if self.discovered_combo.count() <= 1:
            self.append_log("[AUTO] Automatikus átváltás az 🕸️ Oldal Lekaparása & Videó Kiválasztása módra...")
            self.start_deep_stream_hunt()

    def _build_download_options(self) -> dict:
        referer = self.referer_input.text().strip() or self.url_input.text().strip()
        return {
            'output_dir': self.dir_input.text().strip() or self.default_download_dir,
            'mode': self.mode_combo.currentData(),
            'quality': self.quality_combo.currentData(),
            'container': self.container_combo.currentData(),
            'custom_format_id': self.stream_combo.currentData(),
            'playlist': self.chk_playlist.isChecked(),
            'subtitles': self.chk_subs.isChecked(),
            'embed_thumbnail': self.chk_thumb.isChecked(),
            'embed_metadata': self.chk_meta.isChecked(),
            'referer': referer,
            'browser_cookies': self.cookie_combo.currentData(),
            'concurrent_fragments': self.frag_combo.currentData(),
        }

    def start_download(self):
        raw_url = self.url_input.text().strip()
        target_url = self._get_effective_url()
        if not target_url:
            QMessageBox.warning(self, "Hiányzó URL", "Kérlek adj meg egy YouTube vagy videóoldal URL-t a letöltéshez!")
            return

        if self.download_worker and self.download_worker.isRunning():
            return

        # If user pasted a complex/redirected URL (like ?em=..., tickzoo, xleak, etc.) and hasn't scraped it yet,
        # run the scraper first so they can choose which video they want!
        disc = self.discovered_combo.currentData()
        if not isinstance(disc, dict) and self._needs_smart_scraper_first(raw_url) and self._last_scraped_root_url != raw_url:
            self.append_log("[OKOS-LETÖLTÉS] Többszörös/átirányított URL észlelve — videók felkutatása és választóablak megnyitása...")
            self.start_deep_stream_hunt()
            return

        options = self._build_download_options()
        if isinstance(disc, dict):
            queue = [{
                'url': disc['url'],
                'referer': disc.get('referer', options['referer']),
                'title_hint': disc.get('title', ''),
                'embed_source': disc.get('embed_source', ''),
                'embed_parent_ref': disc.get('embed_parent_ref', ''),
                'is_direct_binary': disc.get('is_direct_binary', False),
            }]
        else:
            queue = [{'url': target_url, 'referer': options['referer'], 'title_hint': ''}]
        self._launch_download_queue(queue, options)

    def start_batch_scraped_download(self):
        if self.download_worker and self.download_worker.isRunning():
            return

        queue = []
        for r in range(self.scraper_table.rowCount()):
            chk_item = self.scraper_table.item(r, 0)
            if chk_item and chk_item.checkState() == CHECKED_STATE:
                data = chk_item.data(Qt.ItemDataRole.UserRole)
                if isinstance(data, dict) and data.get('url'):
                    queue.append({
                        'url': data['url'],
                        'referer': data.get('referer', ''),
                        'title_hint': data.get('title', ''),
                        'embed_source': data.get('embed_source', ''),
                        'embed_parent_ref': data.get('embed_parent_ref', ''),
                        'is_direct_binary': data.get('is_direct_binary', False),
                    })

        if not queue:
            QMessageBox.warning(
                self, "Nincs kijelölt elem",
                "Először futtasd az '🕸️ Oldal Lekaparása' gombot, és pipálj ki legalább egy streamet a Scraper táblázatban!"
            )
            return

        options = self._build_download_options()
        self._launch_download_queue(queue, options)

    def _launch_download_queue(self, queue: list, options: dict):
        self.download_btn.setEnabled(False)
        self.batch_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_lbl.setText(f"Állapot: Letöltési sor indítása ({len(queue)} db elem)...")

        self.download_worker = DownloadWorker(queue, options)
        self.download_worker.progress_updated.connect(self._on_progress_updated)
        self.download_worker.log_msg.connect(self.append_log)
        self.download_worker.item_finished.connect(self._on_item_finished)
        self.download_worker.batch_finished.connect(self._on_batch_finished)
        self.download_worker.start()

    def cancel_download(self):
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.cancel()
            self.status_lbl.setText("Állapot: Megszakítás folyamatban...")

    def _on_progress_updated(self, pct: float, speed: str, eta: str, size_info: str, stage: str):
        self.progress_bar.setValue(int(max(0, min(100, pct))))
        self.status_lbl.setText(f"Állapot: {stage}")
        self.stats_lbl.setText(f"Sebesség: {speed}  |  Hátralévő idő: {eta}  |  Méret: {size_info}")

    def _on_item_finished(self, success: bool, title: str, fmt: str, filepath: str):
        if success:
            self.append_log(f"[SIKER] {title} -> {filepath}")
            self._add_history_row(f"✅ {title}", fmt, filepath)
        else:
            self._add_history_row(f"❌ {title}", fmt, filepath)

    def _on_batch_finished(self, ok_count: int, fail_count: int):
        self.download_btn.setEnabled(True)
        self.batch_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        if ok_count > 0:
            self.progress_bar.setValue(100)
            self.status_lbl.setText(f"Állapot: ✅ Kész! Sikeres: {ok_count} db, Hibás: {fail_count} db.")
            self.tabs.setCurrentIndex(1)
            QMessageBox.information(
                self, "Letöltés befejeződött",
                f"Sikeresen letöltve és összefűzve: {ok_count} db videó/hangfájl.\n"
                f"Hibás/kihagyott: {fail_count} db.\n\n"
                f"Mentési mappa: {self.dir_input.text()}"
            )
        else:
            self.status_lbl.setText("Állapot: ❌ A letöltés nem sikerült.")
            QMessageBox.warning(
                self, "Letöltés nem sikerült",
                "Nem sikerült letölteni a kiválasztott elemet. Nézd meg a Részletes Naplót, "
                "vagy használd az '🕸️ Oldal Lekaparása' gombot!"
            )

    def _add_history_row(self, title: str, fmt: str, path: str):
        row = self.history_table.rowCount()
        self.history_table.insertRow(row)
        self.history_table.setItem(row, 0, QTableWidgetItem(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.history_table.setItem(row, 1, QTableWidgetItem(title))
        self.history_table.setItem(row, 2, QTableWidgetItem(fmt))
        self.history_table.setItem(row, 3, QTableWidgetItem(path))

    def _open_history_item(self, row: int, _col: int):
        item = self.history_table.item(row, 3)
        if not item:
            return
        path = item.text()
        target = path if os.path.exists(path) else os.path.dirname(path)
        if os.path.exists(target):
            QDesktopServices.openUrl(QUrl.fromLocalFile(target))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("YouTube & Scraper Video Downloader PRO")
    win = YouTubeDownloaderWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
