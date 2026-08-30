![X-ISO](docs/x-iso-banner.svg)
![Python](https://img.shields.io/badge/python-3.6%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Linux-orange)
![Windows](https://img.shields.io/badge/Windows-partial%20support-yellow)
![GUI](https://img.shields.io/badge/GUI-Tkinter-blue)
![Status](https://img.shields.io/badge/status-active%20development-brightgreen)
![ffmpeg](https://img.shields.io/badge/powered%20by-ffmpeg-red)
![cdparanoia](https://img.shields.io/badge/ripping-cdparanoia-lightgrey)
![MusicBrainz](https://img.shields.io/badge/metadata-MusicBrainz-black)
![Version](https://img.shields.io/badge/version-1.0-blue)
# X-ISO - Disc Image Converter & Burner

A comprehensive cross-platform disc image conversion and audio CD ripping utility with metadata support.

## Features

### Core Functionality
- **Convert Multiple Disc Image Formats**: DMG, BIN, NRG, CUE, MDS, IMG, ISO, ISZ, UDF, CDI, DAO, TAO, and more
- **Burn to Optical Media**: CD, DVD, and Blu-ray disc burning with verification
- **Virtual Drive Management**: Mount and unmount ISO images as virtual drives
- **Audio CD Ripping**: Real extraction via `cdparanoia` + `ffmpeg`, with automatic metadata lookup and ID3/format tagging
- **Audio Conversion**: Convert between multiple audio formats (MP3, WAV, FLAC, AAC, OGG, M4A, WMA, OPUS, APE)

### Advanced Features
- **Multi-Source Metadata Retrieval**: Album, artist, year, and per-track titles, resolved through a prioritized chain of sources (see [Metadata Support](#metadata-support) below)
- **High-Quality Audio Extraction**: 320kbps MP3, lossless FLAC, and other format support
- **Organized File Structure**: Auto-creates Artist/Album folder hierarchy
- **Multi-Format Audio Support**: 9+ audio format conversions
- **USB Drive Imaging**: Create and manage USB drive images
- **Bootable USB Creation**: Create bootable USB drives with MBR/GPT support
- **Disc Copying**: Copy physical discs with verification
- **Disc Image Creation**: Create images from physical media
- **Disc Verification**: Verify disc integrity

## Implementation Status

| Feature | Status |
|---|---|
| Rip Audio CD | ✅ Fully implemented (`cdparanoia` + `ffmpeg` + multi-source metadata) |
| Metadata lookup (MusicBrainz/GnuDB/CDDB) | ✅ Fully implemented |
| Audio Converter (file-to-file) | ✅ Implemented via `ffmpeg` |
| Burn Disc | ✅ Implemented (Linux) — `wodim`/`cdrecord` for CD, `growisofs` for DVD/BD, optional post-burn byte-compare verify |
| Append Data to Disc | ✅ Implemented (Linux) — `growisofs -M`; DVD±R(W)/BD only, not CD-R |
| Erase Rewritable Disc | ✅ Implemented (Linux) — `wodim blank=` for CD, `dvd+rw-format` for DVD |
| Copy CD/DVD/Blu-ray | ✅ Implemented (Linux) — reads source to a temp image via `dd`, then burns it to the destination; supports multiple copies with a disc-swap prompt |
| Make CD/DVD/Blu-ray Image | ✅ Implemented (Linux) — `dd` for ISO; BIN/CUE is an approximate single-track MODE1/2048 rip (not a true raw-sector rip); NRG isn't really implementable simply, so it falls back to ISO with a warning |
| Make USB Drive Image | ✅ Implemented (Linux) — `dd` from a detected USB block device |
| Create Bootable USB | ✅ Implemented (Linux) — `dd` writes the ISO directly; works for the hybrid ISOs most modern Linux distros ship. The MBR/GPT selector is informational only — a raw `dd` write preserves whatever partition table is already inside the source ISO |
| Virtual Drive mount/unmount | ✅ Implemented (Linux) — `udisksctl loop-setup`/`mount`/`unmount`/`loop-delete`, no root required on a typical desktop setup |
| Convert to ISO | ⚠️ Currently a raw byte-copy — not true format-specific conversion for non-ISO sources (DMG/NRG/BIN/etc.) |

All eight "Implemented (Linux)" tools currently show a clear "not implemented on Windows yet" error on Windows rather than simulating success. Untested against real hardware beyond the Rip Audio CD pipeline — treat as implemented-but-unverified until confirmed on your own drives/media.

## System Requirements

### Minimum Requirements
- **OS**: Linux (Linux Mint, Ubuntu, Debian, Fedora, etc.) — full feature support; or Windows — ripping/conversion only, see [Implementation Status](#implementation-status)
- **Python**: 3.6 or higher
- **RAM**: 2GB minimum
- **Storage**: 100MB free space for application + storage for images/audio

### Required External Tools

#### Linux
```bash
# Fedora/RHEL
sudo dnf install cdparanoia ffmpeg wodim dvd+rw-tools udisks2

# Ubuntu/Debian/Linux Mint
sudo apt-get install cdparanoia ffmpeg wodim dvd+rw-tools udisks2

# python3-libdiscid
Libdiscid allows one to create MusicBrainz DiscIDs from audio CDs. It reads a CD's table of contents and generates an identifier which can be used to lookup the CD at MusicBrainz. python-libdiscid provides a binding to work with libdiscid from Python.

This package provides the binding for Python 3.

If you want to manage this through your system's package manager, install python3-libdiscid instead. Run the following commands:

sudo apt-get update
sudo apt-get install libdiscid0 python3-libdiscid

# Arch
sudo pacman -S cdparanoia ffmpeg cdrtools dvd+rw-tools udisks2
```

`wodim` (or `cdrecord` as a fallback), `dvd+rw-tools` (provides `growisofs` and `dvd+rw-format`), and `udisks2` (provides `udisksctl`) are required for Burn/Append/Erase/Copy/Make Image/Virtual Drive. `udisks2` is preinstalled on most desktop Linux distributions already. `dd` and `lsblk` (used for USB imaging, bootable USB creation, and drive detection) are part of standard `coreutils`/`util-linux` and are already present on virtually every Linux system.

#### Windows
- Download and install [FFmpeg](https://ffmpeg.org/download.html)
- Download and install a Windows build of [cdparanoia](https://www.xiph.org/paranoia/) (**required**, not optional, for ripping — X-ISO shells out to `cdparanoia` on both platforms)
- Add both to system PATH
- Note: Windows builds of `cdparanoia` vary in what device-identifier format they expect (bare drive letter vs. numeric generic-device ID). X-ISO normalizes drive letters like `D:` to a bare `D`; if your specific build expects something else, see `_cdparanoia_device_arg()` in `X-ISO.py`.
- Burn/Append/Erase/Copy/Make Image/USB Image/Bootable USB/Virtual Drive are currently Linux-only — see [Implementation Status](#implementation-status)

### Python Version
- Python 3.6+ (3.8+ recommended)
- tkinter (usually included with Python)

## Installation

### Linux (Linux Mint, Ubuntu, Debian)

1. **Clone or download the project**
   ```bash
   git clone https://github.com/david-spies/x-iso.git
   cd x-iso
   ```

2. **Install system dependencies**
   ```bash
   source venv/bin/activate

   sudo apt-get update
   sudo apt-get install python3 python3-tk cdparanoia ffmpeg libdiscid0 python3-libdiscid wodim dvd+rw-tools udisks2
   ```

3. **Install Python dependencies** (recommended, for accurate metadata)
   ```bash
   pip3 install -r requirements.txt
   ```
   This installs `python-discid` and `musicbrainzngs`, which enable exact MusicBrainz disc-ID lookups (see [Metadata Support](#metadata-support)). Without them, X-ISO still works but falls back to less reliable lookup paths.

4. **Set your contact email** (required for metadata lookups)

   Open `X-ISO.py` and set:
   ```python
   CDDB_CONTACT_EMAIL = "your-email@example.com"
   ```
   Both MusicBrainz and GnuDB require a real, traceable contact identifier in API requests and will rate-limit or reject requests from generic/placeholder values. See [Metadata Support](#metadata-support) for details.

5. **Run the application**
   ```bash
   python3 X-ISO.py
   ```

### Windows

1. **Download the project files**

2. **Install Python 3.8+** from [python.org](https://www.python.org/)
   - Make sure to check "Add Python to PATH" during installation

3. **Install FFmpeg**
   - Download from [ffmpeg.org](https://ffmpeg.org/download.html)
   - Extract and add to system PATH

4. **Install cdparanoia**
   - Download a Windows build of cdparanoia and add it to system PATH
   - Required for the Rip Audio CD feature

5. **Install Python dependencies** (recommended)
   ```bash
   pip install -r requirements.txt
   ```

6. **Set your contact email** in `X-ISO.py` (see step 4 under Linux installation above)

7. **Run the application**
   ```bash
   python X-ISO.py
   ```

## Usage Guide

### Converting Disc Images

1. **Launch X-ISO** and go to the "Convert" tab
2. **Click "Browse..."** under "Source Image File"
3. **Select your image file** (DMG, BIN, NRG, etc.)
4. **Set output filename** with ".iso" extension
5. **Click "Convert to ISO"**
6. **Wait for completion** - progress bar shows status
7. **Success message** appears when conversion is complete

> Note: conversion currently copies the source file's bytes directly into the output `.iso`. For sources that are already ISO 9660 images this produces a valid result; for other container formats (DMG, NRG, BIN/CUE, etc.) real format translation isn't implemented yet — see [Implementation Status](#implementation-status).

### Ripping Audio CDs

1. **Insert an audio CD** into your CD drive
2. **Go to Tools > Rip Audio CD**
3. **Select your drive** (device path on Linux, e.g. `/dev/sr0`; drive letter on Windows)
4. **Click "Read CD"** — X-ISO reads the table of contents via `cdparanoia` and looks up metadata automatically (see below)
5. **Review the detected album/artist/tracks**, select which tracks to rip (default: all selected)
6. **Choose output format** (MP3, FLAC, WAV, AAC)
7. **Select output folder**
8. **Click "Start Ripping"** — each selected track is extracted with `cdparanoia` and (unless ripping to WAV) converted and tagged with `ffmpeg`
9. **Files are organized** as: `Artist/Album/Track Number - Title.ext`

### Converting Audio Files

1. **Go to Tools > Audio Converter**
2. **Click "Add Files..."** to select audio files
3. **Choose output format** (MP3, FLAC, WMA, etc.)
4. **Select quality/bitrate**
5. **Choose output folder**
6. **Click "Start Conversion"** — handled via `ffmpeg`

### Burning Discs

1. **Go to Tools > Burn** or click "Burn" tab
2. **Select image file** to burn
3. **Choose target drive** (auto-detected via `lsblk`, or type a device path manually)
4. **Choose media type** (CD, DVD, or BD) — determines whether `wodim`/`cdrecord` or `growisofs` is used
5. **Set options**: verify after burning (does a byte-for-byte compare against the disc after burning)
6. **Click "Burn Disc"** — progress and tool output stream live into the dialog

### Appending Data to a Disc

1. **Go to Tools > Append Data to Disc**
2. **Select target drive** (must be a non-finalized DVD±R(W)/BD — CD-R multisession append isn't supported)
3. **Add files** to append
4. **Click "Append to Disc"** — uses `growisofs -M` to write a new session

### Erasing a Rewritable Disc

1. **Go to Tools > Erase Rewritable Disc**
2. **Select drive** and **media type** (CD or DVD)
3. **Choose Quick or Full (Secure) erase**
4. **Click "Start Erasing"** — confirms before proceeding, since this is destructive

### Copying a Disc

1. **Go to Tools > Copy CD/DVD/Blu-ray**
2. **Select source and destination drives** (must be different)
3. **Choose destination media type** and **number of copies**
4. **Click "Start Copy"** — reads the source to a temporary image once, then burns it to the destination for each copy, prompting you to insert a blank disc between copies

### Making a Disc Image

1. **Go to Tools > Make CD/DVD/Blu-ray Image**
2. **Select source drive** and **output file**
3. **Choose format** — ISO is a straight `dd` read; BIN/CUE produces an approximate single-track rip; NRG falls back to ISO with a warning
4. **Click "Create Image"**

### Making a USB Drive Image

1. **Go to Tools > Make USB Drive Image**
2. **Select source USB drive** (auto-detected) and **output file**
3. **Click "Create Image"** — reads the entire drive via `dd`; can take a while depending on capacity

### Creating Bootable USB

1. **Go to Tools > Create Bootable USB**
2. **Select ISO image file**
3. **Choose target USB drive** (auto-detected; ⚠️ all data on it will be erased!)
4. **Partition scheme selector is informational** — the write is a direct `dd` of the ISO, which preserves whatever partition table the ISO already has (true for essentially all modern Linux distro ISOs)
5. **Click "Create Bootable USB"** — confirms before proceeding, since this is destructive

### Virtual Drive Management

1. **Go to Tools > Virtual Drive**
2. **Click "Browse..."** to select ISO image
3. **Click "Mount"** — sets up a loop device and mounts it via `udisksctl` (no root needed on a typical desktop setup)
4. **Select mounted drive** and click "Unmount" to eject and tear down the loop device

## Supported Formats

### Image Formats (Conversion)
- Apple: DMG
- Binary: BIN
- Nero: NRG
- CUE/BIN: CUE
- Media Descriptor: MDS
- Raw: IMG, DAO, TAO
- Universal: UDF
- DiscJuggler: CDI
- ISO: ISO, ISZ
- Others: VCD, TOAST, CIF, CCD, PCD

### Audio Formats (Ripping & Conversion)
**Input**: CD Audio (CDDA)
**Output**: MP3, WAV, FLAC, AAC, OGG, M4A, WMA, OPUS, APE

## Metadata Support

X-ISO resolves album/artist/year/track metadata through a prioritized chain of sources, falling back automatically if one fails:

1. **MusicBrainz (exact disc ID)** — *recommended, most reliable.* Requires the optional `python-discid` and `musicbrainzngs` packages. X-ISO uses `libdiscid` to compute the CD's real MusicBrainz disc ID directly from the drive and looks it up with an exact match.
2. **MusicBrainz (fuzzy TOC lookup)** — used automatically if `python-discid`/`musicbrainzngs` aren't installed, or the exact lookup finds nothing. Matches the disc by its track-offset table of contents instead of an exact disc ID.
3. **GnuDB** (FreeDB successor) — requires the app to be registered with GnuDB. New client applications must be pre-approved: email `info@gnudb.org` with your app name and contact email (see their [howto](https://gnudb.org/howto.php)). Until registered, GnuDB will reject requests with an "Unknown application" error — this is expected and not a bug in X-ISO.
4. **Direct CDDB query** (legacy servers) — a last-resort fallback with limited reliability, since most legacy FreeDB/CDDB mirrors are stale or discontinued.
5. **Offline fallback** — if every source fails, tracks are labeled generically (`Track 01`, `Track 02`, ...) so ripping can still proceed.

**Required configuration:** both MusicBrainz and GnuDB require a real, traceable contact identifier in their API requests (a descriptive `User-Agent` for MusicBrainz, a `hello` string for GnuDB) — generic or placeholder values get rate-limited or rejected. Set your real email in `X-ISO.py`:
```python
CDDB_CONTACT_EMAIL = "your-email@example.com"
```

Metadata is embedded in ripped audio files with proper ID3/format tags via `ffmpeg` (title, artist, album, track number, year where available).

## Troubleshooting

### "cdparanoia not found"
**Solution**: Install cdparanoia
```bash
# Linux
sudo apt-get install cdparanoia

# Windows: download a Windows cdparanoia build and add it to PATH — it's required for ripping, not optional
```

### "ffmpeg not found"
**Solution**: Install FFmpeg
```bash
# Linux
sudo apt-get install ffmpeg

# Windows: Download from ffmpeg.org
```

### cdparanoia times out reading the disc
This usually means one of:
- No audio CD is inserted (or it's a data/blank disc)
- Your user lacks permission to access the optical drive — add yourself to the `cdrom` group and log out/in:
  ```bash
  sudo usermod -aG cdrom $USER
  ```
- The device path is wrong — check with `ls -l /dev/sr*`
- The drive is genuinely slow to spin up on a cold read (the timeout is 30 seconds, which covers most drives)

X-ISO surfaces a specific reason for each of these rather than a generic timeout message.

### CD not detected
- Check that CD drive is accessible
- Verify CD is inserted correctly (audio CD, not data or blank)
- Try a different CD drive if available
- Check system permissions for CD drive access (see `cdrom` group note above)

### No metadata found for CD
- If using MusicBrainz: the disc may genuinely not be in MusicBrainz's database (uncommon for commercial releases, more likely for obscure/regional pressings)
- If using GnuDB: your app name may not yet be registered with them — see [Metadata Support](#metadata-support)
- Check `CDDB_CONTACT_EMAIL` is set to a real address, not the placeholder
- Check your internet connection
- Metadata will still allow ripping — tracks fall back to generic names (`Track 01`, etc.)

### Conversion fails
- Ensure source file is readable
- Check output folder has write permissions
- Verify sufficient disk space
- Check console output for detailed error messages

### Audio quality issues
- Use higher bitrate settings (320kbps for MP3)
- Use lossless formats (FLAC, WAV) for archival
- Ensure source audio is high quality

## File Organization

When ripping CDs, files are automatically organized:
```
Output Folder/
└── Artist Name/
    └── Album Title/
        ├── 01 - Track Title.mp3
        ├── 02 - Another Track.mp3
        └── ...
```

## Configuration

- `CDDB_CONTACT_EMAIL` in `X-ISO.py` — your real contact email, required for MusicBrainz and GnuDB lookups (see [Metadata Support](#metadata-support))
- Application settings (recent file paths, preferred output formats, quality settings, output folders) persist between sessions

## Performance Tips

1. **Use SSD for output**: Faster writing for large images
2. **Close other applications**: More system resources for conversion
3. **Use lossless formats**: Better for archival (FLAC, WAV)
4. **High bitrate audio**: 320kbps MP3 or FLAC for best quality

## Limitations

- Convert to ISO is currently a raw byte-copy, not true format-specific conversion (see [Implementation Status](#implementation-status))
- Burn/Append/Erase/Copy/Make Image/USB Image/Bootable USB/Virtual Drive are implemented for Linux only; Windows shows a clear "not implemented" error rather than simulating
- BIN/CUE image creation is an approximation (single MODE1/2048 track), not a true raw-sector rip; NRG creation falls back to ISO
- Bootable USB partition-scheme selector (MBR/GPT) is informational only — writing is a direct `dd` of the source ISO
- CD-R multisession append isn't supported (`growisofs -M` only works for DVD±R(W)/BD)
- These newly implemented tools haven't yet been verified against real hardware — see note in [Implementation Status](#implementation-status)
- Windows Media Player integration limited on Linux
- Some proprietary disc formats may not be supported
- Network-based CD drives have limited support
- Real-time audio streaming not supported
- GnuDB requires manual app registration (see [Metadata Support](#metadata-support))

## Requirements Summary

### Essential
- Python 3.6+
- tkinter
- FFmpeg
- cdparanoia (required for ripping on both Linux and Windows)

### Required for Burn/Append/Erase/Copy/Make Image/Virtual Drive (Linux only)
- `wodim` (or `cdrecord`)
- `dvd+rw-tools` (provides `growisofs`, `dvd+rw-format`)
- `udisks2` (provides `udisksctl`)
- `dd`, `lsblk` (standard on any Linux system — coreutils/util-linux)

### Recommended (for reliable metadata)
- python-discid
- musicbrainzngs
- libdiscid0 / python3-libdiscid (Linux system packages)

## License

MIT License - Feel free to use, modify, and distribute

## Contributing

Contributions are welcome! Please submit issues and pull requests.

## Support

For issues and feature requests, please visit the project repository or contact support.

---

**Version**: 2.0
**Last Updated**: August 30, 2026
**Platform**: Cross-Platform (Linux, Windows)
**Python Version**: 3.6+
