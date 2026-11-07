#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extreme Disguised Video Resolvers & Deobfuscators (PRO v6.0)
Integrált megoldások a klónozott GitHub projektek alapján:
- Gujal00/ResolveURL (jsunpack, jsunhunt, unwise, unjuice, aadecode, jjdecode)
- mhdzumair/mediaflow-proxy (DoodStream, StreamHG, StreamWish, FileMoon AES-GCM,
  VOE LUT+ROT13, Mixdrop, Streamtape, Vidoza, Vidmoly, Uqload, Lulustream, Supervideo)
- nilaoda/N_m3u8DL-RE (ImageHeaderUtil: PNG/GIF/BMP/JPEG fejléccel álcázott
  MPEG-TS 0x47/188-bájtos szegmensek tisztítása)
"""

import re
import json
import time
import base64
import random
import string
import urllib.parse
import urllib.request

DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


# ==============================================================================
# 1. JAVASCRIPT DEOBFUSCATORS (ResolveURL integráció)
# ==============================================================================

def unpack_dean_edwards(source: str) -> str:
    """Kicsomagolja az eval(function(p,a,c,k,e,d)...) blokkokat (ResolveURL egymenetes algoritmus + \\' támogatás)."""
    unpacked_chunks = []
    pattern = re.compile(
        r"\}\s*\(\s*'((?:\\.|[^'\\])*)'\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*'((?:\\.|[^'\\])*)'\.split\('\|'\)",
        re.DOTALL
    )
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

    for match in pattern.finditer(source):
        payload, radix_s, count_s, symtab_s = match.groups()
        radix = int(radix_s)
        count = int(count_s)
        symtab = symtab_s.split('|')

        def _unbase(token: str, b: int) -> int:
            if 2 <= b <= 36:
                try:
                    return int(token, b)
                except ValueError:
                    return -1
            val = 0
            dict_map = {ch: idx for idx, ch in enumerate(alphabet[:max(b, 62)])}
            for idx, ch in enumerate(reversed(token)):
                if ch not in dict_map:
                    return -1
                val += (b ** idx) * dict_map[ch]
            return val

        def _lookup(m, b=radix, st=symtab, c=count):
            word = m.group(0)
            idx = _unbase(word, b)
            if 0 <= idx < c and idx < len(st) and st[idx]:
                return st[idx]
            return word

        result = re.sub(r"\b\w+\b", _lookup, payload, flags=re.ASCII)
        unpacked_chunks.append(result.replace(r"\'", "'").replace(r'\/', '/'))
    return "\n".join(unpacked_chunks)


def unhunt_js(source: str) -> str:
    """Kicsomagolja az eval(function(h,u,n,t,e,r)...) Hunter JS obfuszkációt (ResolveURL/jsunhunt)."""
    out = []
    pattern = re.compile(
        r'eval\(function\(h,u,n,t,e,r\).*?}\("([^"]+)",\d+,"([^"]+)",(\d+),(\d+),\d+\)\)',
        re.DOTALL
    )
    for m in pattern.finditer(source):
        h, n, t_s, e_s = m.groups()
        t = int(t_s)
        e = int(e_s)
        result = ""
        i = 0
        while i < len(h):
            s = ""
            while i < len(h) and h[i] != n[e]:
                s += h[i]
                i += 1
            for j in range(len(n)):
                s = s.replace(n[j], str(j))
            try:
                # Base e to base 10
                val = int(s, e) - t
                if 0 <= val < 0x110000:
                    result += chr(val)
            except Exception:
                pass
            i += 1
        if result:
            out.append(result)
    return "\n".join(out)


def unwise_js(source: str) -> str:
    """Kicsomagolja az eval(function(w,i,s,e)...) Wise JS obfuszkációt (ResolveURL/unwise)."""
    out = []
    pattern = re.compile(
        r"}\s*\(\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*\)",
        re.DOTALL
    )
    for m in pattern.finditer(source):
        w, i, s, _e = m.groups()
        v0 = v1 = v2 = 0
        va = []
        vb = []
        while True:
            if v0 < 5:
                vb.append(w[v0])
            elif v0 < len(w):
                va.append(w[v0])
            v0 += 1
            if v1 < 5:
                vb.append(i[v1])
            elif v1 < len(i):
                va.append(i[v1])
            v1 += 1
            if v2 < 5:
                vb.append(s[v2])
            elif v2 < len(s):
                va.append(s[v2])
            v2 += 1
            if len(w) + len(i) + len(s) + len(_e) == len(va) + len(vb) + len(_e):
                break
        v3 = "".join(va)
        v4 = "".join(vb)
        v1 = 0
        result = []
        for v0 in range(0, len(va), 2):
            v5 = -1
            if ord(v4[v1]) % 2:
                v5 = 1
            try:
                result.append(chr(int(v3[v0:v0 + 2], 36) - v5))
            except Exception:
                pass
            v1 += 1
            if v1 >= len(vb):
                v1 = 0
        decoded = "".join(result)
        if decoded:
            out.append(decoded)
    return "\n".join(out)


def unjuice_js(source: str) -> str:
    """Kicsomagolja a JuicyCodes.Run(...) obfuszkációt (ResolveURL/unjuice)."""
    if not re.search(r'JuicyCodes\.Run\(', source, re.IGNORECASE):
        return ""
    try:
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
        e = re.findall(r'JuicyCodes\.Run\(([^\)]+)', source, re.IGNORECASE)[0]
        e = re.sub(r'\"\s*\+\s*\"', '', e)
        e = re.sub(r'[^A-Za-z0-9+/=]', '', e)
        t = ""
        f = 0
        while f + 3 < len(e):
            s = alphabet.index(e[f])
            o = alphabet.index(e[f + 1])
            u = alphabet.index(e[f + 2])
            a = alphabet.index(e[f + 3])
            f += 4
            n = (s << 2) | (o >> 4)
            r = ((15 & o) << 4) | (u >> 2)
            i = ((3 & u) << 6) | a
            t += chr(n)
            if u != 64:
                t += chr(r)
            if a != 64:
                t += chr(i)
        unpacked = unpack_dean_edwards(t)
        return unpacked or t
    except Exception:
        return ""


def unjuice2_js(source: str) -> str:
    """Kicsomagolja a _juicycodes(...) szimbólumtáblás + ROT13 + Base64 + sózott obfuszkációt (ResolveURL/unjuice2)."""
    if not re.search(r'_juicycodes\(', source, re.IGNORECASE):
        return ""
    try:
        import codecs
        symbol_map = ["`", "%", "-", "+", "*", "$", "!", "_", "^", "="]
        raw_arg = re.findall(r'_juicycodes\(([^\)]+)', source, re.IGNORECASE)[0]
        cleaned_str = "".join(re.findall(r'["\']([^"\']+)["\']', raw_arg))
        if not cleaned_str:
            return ""
        ord_salt = "".join(str(ord(c) - 100) for c in cleaned_str[-3:])
        jscode = cleaned_str[:-3]
        pad = (len(jscode) + 3) % 4
        jscode = (jscode + "===")[:-pad] if pad else jscode
        jscode = jscode.replace("_", "+").replace("-", "/")
        b64_dec = base64.b64decode(jscode).decode("ascii", errors="ignore")
        rot_dec = codecs.decode(b64_dec, "rot13")
        ord_string = "".join(str(symbol_map.index(c)) for c in rot_dec if c in symbol_map)
        chunks = [ord_string[i:i + 4] for i in range(0, len(ord_string), 4)]
        out = "".join(chr(int(c) % 1000 - int(ord_salt)) for c in chunks if len(c) == 4)
        return unpack_dean_edwards(out) or out
    except Exception:
        return ""


def aadecode_js(source: str) -> str:
    """Kicsomagolja a japán hangulatjeles (ﾟДﾟ)[ﾟεﾟ] AAEncode JS obfuszkációt (ResolveURL/aadecode)."""
    if "ﾟДﾟ" not in source and "ﾟɆﾟ" not in source:
        return ""
    try:
        text = re.sub(r"\s+|/\*.*?\*/", "", source)
        alt = "ﾟɆﾟ" in text
        if alt:
            data = text.split("+(ﾟɆﾟ)[ﾟoﾟ]")[1]
            chars = data.split("+(ﾟɆﾟ)[ﾟεﾟ]+")[1:]
            char1, char2 = "ღ", "(ﾟɆﾟ)[ﾟΘﾟ]"
        else:
            data = text.split("+(ﾟДﾟ)[ﾟoﾟ]")[1]
            chars = data.split("+(ﾟДﾟ)[ﾟεﾟ]+")[1:]
            char1, char2 = "c", "(ﾟДﾟ)['0']"
        txt = ""
        for char in chars:
            char = (
                char.replace("(oﾟｰﾟo)", "u").replace(char1, "0").replace(char2, "c")
                .replace("ﾟΘﾟ", "1").replace("!+[]", "1").replace("-~", "1+")
                .replace("o", "3").replace("_", "3").replace("ﾟｰﾟ", "4").replace("(+", "(")
            )
            char = re.sub(r'\((\d)\)', r'\1', char)
            c = ""
            subchar = ""
            for v in char:
                c += v
                if re.fullmatch(r'[\d\+\-\(\)]+', c):
                    try:
                        subchar += str(eval(c, {"__builtins__": None}, {}))
                        c = ""
                    except Exception:
                        pass
            if subchar:
                txt += subchar + "|"
        txt = txt[:-1].replace('+', '')
        return "".join([chr(int(n, 8)) for n in txt.split('|') if n.isdigit()])
    except Exception:
        return ""


def deobfuscate_all_js(html: str, log_fn=None) -> str:
    """Lefuttatja az összes ismert JS kicsomagolót (Dean Edwards, Hunter, Wise, JuicyCodes v1/v2, AAEncode)."""
    chunks = []
    p1 = unpack_dean_edwards(html)
    if p1:
        if log_fn:
            log_fn("[DEOBFUSCATOR] 🔓 Dean Edwards eval(p,a,c,k,e,d) kód kicsomagolva!")
        chunks.append(p1)
    p2 = unhunt_js(html)
    if p2:
        if log_fn:
            log_fn("[DEOBFUSCATOR] 🔓 Hunter eval(h,u,n,t,e,r) kód kicsomagolva!")
        chunks.append(p2)
    p3 = unwise_js(html)
    if p3:
        if log_fn:
            log_fn("[DEOBFUSCATOR] 🔓 Wise eval(w,i,s,e) kód kicsomagolva!")
        chunks.append(p3)
    p4 = unjuice_js(html) or unjuice2_js(html)
    if p4:
        if log_fn:
            log_fn("[DEOBFUSCATOR] 🔓 JuicyCodes / _juicycodes(...) kód kicsomagolva!")
        chunks.append(p4)
    p5 = aadecode_js(html)
    if p5:
        if log_fn:
            log_fn("[DEOBFUSCATOR] 🔓 AAEncode (ﾟДﾟ) japán hangulatjel-kód kicsomagolva!")
        chunks.append(p5)
    return "\n".join(chunks)


# ==============================================================================
# 2. N_m3u8DL-RE + MEDIAFLOW-PROXY ALAPÚ KÉP-FEJLÉC ÉS PADDING ELTÁVOLÍTÓ
# ==============================================================================

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_IEND_MARKER = b"\x49\x45\x4e\x44\xae\x42\x60\x82"


def strip_disguised_m3u8_wrapper(data: bytes) -> bytes:
    """
    mediaflow-proxy TSStreamTransformer alapján:
    Egyes megosztók még magát az .m3u8 szöveges playlistet is 1x1 PNG fejléc + 0xFF
    kitöltőbájtok mögé csomagolják! Ez a függvény kicsomagolja az #EXTM3U szöveget.
    """
    if data.startswith(_PNG_SIGNATURE):
        iend_pos = data.find(_PNG_IEND_MARKER)
        if iend_pos != -1:
            data = data[iend_pos + len(_PNG_IEND_MARKER):]
    idx = 0
    while idx < len(data) and data[idx] in (0x00, 0xFF):
        idx += 1
    if idx > 0:
        data = data[idx:]
    ext_pos = data.find(b"#EXTM3U")
    if 0 < ext_pos < 4096:
        return data[ext_pos:]
    return data


def strip_disguised_image_header(data: bytes) -> bytes:
    """
    N_m3u8DL-RE ImageHeaderUtil.cs + mediaflow-proxy TSStreamTransformer alapján:
    Ha egy HLS (.ts) videószegmens elejére:
      - hamis PNG (89 50 4E 47 ... IEND), GIF (47 49 46 38), BMP (42 4D) vagy JPEG (FF D8 FF) fejlécet,
      - VAGY 0xFF / 0x00 padding bájtokat (TurboVidPlay / StreamWish / FileMoon stílus)
    ragasztottak az álcázáshoz, megkeresi az MPEG-TS szinkronbájtot (0x47 188 bájtos lépésközzel)
    és levágja a hamis fejlécet!
    """
    size = len(data)
    if size < 188 * 2:
        return data

    # Fast path: already starts with aligned MPEG-TS 0x47 sync bytes
    if data[0] == 0x47 and data[188] == 0x47:
        return data

    is_png = (data[:4] == b'\x89PNG')
    is_gif = (data[:4] == b'GIF8')
    is_bmp = (data[:2] == b'BM' and data[5:9] == b'\x00\x00\x00\x00')
    is_jpg = (data[:3] == b'\xff\xd8\xff')
    is_ff_pad = (data[0] in (0x00, 0xFF))

    if not (is_png or is_gif or is_bmp or is_jpg or is_ff_pad):
        return data

    # Search for 3 consecutive MPEG-TS 0x47 sync bytes spaced by 188 bytes
    limit = min(size - 188 * 2 - 4, 131072)
    for i in range(0, limit):
        if data[i] == 0x47 and data[i + 188] == 0x47 and data[i + 376] == 0x47:
            return data[i:]

    # Fallback: PNG IEND marker + 0x00/0xFF padding strip (mediaflow-proxy TSStreamTransformer)
    if is_png:
        iend_pos = data.find(_PNG_IEND_MARKER)
        if iend_pos != -1:
            start = iend_pos + len(_PNG_IEND_MARKER)
            while start < size and data[start] in (0x00, 0xFF):
                start += 1
            return data[start:]

    if is_gif and size > 42:
        return data[42:]
    if is_bmp and size > 0x3E:
        return data[0x3E:]
    return data


# ==============================================================================
# 3. SPECIÁLIS VIDEÓMEGOSZTÓ FELOLDÓK (mediaflow-proxy + ResolveURL alapján)
# ==============================================================================

def resolve_voe_payload(html: str, base_url: str, fetch_fn, log_fn=None) -> str:
    """
    VOE.sx (és tükördomainjei) ROT13 + LUT + Base64 + Caesar-shift dekódolója
    (mediaflow-proxy/extractors/voe.py és ResolveURL/voesx.py alapján).
    """
    # Check window.location.href redirect first
    redir_m = re.search(r"window\.location\.href\s*=\s*['\"](https?://[^'\"]+)['\"]", html)
    if redir_m:
        try:
            html, base_url = fetch_fn(redir_m.group(1), referer=base_url)
        except Exception:
            pass

    m = re.search(r'json">\["([^"]+)"]</script>\s*<script\s*src="([^"]+)"', html, re.DOTALL)
    if not m:
        return ""
    try:
        ct_raw, script_src = m.groups()
        script_url = urllib.parse.urljoin(base_url, script_src)
        script_text, _ = fetch_fn(script_url, referer=base_url)
        luts_m = re.search(r"(\[(?:'\W{2}'[,\]]){1,9})", script_text, re.DOTALL)
        if not luts_m:
            return ""
        luts = luts_m.group(1)
        lut = ["".join([("\\" + x) if x in ".*+?^${}()|[]\\" else x for x in i]) for i in luts[2:-2].split("','")]
        txt = ""
        for ch in ct_raw:
            x = ord(ch)
            if 64 < x < 91:
                x = (x - 52) % 26 + 65
            elif 96 < x < 123:
                x = (x - 84) % 26 + 97
            txt += chr(x)
        for pat in lut:
            txt = re.sub(pat, "", txt)
        ct_dec = base64.b64decode(txt + "===").decode("utf-8", errors="ignore")
        shifted = "".join([chr(ord(i) - 3) for i in ct_dec])
        final_json = base64.b64decode(shifted[::-1] + "===").decode("utf-8", errors="ignore")
        data = json.loads(final_json)
        if log_fn:
            log_fn(f"[FELOLDÓ] 🔓 VOE LUT+ROT13 titkosítás sikeresen visszafejtve!")
        return data.get("source") or ""
    except Exception:
        return ""


def resolve_streamtape(html: str, base_url: str, log_fn=None) -> str:
    """Streamtape.com /get_video?id=...&ip=... token összerakó (mediaflow-proxy/streamtape.py)."""
    if "robotlink" not in html and "get_video?" not in html:
        return ""
    matches = re.findall(r"id=.*?(?=')", html)
    for i in range(1, len(matches)):
        if matches[i - 1] == matches[i] and "ip=" in matches[i]:
            if log_fn:
                log_fn("[FELOLDÓ] 🔓 Streamtape dinamikus video-token összeállítva!")
            return f"https://streamtape.com/get_video?{matches[i]}"
    return ""


def resolve_mixdrop(unpacked_js: str, base_url: str, log_fn=None) -> str:
    """Mixdrop MDCore.wurl kinyerő (mediaflow-proxy/mixdrop.py)."""
    m = re.search(r'MDCore\.wurl\s*=\s*["\']([^"\']+)["\']', unpacked_js)
    if m:
        raw = m.group(1)
        if raw.startswith("//"):
            raw = "https:" + raw
        if log_fn:
            log_fn("[FELOLDÓ] 🔓 Mixdrop MDCore.wurl stream feloldva!")
        return urllib.parse.urljoin(base_url, raw)
    return ""


def resolve_turbovidplay(html: str, base_url: str, fetch_fn, log_fn=None) -> str:
    """
    TurboVidPlay / Emturbovid / Tuborstb urlPlay + köztes playlist feloldó
    (mediaflow-proxy/extractors/turbovidplay.py alapján).
    """
    m = re.search(r'(?:urlPlay|data-hash)\s*=\s*[\'"]([^\'"]+)', html)
    if not m:
        return ""
    try:
        media_url = urllib.parse.urljoin(base_url, m.group(1).strip())
        playlist_txt, _ = fetch_fn(media_url, referer=base_url)
        m2 = re.search(r'https?://[^\'"\s<>]+\.m3u8[^\'"\s<>]*', playlist_txt)
        if m2:
            if log_fn:
                log_fn("[FELOLDÓ] 🔓 TurboVidPlay köztes urlPlay playlist feloldva!")
            return m2.group(0)
    except Exception:
        pass
    return ""


def resolve_filemoon_f16px_aesgcm(embed_url: str, log_fn=None) -> str:
    """
    FileMoon / Byse / F16Px AES-256-GCM titkosított API feloldó
    (mediaflow-proxy/extractors/filemoon.py és F16Px.py alapján):
    Szintetikus HMAC-SHA256 fingerprint tokent generál, lekéri a
    /api/videos/{code}/embed/playback végpontot, összefűzi a szétdarabolt
    key_parts kulcsot, és AES-256-GCM-mel visszafejti a payloadot!
    """
    import os
    import hmac
    import hashlib
    parsed = urllib.parse.urlparse(embed_url)
    m = re.search(r'/(?:e|d)/([A-Za-z0-9_-]{6,32})', parsed.path or '')
    if not m:
        return ""
    code = m.group(1)
    host = parsed.netloc
    origin = f"{parsed.scheme}://{host}"

    def _b64url_dec(v: str) -> bytes:
        v = v.replace("-", "+").replace("_", "/")
        pad = (-len(v)) % 4
        if pad:
            v += "=" * pad
        return base64.b64decode(v)

    def _b64url_enc(b: bytes) -> str:
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")

    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        viewer_id = _b64url_enc(os.urandom(16))
        device_id = _b64url_enc(os.urandom(16))
        now = int(time.time())
        fp_payload = {
            "viewer_id": viewer_id,
            "device_id": device_id,
            "confidence": 0.93,
            "iat": now,
            "exp": now + 600,
        }
        pay_b64 = _b64url_enc(json.dumps(fp_payload, separators=(",", ":")).encode("utf-8"))
        sig = hmac.new(b"", pay_b64.encode("utf-8"), hashlib.sha256).digest()
        fp_body = json.dumps({
            "fingerprint": {
                "token": f"{pay_b64}.{_b64url_enc(sig)}",
                "viewer_id": viewer_id,
                "device_id": device_id,
                "confidence": 0.93,
            }
        }).encode("utf-8")

        for ep in [f"{origin}/api/videos/{code}/embed/playback", f"{origin}/api/videos/{code}"]:
            try:
                req = urllib.request.Request(
                    ep,
                    data=fp_body if ep.endswith("/playback") else None,
                    headers={
                        "User-Agent": DEFAULT_UA,
                        "Referer": embed_url,
                        "Origin": origin,
                        "Content-Type": "application/json",
                    },
                    method="POST" if ep.endswith("/playback") else "GET"
                )
                with urllib.request.urlopen(req, timeout=8) as r:
                    data = json.loads(r.read().decode("utf-8", errors="ignore"))
                if data.get("sources"):
                    return data["sources"][0].get("url", "")
                pb = data.get("playback")
                if pb and pb.get("key_parts") and pb.get("payload") and pb.get("iv"):
                    key = b"".join(_b64url_dec(p) for p in pb["key_parts"])
                    iv = _b64url_dec(pb["iv"])
                    ciphertext_and_tag = _b64url_dec(pb["payload"])
                    pt = AESGCM(key).decrypt(iv, ciphertext_and_tag, None)
                    dec_obj = json.loads(pt.decode("utf-8", errors="ignore"))
                    sources = dec_obj.get("sources") or []
                    if sources:
                        if log_fn:
                            log_fn("[FELOLDÓ] 🔓 FileMoon/F16Px AES-256-GCM titkosított playback sikeresen visszafejtve!")
                        return sources[0].get("url", "")
            except Exception:
                continue
    except Exception:
        pass
    return ""


def resolve_pornhub(html_text: str, base_url: str, log_fn=None) -> list:
    """
    Pornhub, Redtube, YouPorn és az Aylo/MindGeek hálózat beágyazott flashvars és
    mediaDefinitions JSON feloldója:
    Közvetlenül kinyeri az 1080p, 720p, 480p HLS master.m3u8 és MP4 folyamokat,
    valódi címmel, borítóképpel és másodperc-pontos videóhosszal!
    """
    import html as html_mod
    results = []
    data = {}

    # 1. Keresés var flashvars_... = {...};
    m = re.search(r"var\s+flashvars_\d+\s*=\s*(\{.+?\});\s*(?:var\s+|/\*)", html_text, re.DOTALL)
    if not m:
        m = re.search(r"var\s+flashvars_\d+\s*=\s*(\{.+?\});", html_text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
        except Exception:
            try:
                clean_json = m.group(1).replace(r'\/', '/')
                data = json.loads(clean_json)
            except Exception:
                pass

    title = data.get('video_title') or ""
    if not title:
        tm = re.search(r'<title>(.*?)</title>', html_text, re.IGNORECASE)
        if tm:
            title = html_mod.unescape(tm.group(1))
            for suf in [" - Pornhub.com", " - Redtube.com", " - YouPorn.com"]:
                if title.endswith(suf):
                    title = title[:-len(suf)].strip()
    if not title:
        og_t = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html_text, re.IGNORECASE)
        if og_t:
            title = html_mod.unescape(og_t.group(1)).strip()
    if not title:
        title = "Pornhub_Video"

    duration_sec = data.get('video_duration')
    duration_str = "--:--"
    if duration_sec:
        try:
            sec = int(duration_sec)
            m_part, s_part = divmod(sec, 60)
            h_part, m_part = divmod(m_part, 60)
            duration_str = f"{h_part:d}:{m_part:02d}:{s_part:02d}" if h_part else f"{m_part:d}:{s_part:02d}"
        except Exception:
            pass

    thumb_url = data.get('image_url') or ""
    if not thumb_url:
        im = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html_text, re.IGNORECASE)
        if im:
            thumb_url = html_mod.unescape(im.group(1))

    media_defs = data.get('mediaDefinitions')
    if not media_defs:
        md_m = re.search(r'mediaDefinitions\s*:\s*(\[\s*\{.+?\}\s*\])', html_text, re.DOTALL)
        if md_m:
            try:
                media_defs = json.loads(md_m.group(1).replace(r'\/', '/'))
            except Exception:
                pass

    if isinstance(media_defs, list):
        sorted_defs = sorted(
            [d for d in media_defs if isinstance(d, dict) and d.get('videoUrl')],
            key=lambda x: int(x.get('height') or x.get('quality') or 0),
            reverse=True
        )
        for idx, md in enumerate(sorted_defs):
            raw_u = md.get('videoUrl', '').strip()
            if not raw_u:
                continue
            vurl = html_mod.unescape(raw_u).replace(r'\/', '/')
            fmt = md.get('format', '').lower()
            height = md.get('height') or md.get('quality') or ''
            height_str = f"{height}p" if height else ""

            stype = f"HLS {height_str} Stream (Pornhub CDN)" if fmt == 'hls' else f"MP4 {height_str} (Pornhub)"
            results.append({
                'title': title,
                'display_title': f"{title} ({height_str})".strip(),
                'url': vurl,
                'type': stype,
                'origin_desc': f"Pornhub {height_str}",
                'duration': duration_str,
                'thumb_url': thumb_url,
                'referer': "https://www.pornhub.com/",
                'embed_source': base_url,
                'embed_parent_ref': base_url,
                'video_group_id': base_url,
                'priority': idx + 1,
                'label': f"[{height_str or fmt.upper()}] {title[:55]}"
            })

    if results and log_fn:
        sub_types = [r.get('type','').split()[1] for r in results[:4]]
        log_fn(f"[FELOLDÓ] 🔓 Pornhub/Aylo médiafolyamok feloldva: {title} ({len(results)} sáv: {', '.join(sub_types)})")

    return results


