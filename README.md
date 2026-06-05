![X-ISO](docs/x-iso-banner.svg)
# X-ISO - Disc Image Converter & Burner

A comprehensive cross-platform disc image conversion and audio CD ripping utility with metadata support.

## Features

### Core Functionality
- **Convert Multiple Disc Image Formats**: DMG, BIN, NRG, CUE, MDS, IMG, ISO, ISZ, UDF, CDI, DAO, TAO, and more
- **Burn to Optical Media**: CD, DVD, and Blu-ray disc burning with verification
- **Virtual Drive Management**: Mount and unmount ISO images as virtual drives
- **Audio CD Ripping**: Full support for extracting audio CDs with automatic metadata lookup
- **Audio Conversion**: Convert between multiple audio formats (MP3, WAV, FLAC, AAC, OGG, M4A, WMA, OPUS, APE)

### Advanced Features
- **Automatic Metadata Retrieval**: Album info, artist names, and track titles from GnuDB
- **High-Quality Audio Extraction**: 320kbps MP3, lossless FLAC, and other format support
- **Organized File Structure**: Auto-creates Artist/Album folder hierarchy
- **Multi-Format Audio Support**: 9+ audio format conversions
- **USB Drive Imaging**: Create and manage USB drive images
- **Bootable USB Creation**: Create bootable USB drives with MBR/GPT support
- **Disc Copying**: Copy physical discs with verification
- **Disc Image Creation**: Create images from physical media
- **Disc Verification**: Verify disc integrity
- **Audio Ripper**: Extract audio tracks from CDs with metadata

## System Requirements

### Minimum Requirements
- **OS**: Linux (Linux Mint, Ubuntu, Debian, Fedora, etc.) or Windows
- **Python**: 3.6 or higher
- **RAM**: 2GB minimum
- **Storage**: 100MB free space for application + storage for images/audio

### Required External Tools

#### Linux
```bash
# Fedora/RHEL
sudo dnf install cdparanoia ffmpeg

# Ubuntu/Debian/Linux Mint
sudo apt-get install cdparanoia ffmpeg

# Arch
sudo pacman -S cdparanoia ffmpeg
```

#### Windows
- Download and install [FFmpeg](https://ffmpeg.org/download.html)
- Download and install [cdparanoia](https://www.xiph.org/paranoia/) (optional, for CD audio extraction)
- Add both to system PATH

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
   sudo apt-get update
   sudo apt-get install python3 python3-tk cdparanoia ffmpeg
   ```

3. **Install Python dependencies** (optional, for enhanced features)
   ```bash
   pip3 install -r requirements.txt
   ```

4. **Run the application**
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

4. **Install Python dependencies** (optional)
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the application**
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

### Ripping Audio CDs

1. **Insert an audio CD** into your CD drive
2. **Go to Tools > Rip Audio CD**
3. **Click "Read CD"** to detect tracks
4. **Metadata automatically retrieves** album, artist, and track names from GnuDB
5. **Select tracks** to rip (default: all selected)
6. **Choose output format** (MP3, FLAC, WAV, etc.)
7. **Select output folder**
8. **Click "Start Ripping"**
9. **Files are organized** as: `Artist/Album/Track Number - Title.mp3`

### Converting Audio Files

1. **Go to Tools > Audio Converter**
2. **Click "Add Files..."** to select audio files
3. **Choose output format** (MP3, FLAC, WMA, etc.)
4. **Select quality/bitrate**
5. **Choose output folder**
6. **Click "Start Conversion"**

### Burning Discs

1. **Go to Tools > Burn** or click "Burn" tab
2. **Select image file** to burn
3. **Choose target drive** (CD-RW, DVD-RW, Blu-ray)
4. **Set burn options**:
   - Verify data after burning
   - Finalize disc
   - Write speed
5. **Click "Burn Disc"**

### Creating Bootable USB

1. **Go to Tools > Create Bootable USB**
2. **Select ISO image file**
3. **Choose target USB drive** (⚠️ Warning: data will be erased!)
4. **Select partition scheme**:
   - MBR (BIOS/UEFI compatibility)
   - GPT (UEFI only)
5. **Choose file system** (FAT32, NTFS, exFAT)
6. **Click "Create Bootable USB"**

### Virtual Drive Management

1. **Go to Tools > Virtual Drive**
2. **Click "Browse..."** to select ISO image
3. **Click "Mount"** to mount as virtual drive
4. **Select mounted drive** and click "Unmount" to eject

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

The application automatically retrieves metadata from **GnuDB** (replacement for FreeDB) when ripping CDs:
- Album title
- Artist name
- Release year
- Individual track titles

Metadata is embedded in ripped audio files with proper ID3 tags.

## Troubleshooting

### "cdparanoia not found"
**Solution**: Install cdparanoia
```bash
# Linux
sudo apt-get install cdparanoia

# Windows: Use FFmpeg only (cdparanoia is optional)
```

### "ffmpeg not found"
**Solution**: Install FFmpeg
```bash
# Linux
sudo apt-get install ffmpeg

# Windows: Download from ffmpeg.org
```

### CD not detected
- Check that CD drive is accessible
- Verify CD is inserted correctly
- Try different CD drive if available
- Check system permissions for CD drive access

### No metadata found for CD
- CD may not be in GnuDB database
- Check internet connection (required for GnuDB lookup)
- Metadata will still be available for standard CDs (track numbers and durations)

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

All settings are saved in the application and persist between sessions:
- Recent file paths
- Preferred output formats
- Quality settings
- Output folders

## Performance Tips

1. **Use SSD for output**: Faster writing for large images
2. **Close other applications**: More system resources for conversion
3. **Use lossless formats**: Better for archival (FLAC, WAV)
4. **High bitrate audio**: 320kbps MP3 or FLAC for best quality

## Limitations

- Windows Media Player integration limited on Linux
- Some proprietary disc formats may not be supported
- Network-based CD drives have limited support
- Real-time audio streaming not supported

## Requirements Summary

### Essential
- Python 3.6+
- tkinter
- FFmpeg

### Optional (for CD audio extraction)
- cdparanoia

### Optional (for enhanced metadata)
- python-discid
- musicbrainzngs

## License

MIT License - Feel free to use, modify, and distribute

## Contributing

Contributions are welcome! Please submit issues and pull requests.

## Support

For issues and feature requests, please visit the project repository or contact support.

---

**Version**: 1.8  
**Last Updated**: June 5, 2026  
**Platform**: Cross-Platform (Linux, Windows)  
**Python Version**: 3.6+
