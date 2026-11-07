# 🕸️ YouTube & Univerzális Álcázott Stream Scraper / Videó Letöltő PRO (GUI)

Modern, magyar nyelvű grafikus (`PyQt6` / `PyQt5`) videóletöltő és többrétegű álcázott stream-feloldó alkalmazás Linuxra, beépített `yt-dlp` motorral és **Vizuális (borítóképes) Videóválasztó Ablakkal**.

---

## 🚀 Főbb Képességek

1. **YouTube és 1000+ videómegosztó támogatása (`yt-dlp` motor)**:
   - 4K / 1440p / 1080p / 720p videó + hang letöltés és automatikus FFmpeg összefűzés (`MP4`, `MKV`, `WEBM`).
   - Csak hang kinyerése (`MP3 320kbps`, `M4A`, `FLAC`, `OPUS`, `WAV`).
   - Feliratok, borítókép és metaadatok beágyazása.

2. **Többrétegű Átirányítások (`?em=...`, `#ember`) és Álcázott Streamek Feloldása**:
   - **`?em=` / `?embed=` Base64 paraméter dekódolás**: Különválasztja és egyszerre felkutatja az URL paraméterben érkező beágyazott videót és a háttéroldal saját videóját.
   - **Rejtett `#ember` (`extraerSrcIframe` + `capzu`) kicsomagoló**: Automatikusan kinyeri a rejtett `<input id="ember" type="hidden" value="<IFRAME SRC=...>"` elemekből a valódi lejátszót, és feloldja a `var urls = [...]` alapú Multi-Referer Hotlink védelmet.
   - **Vizuális Videóválasztó Ablak (`VideoSelectorDialog`)**: Ha egy oldalon több különböző videó található, borítóképpel, címmel, pontos időtartammal, fájlmérettel és forrás-információval jeleníti meg őket, hogy egyetlen kattintással kiválasztható legyen a kívánt videó.

3. **Integrált Extrém Dekódoló és Feloldó Motor (`extreme_resolvers.py`)**:
   - **JavaScript Deobfuscatorok** (*ResolveURL* alapján):
     - Dean Edwards `eval(function(p,a,c,k,e,d)...)`
     - Hunter `eval(function(h,u,n,t,e,r)...)`
     - Wise `eval(function(w,i,s,e)...)`
     - `JuicyCodes.Run(...)` és `_juicycodes(...)` (ROT13 + Base64 + szimbólumtábla)
     - `AAEncode` (`(ﾟДﾟ)[ﾟεﾟ]`) japán hangulatjel-kódolás
   - **Speciális Videómegosztó Feloldók** (*mediaflow-proxy* és *ResolveURL* alapján):
     - `StreamHG` / `Ghbrisk` / `VidHide` / `StreamWish` (`hls4` TikTok CDN + `hls2` tartalék sáv)
     - `DoodStream` / `Playmogo` / `DS2Play` (`/pass_md5/...` + dinamikus token generálás)
     - `FileMoon` / `Byse` / `F16Px` (`/api/videos/{code}/embed/playback` + szintetikus HMAC-SHA256 fingerprint + `AES-256-GCM` visszafejtés)
     - `VOE.sx` (ROT13 + LUT + Base64 + Caesar-shift)
     - `Mixdrop` (`MDCore.wurl`), `Streamtape` (`/get_video` dinamikus token), `TurboVidPlay` (`urlPlay`)
   - **Képfejléccel Álcázott HLS (`.m3u8`) Szegmens-Tisztító és AES-128 Dekódoló** (*N_m3u8DL-RE* + *Cat-Catch* alapján):
     - Automatikusan felismeri és levágja a HLS szegmensek elejére ragasztott hamis `1x1 PNG` (`89 50 4E 47 ... IEND`), `GIF`, `BMP`, `JPEG` fejléceket és `0xFF`/`0x00` kitöltőbájtokat egészen a valódi `0x47` (188 bájtos) MPEG-TS szinkronbájtig.
     - Kezeli a `#EXT-X-KEY:METHOD=AES-128,URI="...",IV=...` titkosított szegmenseket és a `#EXT-X-MAP` (fMP4) inicializáló fejléceket.
   - **FetchV Közvetlen Folyam-Szimatoló (`probe_direct_media_stream` & `download_direct_media_stream`)**:
     - `Range: bytes=0-4095` próbakéréssel, `Content-Type`, `Content-Range`, `Content-Disposition` (`filename*=UTF-8''...`) és *Magic Bytes* (`#EXTM3U`, `ftyp`, `\x1a\x45\xdf\xa3`, `<MPD`) vizsgálattal azonosítja a közvetlen `.mp4` / `.m3u8` folyamokat (pl. `gofile.io/download/direct/...`).
     - Automatikusan élő előnézeti képkockát (`ffmpeg`) és pontos hosszt (`ffprobe`) nyer ki a közvetlen videófájlokból is.

---

## 📦 Telepítés (`.deb` csomagból)

```bash
sudo dpkg -i youtube-downloader-gui_2026.10.26-7_all.deb
sudo apt-get install -f
```

Indítás terminálból vagy az Alkalmazások menüből (**YouTube Videó Letöltő (GUI)**):

```bash
youtube-downloader-gui
```

## 🛠️ Csomag újraépítése forrásból

```bash
bash build_deb.sh
```