def resolve_xvideos(html_text: str, base_url: str, log_fn=None) -> list:
    """
    XVideos és XNXX html5player videófeloldó (HLS master és High/Low MP4 minőségek).
    """
    import html as html_mod
    results = []

    title = ""
    tm = re.search(r"html5player\.setVideoTitle\(['\"]([^'\"]+)['\"]\)", html_text)
    if tm:
        title = html_mod.unescape(tm.group(1)).strip()
    if not title:
        og_t = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html_text, re.IGNORECASE)
        if og_t:
            title = html_mod.unescape(og_t.group(1)).strip()
    if not title:
        title = "XVideos_Video"

    thumb_url = ""
    im = re.search(r"html5player\.setThumbUrl169\(['\"]([^'\"]+)['\"]\)", html_text)
    if not im:
        im = re.search(r"html5player\.setThumbUrl\(['\"]([^'\"]+)['\"]\)", html_text)
    if im:
        thumb_url = html_mod.unescape(im.group(1)).strip()

    # HLS URL
    hls_m = re.search(r"html5player\.setVideoHLS\(['\"]([^'\"]+)['\"]\)", html_text)
    if hls_m:
        hls_url = html_mod.unescape(hls_m.group(1)).strip()
        results.append({
            'title': title,
            'display_title': f"{title} (HLS Valódi Minőség)".strip(),
            'url': hls_url,
            'type': "HLS Adaptív Stream (XVideos)",
            'origin_desc': "XVideos HLS",
            'duration': "--:--",
            'thumb_url': thumb_url,
            'referer': base_url,
            'embed_source': base_url,
            'embed_parent_ref': base_url,
            'video_group_id': base_url,
            'priority': 1,
            'label': f"[HLS] {title[:55]}"
        })

    # High MP4 URL
    high_m = re.search(r"html5player\.setVideoUrlHigh\(['\"]([^'\"]+)['\"]\)", html_text)
    if high_m:
        high_url = html_mod.unescape(high_m.group(1)).strip()
        results.append({
            'title': title,
            'display_title': f"{title} (Magas Minőség MP4)".strip(),
            'url': high_url,
            'type': "MP4 High Stream (XVideos)",
            'origin_desc': "XVideos High MP4",
            'duration': "--:--",
            'thumb_url': thumb_url,
            'referer': base_url,
            'embed_source': base_url,
            'embed_parent_ref': base_url,
            'video_group_id': base_url,
            'priority': 2,
            'label': f"[High MP4] {title[:55]}"
        })

    # Low MP4 URL
    low_m = re.search(r"html5player\.setVideoUrlLow\(['\"]([^'\"]+)['\"]\)", html_text)
    if low_m:
        low_url = html_mod.unescape(low_m.group(1)).strip()
        results.append({
            'title': title,
            'display_title': f"{title} (Normál Minőség MP4)".strip(),
            'url': low_url,
            'type': "MP4 Low Stream (XVideos)",
            'origin_desc': "XVideos Low MP4",
            'duration': "--:--",
            'thumb_url': thumb_url,
            'referer': base_url,
            'embed_source': base_url,
            'embed_parent_ref': base_url,
            'video_group_id': base_url,
            'priority': 3,
            'label': f"[Low MP4] {title[:55]}"
        })

    if results and log_fn:
        log_fn(f"[FELOLDÓ] 🔓 XVideos/XNXX sávok feloldva: {title} ({len(results)} sáv)")

    return results


