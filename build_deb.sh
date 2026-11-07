#!/bin/bash
set -e

SRC_ROOT="/data/youtube downloader"
GUI_SRC="$SRC_ROOT/youtube-downloader-gui-src"
YTDLP_SRC="$SRC_ROOT/yt-dlp-master"
YTDN_SRC="$SRC_ROOT/ytDownloader-main"
VIDDL_SRC="$SRC_ROOT/video-downloader-master"

PKG_NAME="youtube-downloader-gui"
PKG_VER="2026.10.26-7"
BUILD_DIR="$GUI_SRC/deb_build/${PKG_NAME}_${PKG_VER}_all"

rm -rf "$GUI_SRC/deb_build"
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/bin"
mkdir -p "$BUILD_DIR/usr/lib/$PKG_NAME"
mkdir -p "$BUILD_DIR/usr/share/applications"
mkdir -p "$BUILD_DIR/usr/share/pixmaps"
mkdir -p "$BUILD_DIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$BUILD_DIR/usr/share/icons/hicolor/scalable/apps"

# Copy GUI main script and extreme_resolvers module
cp "$GUI_SRC/gui_main.py" "$BUILD_DIR/usr/lib/$PKG_NAME/gui_main.py"
cp "$GUI_SRC/extreme_resolvers.py" "$BUILD_DIR/usr/lib/$PKG_NAME/extreme_resolvers.py"
chmod 755 "$BUILD_DIR/usr/lib/$PKG_NAME/gui_main.py"
chmod 644 "$BUILD_DIR/usr/lib/$PKG_NAME/extreme_resolvers.py"

# Copy yt_dlp engine from yt-dlp-master
cp -r "$YTDLP_SRC/yt_dlp" "$BUILD_DIR/usr/lib/$PKG_NAME/"

# Copy icons from ytDownloader-main and video-downloader-master
cp "$YTDN_SRC/resources/icon.png" "$BUILD_DIR/usr/lib/$PKG_NAME/icon.png"
cp "$YTDN_SRC/resources/icon.png" "$BUILD_DIR/usr/share/pixmaps/$PKG_NAME.png"
cp "$YTDN_SRC/resources/icon.png" "$BUILD_DIR/usr/share/icons/hicolor/256x256/apps/$PKG_NAME.png"
cp "$VIDDL_SRC/data/com.github.unrud.VideoDownloader.svg" "$BUILD_DIR/usr/share/icons/hicolor/scalable/apps/$PKG_NAME.svg"

# Create /usr/bin/youtube-downloader-gui launcher
cat << 'EOF' > "$BUILD_DIR/usr/bin/youtube-downloader-gui"
#!/bin/bash
exec /usr/bin/python3 /usr/lib/youtube-downloader-gui/gui_main.py "$@"
EOF
chmod 755 "$BUILD_DIR/usr/bin/youtube-downloader-gui"

# Create /usr/bin/yt-dlp CLI wrapper so yt-dlp is also available system-wide
cat << 'EOF' > "$BUILD_DIR/usr/bin/yt-dlp"
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/usr/lib/youtube-downloader-gui')
import yt_dlp
if __name__ == '__main__':
    yt_dlp.main()
EOF
chmod 755 "$BUILD_DIR/usr/bin/yt-dlp"

# Create Desktop entry
cat << 'EOF' > "$BUILD_DIR/usr/share/applications/youtube-downloader-gui.desktop"
[Desktop Entry]
Name=YouTube Video Downloader
Name[hu]=YouTube Videó Letöltő (GUI)
Comment=Download videos and audio from YouTube and 1000+ websites
Comment[hu]=Videók és zenék letöltése YouTube-ról és más oldalakról (yt-dlp GUI)
Exec=/usr/bin/youtube-downloader-gui %U
Icon=youtube-downloader-gui
Terminal=false
Type=Application
Categories=AudioVideo;Video;Network;Qt;
Keywords=youtube;video;audio;mp3;mp4;downloader;yt-dlp;letolto;
StartupNotify=true
EOF
chmod 644 "$BUILD_DIR/usr/share/applications/youtube-downloader-gui.desktop"

# Create DEBIAN/control
cat << EOF > "$BUILD_DIR/DEBIAN/control"
Package: $PKG_NAME
Version: $PKG_VER
Section: video
Priority: optional
Architecture: all
Depends: python3, python3-pyqt5, ffmpeg
Recommends: nodejs
Provides: yt-dlp
Maintainer: Jules <jules@localhost>
Description: Grafikus YouTube es Video Letolto alkalmazas (PyQt6 + yt-dlp)
 Modern, magyar nyelvu grafikus felulet YouTube videok, lejatszasi listak
 es hangfajlok (MP4, MKV, WEBM, MP3, M4A, FLAC, OPUS, WAV) letoltesehez.
 Tartalmazza a beepitett yt-dlp (2026.10.26) motort es parancssori eszkozt is.
EOF

# Create DEBIAN/postinst
cat << 'EOF' > "$BUILD_DIR/DEBIAN/postinst"
#!/bin/bash
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
exit 0
EOF
chmod 755 "$BUILD_DIR/DEBIAN/postinst"

# Build .deb package
DEB_OUT="$SRC_ROOT/${PKG_NAME}_${PKG_VER}_all.deb"
dpkg-deb --root-owner-group --build "$BUILD_DIR" "$DEB_OUT"
cp -f "$DEB_OUT" "$SRC_ROOT/${PKG_NAME}_2026.10.26-1_all.deb"
echo "Successfully built: $DEB_OUT"