def extract_hidden_ember_and_redirect_domains(html: str, base_url: str) -> tuple:
    """
    Tickzoo / Megalinks / Capistock stílusú rejtett #ember input + var urls = [...]
    átirányító tömb kinyerése:
    - Sok wrapper oldal egy rejtett <input id="ember" type="hidden" value='<IFRAME SRC="...">'>
      elemben tárolja a valódi lejátszót, és kattintáskor (extraerSrcIframe + capzu)
      egy véletlenszerűen kiválasztott másik domainre (var urls = ['https://xleak.net/...'])
      irányít át ?em=base64 paraméterrel, mert a CDN (pl. store*.gofile.io) csak
      az átirányított domain Referer fejlécét fogadja el!
    Visszaadja: (hidden_iframe_urls: list, allowed_referer_origins: list)
    """
    import html as html_mod
    hidden_iframes = []
    allowed_referers = []
    seen_if = set()
    seen_ref = set()

    # 1. Extract var urls = ['https://...', ...] redirect domains for Referer hotlink bypass
    urls_arr_m = re.search(r'var\s+urls\s*=\s*\[(.*?)\]', html, re.DOTALL | re.IGNORECASE)
    if urls_arr_m:
        for u_m in re.finditer(r'["\'](https?://[^"\']+)["\']', urls_arr_m.group(1)):
            u_cand = u_m.group(1).strip()
            p = urllib.parse.urlparse(u_cand)
            if p.scheme and p.netloc:
                origin_ref = f"{p.scheme}://{p.netloc}/"
                if origin_ref not in seen_ref:
                    seen_ref.add(origin_ref)
                    allowed_referers.append(origin_ref)

    # Also check commented or active url_destino domains (e.g. capistock.com, xleak.net)
    for dest_m in re.finditer(r'["\'](https?://[^"\']+\?em=)', html, re.IGNORECASE):
        p = urllib.parse.urlparse(dest_m.group(1))
        if p.scheme and p.netloc:
            origin_ref = f"{p.scheme}://{p.netloc}/"
            if origin_ref not in seen_ref:
                seen_ref.add(origin_ref)
                allowed_referers.append(origin_ref)

    # 2. Extract hidden #ember value or HTML-escaped <iframe src="...">
    unescaped = html_mod.unescape(html)
    for m in re.finditer(
        r'id=["\']ember["\'][^>]*value=(?:["\'](.*?)["\'])',
        unescaped, re.IGNORECASE | re.DOTALL
    ):
        inner = m.group(1)
        for if_m in re.finditer(r'<iframe[^>]+src=["\']([^"\']+)["\']', inner, re.IGNORECASE):
            u = urllib.parse.urljoin(base_url, if_m.group(1).strip())
            if u not in seen_if:
                seen_if.add(u)
                hidden_iframes.append(u)

    return hidden_iframes, allowed_referers


def _format_duration_sec(seconds) -> str:
    if not seconds:
        return "--:--"
    try:
        sec = int(float(seconds))
        if sec <= 0:
            return "--:--"
        h = sec // 3600
        m = (sec % 3600) // 60
        s = sec % 60
        return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
    except Exception:
        return "--:--"


def _format_bytes_human(num_bytes: int) -> str:
    if not num_bytes or num_bytes <= 0:
        return ""
    mb = num_bytes / (1024 * 1024)
    if mb >= 1024:
        return f"{mb / 1024:.2f} GB"
    return f"{mb:.1f} MB"


def _probe_live_video_thumb_and_duration(stream_url: str, referer: str = "") -> tuple:
    """
    Közvetlen .mp4 / .m3u8 streamekhez (pl. store*.gofile.io/download/direct/...),
    amelyekhez nincs HTML borítókép:
    - ffprobe segítségével lekéri a pontos hosszt (másodperc) és felbontást,
    - ffmpeg segítségével (3. másodpercnél, vagy 0.5 mp-nél) kinyer egy valódi
      320px széles PNG előnézeti képkockát a videóból!
    """
    import subprocess
    headers_str = f"User-Agent: {DEFAULT_UA}\r\n"
    if referer:
        headers_str += f"Referer: {referer}\r\n"
        p = urllib.parse.urlparse(referer)
        if p.scheme and p.netloc:
            headers_str += f"Origin: {p.scheme}://{p.netloc}\r\n"

    duration_str = "--:--"
    resolution_str = ""
    try:
        cmd_probe = [
            "ffprobe", "-v", "error",
            "-headers", headers_str,
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height:format=duration",
            "-of", "json",
            stream_url
        ]
        pr = subprocess.run(cmd_probe, capture_output=True, text=True, timeout=7)
        if pr.returncode == 0 and pr.stdout:
            info = json.loads(pr.stdout)
            dur = (info.get("format") or {}).get("duration")
            if dur:
                duration_str = _format_duration_sec(dur)
            streams = info.get("streams") or []
            if streams:
                w = streams[0].get("width")
                h = streams[0].get("height")
                if w and h:
                    resolution_str = f"{h}p"
    except Exception:
        pass

    thumb_bytes = b""
    for seek_pos in ("00:00:03", "00:00:00.5"):
        try:
            cmd_thumb = [
                "ffmpeg", "-y",
                "-headers", headers_str,
                "-ss", seek_pos,
                "-i", stream_url,
                "-frames:v", "1",
                "-vf", "scale=320:-1",
                "-f", "image2pipe",
                "-vcodec", "png",
                "-"
            ]
            tr = subprocess.run(cmd_thumb, capture_output=True, timeout=8)
            if tr.returncode == 0 and tr.stdout and tr.stdout.startswith(b"\x89PNG"):
                thumb_bytes = tr.stdout
                break
        except Exception:
            continue

    return thumb_bytes, duration_str, resolution_str


def probe_direct_media_stream(
    target_url: str, referer: str = "", extra_referers: list = None,
    prefix_tag: str = "", base_priority: int = 0, log_fn=None
) -> list:
    """
    FetchV (worker.js + videodownloader.js) & Cat-Catch (search.js) alapú
    közvetlen folyam-detektor (MIME-típus, Content-Range, Content-Disposition,
    és bináris Magic Bytes fejléc-szimatoló + automatikus Multi-Referer Hotlink feloldó):
    - Észleli, ha egy URL (pl. ?em= paraméterből dekódolt GoFile / CDN link) már maga a
      közvetlen .mp4 / .m3u8 / .webm / .mpd videófolyam, nem pedig HTML weboldal!
    - Ha az alapértelmezett Referer 403 Forbidden / 502 hibát ad (pl. tickzoo.tv -> gofile.io),
      automatikusan végigpróbálja a megengedett átirányító Referereket (xleak.net, capistock.com, stb.)!
    - Kinyeri a VALÓDI fájlnevet a Content-Disposition fejlécből vagy az URL-ből
      (nem az álcázó oldal 'x-leak' címét használja!).
    - Kinyeri a pontos fájlméretet, hosszt és egy élő videó-képkocka borítóképet!
    """
    import os
    parsed = urllib.parse.urlparse(target_url)
    path_low = (parsed.path or "").lower()
    host_low = (parsed.netloc or "").lower()

    likely_direct = (
        path_low.endswith((".mp4", ".m3u8", ".m3u", ".mpd", ".webm", ".mkv", ".m4v", ".mov", ".flv", ".ts"))
        or "/download/direct/" in path_low
        or "gofile.io" in host_low
        or "cloudatacdn.com" in host_low
        or "master.txt" in path_low
    )
    if not likely_direct:
        return []

    candidate_refs = []
    for r_cand in (
        [referer]
        + (extra_referers or [])
        + ["https://xleak.net/", "https://capistock.com/", f"{parsed.scheme}://{parsed.netloc}/", ""]
    ):
        if r_cand is not None and r_cand not in candidate_refs:
            candidate_refs.append(r_cand)

    working_ref = referer
    content_type = ""
    content_disp = ""
    total_bytes = 0
    head_bytes = b""
    final_url = target_url
    probe_ok = False

    for ref_try in candidate_refs:
        headers = {
            "User-Agent": DEFAULT_UA,
            "Accept": "*/*",
            "Range": "bytes=0-4095",
        }
        if ref_try:
            headers["Referer"] = ref_try
            p_ref = urllib.parse.urlparse(ref_try)
            if p_ref.scheme and p_ref.netloc:
                headers["Origin"] = f"{p_ref.scheme}://{p_ref.netloc}"
        try:
            req = urllib.request.Request(target_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                content_type = (resp.headers.get("Content-Type") or "").lower()
                content_disp = resp.headers.get("Content-Disposition") or ""
                cr = resp.headers.get("Content-Range") or ""
                cl = resp.headers.get("Content-Length") or ""
                if "/" in cr:
                    try:
                        total_bytes = int(cr.split("/")[-1].strip())
                    except ValueError:
                        pass
                elif cl.isdigit():
                    total_bytes = int(cl)
                head_bytes = resp.read(4096)
                final_url = resp.url or target_url
                working_ref = ref_try
                probe_ok = True
                break
        except urllib.error.HTTPError as he:
            if he.code in (401, 403, 502, 503):
                continue
            break
        except Exception:
            continue

    if not probe_ok:
        return []

    # Check if the response is actually HTML rather than media
    stripped_head = head_bytes.lstrip()
    if (
        "text/html" in content_type
        and not stripped_head.startswith(b"#EXTM3U")
        and b"ftyp" not in head_bytes[:64]
    ):
        return []

    is_m3u8 = (
        b"#EXTM3U" in head_bytes[:512]
        or "mpegurl" in content_type
        or path_low.endswith((".m3u8", ".m3u"))
    )
    is_mpd = (b"<MPD" in head_bytes[:512] or "dash+xml" in content_type or path_low.endswith(".mpd"))
    is_video_bin = (
        "video/" in content_type
        or "application/octet-stream" in content_type
        or b"ftyp" in head_bytes[:64]
        or head_bytes.startswith((b"\x1a\x45\xdf\xa3", b"FLV", b"RIFF"))
        or path_low.endswith((".mp4", ".webm", ".mkv", ".m4v", ".mov"))
    )

    if not (is_m3u8 or is_mpd or is_video_bin):
        return []

    # Extract true filename from Content-Disposition or URL path (avoiding wrapper title 'x-leak')
    real_title = ""
    if content_disp:
        m_utf8 = re.search(r"filename\*\s*=\s*UTF-8''([^;\r\n]+)", content_disp, re.IGNORECASE)
        if m_utf8:
            real_title = urllib.parse.unquote(m_utf8.group(1).strip().strip('"\''))
        else:
            m_fn = re.search(r'filename\s*=\s*["\']?([^"\';\r\n]+)["\']?', content_disp, re.IGNORECASE)
            if m_fn:
                real_title = urllib.parse.unquote(m_fn.group(1).strip())

    if not real_title:
        base_name = urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(final_url).path or ""))
        if base_name and base_name.lower() not in ("master.m3u8", "index.m3u8", "playlist.m3u8", "video.mp4"):
            real_title = base_name

    if real_title:
        real_title = re.sub(r'\.(?:mp4|m3u8|m3u|webm|mkv|mov|flv|ts|mpd)$', '', real_title, flags=re.IGNORECASE).strip()

    if not real_title:
        real_title = f"Közvetlen_Stream_{parsed.netloc}"

    size_str = _format_bytes_human(total_bytes)
    if log_fn:
        log_fn(
            f"[FETCHV-SNIFFER] 🎯 Közvetlen médiafolyam azonosítva ({content_type or 'stream'}"
            f"{', ' + size_str if size_str else ''}, Referer: {working_ref or 'nincs'}): {real_title}"
        )

    thumb_bytes, duration_str, res_str = _probe_live_video_thumb_and_duration(final_url, referer=working_ref)

    host_name = urllib.parse.urlparse(final_url).netloc
    tag_str = f"{prefix_tag} " if prefix_tag else ""
    res_badge = f" {res_str}" if res_str else ""
    size_badge = f" [{size_str}]" if size_str else ""

    if is_m3u8:
        stype = f"HLS Stream{res_badge} (.m3u8 - {host_name}){size_badge}"
    elif is_mpd:
        stype = f"DASH Stream{res_badge} (.mpd - {host_name}){size_badge}"
    else:
        stype = f"Közvetlen MP4{res_badge} ({host_name}){size_badge}"

    dur_display = f"{duration_str} ({size_str})" if (size_str and duration_str != "--:--") else (duration_str if duration_str != "--:--" else (size_str or "Ismeretlen"))

    return [{
        'title': real_title,
        'display_title': f"{tag_str}{real_title}{size_badge}".strip(),
        'url': final_url,
        'type': stype,
        'origin_desc': prefix_tag or f"Közvetlen CDN ({host_name})",
        'duration': dur_display,
        'thumb_url': '',
        'thumb_bytes': thumb_bytes,
        'referer': working_ref,
        'embed_source': '',
        'embed_parent_ref': working_ref,
        'video_group_id': final_url,
        'is_direct_binary': is_video_bin and not is_m3u8 and not is_mpd,
        'filesize': total_bytes,
        'priority': base_priority,
        'label': f"[{tag_str}{stype}] {real_title[:55]}"
    }]


def download_direct_media_stream(
    url: str, out_file: str, referer: str = "",
    progress_cb=None, log_fn=None, cancel_check_fn=None
) -> str:
    """
    FetchV (videodownloader.js) stílusú közvetlen MP4/WebM bináris letöltő:
    - Automatikus Multi-Referer ellenőrzéssel (pl. store*.gofile.io -> Referer: https://xleak.net/)
    - 1 MB-os pufferekkel, élő sebesség / hátralévő idő / MB kijelzéssel és
      megszakadás esetén HTTP Range folytatással (Resume)!
    """
    import os
    parsed = urllib.parse.urlparse(url)
    candidate_refs = []
    for r_c in [referer, "https://xleak.net/", "https://capistock.com/", f"{parsed.scheme}://{parsed.netloc}/", ""]:
        if r_c is not None and r_c not in candidate_refs:
            candidate_refs.append(r_c)

    part_file = out_file + ".part"
    downloaded = 0
    total_size = 0
    t_start = time.time()

    def _fmt_mb(b: float) -> str:
        return f"{b / (1024 * 1024):.2f} MB"

    # Find working referer first
    active_ref = referer
    for r_try in candidate_refs:
        h_test = {"User-Agent": DEFAULT_UA, "Range": "bytes=0-1023"}
        if r_try:
            h_test["Referer"] = r_try
            p_r = urllib.parse.urlparse(r_try)
            if p_r.scheme and p_r.netloc:
                h_test["Origin"] = f"{p_r.scheme}://{p_r.netloc}"
        try:
            req_t = urllib.request.Request(url, headers=h_test)
            with urllib.request.urlopen(req_t, timeout=12) as resp_t:
                active_ref = r_try
                cr = resp_t.headers.get("Content-Range") or ""
                cl = resp_t.headers.get("Content-Length") or ""
                if "/" in cr:
                    try:
                        total_size = int(cr.split("/")[-1].strip())
                    except ValueError:
                        pass
                elif cl.isdigit():
                    total_size = int(cl)
                break
        except urllib.error.HTTPError as he:
            if he.code in (401, 403, 502, 503):
                continue
            break
        except Exception:
            continue

    if log_fn:
        log_fn(
            f"[FETCHV-DIRECT] 🚀 Közvetlen bináris stream letöltése (Referer: {active_ref or 'nincs'}"
            f"{', Méret: ' + _fmt_mb(total_size) if total_size else ''})..."
        )

    try:
        with open(part_file, "wb") as f_out:
            for attempt in range(5):
                if cancel_check_fn and cancel_check_fn():
                    raise InterruptedError("A felhasználó megszakította a letöltést.")
                headers = {"User-Agent": DEFAULT_UA, "Accept": "*/*"}
                if active_ref:
                    headers["Referer"] = active_ref
                    p_r = urllib.parse.urlparse(active_ref)
                    if p_r.scheme and p_r.netloc:
                        headers["Origin"] = f"{p_r.scheme}://{p_r.netloc}"
                if downloaded > 0:
                    headers["Range"] = f"bytes={downloaded}-"

                try:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=25) as resp:
                        if total_size <= 0:
                            cl = resp.headers.get("Content-Length") or ""
                            if cl.isdigit():
                                total_size = int(cl) + downloaded
                        while True:
                            if cancel_check_fn and cancel_check_fn():
                                raise InterruptedError("A felhasználó megszakította a letöltést.")
                            chunk = resp.read(512 * 1024)
                            if not chunk:
                                break
                            f_out.write(chunk)
                            downloaded += len(chunk)
                            if progress_cb:
                                elapsed = max(0.1, time.time() - t_start)
                                spd = downloaded / elapsed
                                spd_str = f"{spd / (1024 * 1024):.2f} MB/s"
                                if total_size > 0:
                                    pct = min(100.0, (downloaded / total_size) * 100.0)
                                    rem = max(0, total_size - downloaded)
                                    eta_s = int(rem / spd) if spd > 0 else 0
                                    eta_str = f"{eta_s // 60:02d}:{eta_s % 60:02d}"
                                    sz_str = f"{_fmt_mb(downloaded)} / {_fmt_mb(total_size)}"
                                else:
                                    pct = 50.0
                                    eta_str = "--:--"
                                    sz_str = _fmt_mb(downloaded)
                                progress_cb(pct, spd_str, eta_str, sz_str, f"Közvetlen MP4 letöltése ({pct:.1f}%)...")
                    break
                except InterruptedError:
                    raise
                except Exception:
                    if attempt == 4:
                        raise
                    time.sleep(1.0 * (attempt + 1))

        if os.path.exists(out_file):
            os.remove(out_file)
        os.replace(part_file, out_file)
        if progress_cb:
            progress_cb(100.0, "-", "00:00", _fmt_mb(downloaded), "Közvetlen MP4 letöltés kész!")
        return out_file
    except Exception:
        try:
            if os.path.exists(part_file):
                os.remove(part_file)
        except OSError:
            pass
        raise


def scrape_generic_player_sources(html_and_js: str, base_url: str) -> list:
    """
    ResolveURL helpers.py scrape_sources() + Cat-Catch search.js mintájára kinyeri
    a JWPlayer / VideoJS / Plyr / Clappr / Flowplayer konfigurációkból a
    'sources: [...]', 'file: "..."', 'src: "..."' és inline base64 m3u8 streameket.
    """
    found = []
    seen = set()
    patterns = [
        r'''(?:file|src|hls|mp4|url)\s*:\s*["']((?:https?:)?//[^"'\s<>]+\.(?:m3u8|m3u|mpd|mp4|webm|txt)[^"'\s<>]*)["']''',
        r'''sources\s*:\s*\[\s*["']((?:https?:)?//[^"'\s<>]+)["']''',
        r'''<source[^>]+src=["']((?:https?:)?//[^"'\s<>]+)["']''',
    ]
    for pat in patterns:
        for m in re.finditer(pat, html_and_js, re.IGNORECASE):
            u = m.group(1).strip()
            if u.startswith("//"):
                u = "https:" + u
            u = urllib.parse.urljoin(base_url, u)
            if any(bad in u.lower() for bad in ['thumb', 'sprite', 'preview', 'vast', 'ima3', '.vtt', '.srt', '.jpg', '.png']):
                continue
            if u not in seen:
                seen.add(u)
                found.append(u)
    return found


def probe_hls_needs_header_strip(m3u8_url: str, referer: str = "") -> bool:
    """
    Megvizsgálja az m3u8 playlist első szegmensét: ha hamis PNG/GIF/BMP/JPEG
    fejléc van az elején (pl. 1x1 PNG a TikTok CDN-es /stream/ HLS-ben), vagy
    nem 0x47 MPEG-TS szinkronbájttal kezdődik, True-t ad vissza!
    """
    headers = {"User-Agent": DEFAULT_UA}
    if referer:
        headers["Referer"] = referer
        parsed = urllib.parse.urlparse(referer)
        if parsed.scheme and parsed.netloc:
            headers["Origin"] = f"{parsed.scheme}://{parsed.netloc}"

    try:
        req = urllib.request.Request(m3u8_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            raw_m3u8 = strip_disguised_m3u8_wrapper(r.read()).decode("utf-8", errors="ignore")
        current_base = m3u8_url

        if "#EXT-X-STREAM-INF" in raw_m3u8:
            sub_candidates = [
                line.strip() for line in raw_m3u8.splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            if sub_candidates:
                sub_url = urllib.parse.urljoin(current_base, sub_candidates[0])
                req2 = urllib.request.Request(sub_url, headers=headers)
                with urllib.request.urlopen(req2, timeout=10) as r2:
                    raw_m3u8 = strip_disguised_m3u8_wrapper(r2.read()).decode("utf-8", errors="ignore")
                current_base = sub_url

        seg_urls = [
            urllib.parse.urljoin(current_base, line.strip())
            for line in raw_m3u8.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if not seg_urls:
            return False

        first_seg = seg_urls[0]
        low_seg = first_seg.lower()
        if any(k in low_seg for k in ["tiktokcdn.com", ".image", ".png", ".jpg", ".gif", ".bmp", ".txt"]):
            return True

        range_headers = dict(headers)
        range_headers["Range"] = "bytes=0-2047"
        req_s = urllib.request.Request(first_seg, headers=range_headers)
        with urllib.request.urlopen(req_s, timeout=10) as rs:
            head_bytes = rs.read(2048)

        if head_bytes[:4] in (b'\x89PNG', b'GIF8') or head_bytes[:2] == b'BM' or head_bytes[:3] == b'\xff\xd8\xff':
            return True
        if head_bytes and head_bytes[0] != 0x47 and head_bytes[:4] != b'\x00\x00\x00\x18':
            return True
    except Exception:
        pass
    return False


def _decrypt_aes128_cbc(data: bytes, key: bytes, iv: bytes) -> bytes:
    """Cat-Catch / FetchV kompatibilis HLS AES-128-CBC szegmens visszafejtő."""
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        if len(data) < 16 or len(data) % 16 != 0:
            return data
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        pt = decryptor.update(data) + decryptor.finalize()
        # Strip PKCS#7 padding if valid
        pad_len = pt[-1]
        if 1 <= pad_len <= 16 and pt[-pad_len:] == bytes([pad_len]) * pad_len:
            pt = pt[:-pad_len]
        return pt
    except Exception:
        return data


def download_disguised_hls_with_header_strip(
    m3u8_url: str, out_file: str, referer: str = "",
    max_workers: int = 8, progress_cb=None, log_fn=None, cancel_check_fn=None
) -> str:
    """
    N_m3u8DL-RE + Cat-Catch + FetchV stílusú extrém HLS letöltő:
    - Kezeli a PNG/GIF/BMP/JPEG/0xFF fejléccel álcázott szegmenseket (pl. 70 bájtos 1x1 PNG a TikTok CDN-en).
    - Kezeli a #EXT-X-KEY:METHOD=AES-128,URI="...",IV=0x... titkosított HLS szegmenseket (Cat-Catch m3u8.js mintára).
    - Kezeli a #EXT-X-MAP:URI="..." fMP4 inicializáló fejlécet.
    - Automatikusan kiválasztja a legnagyobb felbontású/sávszélességű al-playlistet (#EXT-X-STREAM-INF BANDWIDTH).
    - Párhuzamosan letölti, visszafejti és megtisztítja a szegmenseket, majd FFmpeg-gel MP4-be fűzi!
    """
    import os
    import subprocess
    from concurrent.futures import ThreadPoolExecutor, as_completed

    headers = {"User-Agent": DEFAULT_UA}
    if referer:
        headers["Referer"] = referer
        parsed = urllib.parse.urlparse(referer)
        if parsed.scheme and parsed.netloc:
            headers["Origin"] = f"{parsed.scheme}://{parsed.netloc}"

    def _get_bytes(u: str) -> bytes:
        req = urllib.request.Request(u, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read()

    raw_m3u8 = strip_disguised_m3u8_wrapper(_get_bytes(m3u8_url)).decode("utf-8", errors="ignore")
    current_base = m3u8_url

    # Check if master playlist pointing to sub-playlists -> pick highest BANDWIDTH
    if "#EXT-X-STREAM-INF" in raw_m3u8:
        lines = [ln.strip() for ln in raw_m3u8.splitlines() if ln.strip()]
        best_sub = ""
        best_bw = -1
        for i, ln in enumerate(lines):
            if ln.startswith("#EXT-X-STREAM-INF") and i + 1 < len(lines) and not lines[i + 1].startswith("#"):
                bw_m = re.search(r'BANDWIDTH=(\d+)', ln)
                bw = int(bw_m.group(1)) if bw_m else 0
                if bw >= best_bw:
                    best_bw = bw
                    best_sub = lines[i + 1]
        if not best_sub:
            sub_candidates = [ln for ln in lines if not ln.startswith("#")]
            if sub_candidates:
                best_sub = sub_candidates[0]
        if best_sub:
            sub_url = urllib.parse.urljoin(current_base, best_sub)
            if log_fn:
                log_fn(f"[EXTREME-HLS] Legjobb minőségű al-playlist követése: {sub_url}")
            raw_m3u8 = strip_disguised_m3u8_wrapper(_get_bytes(sub_url)).decode("utf-8", errors="ignore")
            current_base = sub_url

    # Parse #EXT-X-MEDIA-SEQUENCE, #EXT-X-KEY (AES-128), #EXT-X-MAP (fMP4 init), and segment URLs
    media_sequence = 0
    current_key_bytes = None
    current_iv_bytes = None
    key_cache = {}
    init_map_bytes = b""
    seg_tasks = []  # list of (idx, seg_url, key_bytes, iv_bytes)

    for line in raw_m3u8.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#EXT-X-MEDIA-SEQUENCE:"):
            try:
                media_sequence = int(s.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif s.startswith("#EXT-X-MAP:"):
            uri_m = re.search(r'URI=["\']([^"\']+)["\']', s)
            if uri_m and not init_map_bytes:
                map_url = urllib.parse.urljoin(current_base, uri_m.group(1))
                try:
                    init_map_bytes = strip_disguised_image_header(_get_bytes(map_url))
                except Exception:
                    pass
        elif s.startswith("#EXT-X-KEY:"):
            if "METHOD=AES-128" in s:
                uri_m = re.search(r'URI=["\']([^"\']+)["\']', s)
                iv_m = re.search(r'IV=0x([0-9a-fA-F]+)', s)
                if uri_m:
                    key_url = urllib.parse.urljoin(current_base, uri_m.group(1))
                    if key_url not in key_cache:
                        try:
                            key_cache[key_url] = _get_bytes(key_url)[:16]
                            if log_fn:
                                log_fn(f"[EXTREME-HLS] 🔑 AES-128 titkosítási kulcs letöltve: {key_url}")
                        except Exception:
                            key_cache[key_url] = None
                    current_key_bytes = key_cache[key_url]
                if iv_m:
                    try:
                        current_iv_bytes = bytes.fromhex(iv_m.group(1).zfill(32)[:32])
                    except ValueError:
                        current_iv_bytes = None
                else:
                    current_iv_bytes = None
            elif "METHOD=NONE" in s:
                current_key_bytes = None
                current_iv_bytes = None
        elif not s.startswith("#"):
            seg_idx = len(seg_tasks)
            seq_num = media_sequence + seg_idx
            seg_url = urllib.parse.urljoin(current_base, s)
            iv_for_seg = current_iv_bytes or seq_num.to_bytes(16, byteorder="big")
            seg_tasks.append((seg_idx, seg_url, current_key_bytes, iv_for_seg))

    if not seg_tasks:
        raise RuntimeError("Nem található szegmens az m3u8 playlistben.")

    total_segs = len(seg_tasks)
    if log_fn:
        log_fn(
            f"[EXTREME-HLS] 🛡️ {total_segs} db álcázott/védett szegmens párhuzamos letöltése és "
            f"hamis PNG/GIF/Képfejléc + AES-128 tisztítása ({max_workers} szálon)..."
        )

    tmp_ts = out_file + ".temp_clean.ts"
    completed = 0
    next_write_idx = 0
    pending_chunks = {}
    downloaded_bytes = 0
    stripped_header_count = 0
    t_start = time.time()

    def _fmt_mb(b: float) -> str:
        return f"{b / (1024 * 1024):.1f} MB"

    def _fetch_and_clean(task_tuple):
        idx, u, k_bytes, iv_bytes = task_tuple
        for attempt in range(4):
            if cancel_check_fn and cancel_check_fn():
                return idx, b"", False
            try:
                raw_seg = _get_bytes(u)
                if k_bytes and len(k_bytes) == 16:
                    # Try decrypting before or after header strip
                    clean_before = strip_disguised_image_header(raw_seg)
                    if len(clean_before) != len(raw_seg) and len(clean_before) % 16 == 0:
                        dec_seg = _decrypt_aes128_cbc(clean_before, k_bytes, iv_bytes)
                        clean_seg = strip_disguised_image_header(dec_seg)
                    else:
                        dec_seg = _decrypt_aes128_cbc(raw_seg, k_bytes, iv_bytes)
                        clean_seg = strip_disguised_image_header(dec_seg)
                else:
                    clean_seg = strip_disguised_image_header(raw_seg)
                was_stripped = (len(clean_seg) != len(raw_seg))
                return idx, clean_seg, was_stripped
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(0.6 * (attempt + 1))
        return idx, b"", False

    try:
        with open(tmp_ts, "wb") as f_out:
            if init_map_bytes:
                f_out.write(init_map_bytes)
            with ThreadPoolExecutor(max_workers=max(1, max_workers)) as pool:
                futures = [pool.submit(_fetch_and_clean, t) for t in seg_tasks]
                for fut in as_completed(futures):
                    if cancel_check_fn and cancel_check_fn():
                        for f in futures:
                            f.cancel()
                        raise InterruptedError("A felhasználó megszakította a letöltést.")

                    idx, clean_bytes, was_stripped = fut.result()
                    if was_stripped:
                        stripped_header_count += 1
                    downloaded_bytes += len(clean_bytes)
                    pending_chunks[idx] = clean_bytes
                    completed += 1

                    # Flush contiguous segments in order to disk so RAM stays low
                    while next_write_idx in pending_chunks:
                        f_out.write(pending_chunks.pop(next_write_idx))
                        next_write_idx += 1

                    if progress_cb:
                        pct = (completed / total_segs) * 100.0
                        elapsed = max(0.1, time.time() - t_start)
                        speed_bps = downloaded_bytes / elapsed
                        speed_str = f"{speed_bps / (1024 * 1024):.2f} MB/s"
                        est_total = (downloaded_bytes / completed) * total_segs
                        rem_bytes = max(0.0, est_total - downloaded_bytes)
                        eta_sec = int(rem_bytes / speed_bps) if speed_bps > 0 else 0
                        eta_str = f"{eta_sec // 60:02d}:{eta_sec % 60:02d}"
                        size_str = f"{_fmt_mb(downloaded_bytes)} / ~{_fmt_mb(est_total)}"
                        stage_str = (
                            f"Álcázott szegmens tisztítása (PNG->TS): {completed}/{total_segs} ({pct:.1f}%)"
                        )
                        progress_cb(pct, speed_str, eta_str, size_str, stage_str)
    except Exception:
        try:
            os.remove(tmp_ts)
        except OSError:
            pass
        raise

    if log_fn:
        log_fn(
            f"[EXTREME-HLS] ✅ {total_segs} szegmens letöltve ({_fmt_mb(downloaded_bytes)}), "
            f"{stripped_header_count} db hamis képfejléc levágva! FFmpeg MP4 összefűzés..."
        )
    if progress_cb:
        progress_cb(100.0, "-", "00:00", _fmt_mb(downloaded_bytes), "Tiszta MPEG-TS -> MP4 összefűzés (FFmpeg)...")

    cmd = ["ffmpeg", "-y", "-i", tmp_ts, "-c", "copy", "-bsf:a", "aac_adtstoasc", out_file]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        os.remove(tmp_ts)
    except OSError:
        pass

    if proc.returncode == 0 and os.path.exists(out_file):
        return out_file
    raise RuntimeError(f"Extreme-HLS FFmpeg remux hiba: {proc.stderr[-300:] if proc.stderr else 'ismeretlen'}")



