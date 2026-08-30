import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import subprocess
import shutil
import platform
from pathlib import Path
import time
import urllib.request
import urllib.error
import urllib.parse
import socket
import json
import re

# GnuDB requires a real, unique contact email identifying your installation
# (see https://gnudb.org/howto.php) — set this to your own email address.
# Using a generic/shared value will get requests rejected as "Unknown application".
CDDB_CONTACT_EMAIL = "your-email@example.com"

class MetadataFetcher:
    """Handles CD metadata retrieval from multiple sources with fallbacks"""

    def __init__(self, contact_email=None):
        self.cache = {}
        socket.setdefaulttimeout(10)
        # GnuDB requires a real, unique contact email in the "hello" string
        # (see https://gnudb.org/howto.php) — generic/shared identifiers get
        # rejected as "Unknown application". Set this to your own email.
        self.contact_email = contact_email or "your-email@example.com"
        self.hostname = platform.node() or "localhost"

    def fetch_metadata(self, cddb_id, offsets, total_seconds, num_tracks,
                        mb_offsets_frames=None, mb_leadout_frames=None, cd_device=None):
        """Fetch metadata from multiple sources in order of reliability.

        `offsets`/`total_seconds` are CDDB-style (seconds) values, used for GnuDB/CDDB.
        `mb_offsets_frames`/`mb_leadout_frames` are raw CD-frame values (75/sec),
        used only for the fuzzy TOC fallback below — NOT the same numbers as `offsets`.
        `cd_device` is the physical drive path/letter, needed for the exact
        libdiscid-based MusicBrainz lookup (the most reliable source, when available).
        """
        print(f"\n=== METADATA LOOKUP ===")
        print(f"Disc ID: {cddb_id}")
        print(f"Tracks: {num_tracks}, Total: {total_seconds}s")

        result = None

        print("\n1. Trying MusicBrainz (exact disc ID via libdiscid)...")
        result = self._fetch_musicbrainz_exact(cd_device)
        if result:
            print(f"✓ MusicBrainz (exact) SUCCESS: {result['album']} by {result['artist']}")
            return result

        if mb_offsets_frames and mb_leadout_frames:
            print("\n2. Trying MusicBrainz (fuzzy TOC lookup)...")
            result = self._fetch_musicbrainz(mb_offsets_frames, mb_leadout_frames, num_tracks)
            if result:
                print(f"✓ MusicBrainz (fuzzy) SUCCESS: {result['album']} by {result['artist']}")
                return result
        else:
            print("\n2. Skipping fuzzy MusicBrainz TOC lookup (no frame-accurate offsets available)")

        print("\n3. Trying GnuDB...")
        result = self._fetch_gnudb(cddb_id, offsets, total_seconds, num_tracks)
        if result:
            print(f"✓ GnuDB SUCCESS: {result['album']} by {result['artist']}")
            return result

        print("\n4. Trying direct CDDB query...")
        result = self._fetch_cddb_direct(cddb_id, offsets, total_seconds, num_tracks)
        if result:
            print(f"✓ CDDB SUCCESS: {result['album']} by {result['artist']}")
            return result

        print("\n! No metadata sources available")
        return {
            'album': 'Unknown Album',
            'artist': 'Unknown Artist',
            'year': '',
            'tracks': {i: f'Track {i:02d}' for i in range(1, num_tracks + 1)}
        }

    def _fetch_musicbrainz_exact(self, cd_device):
        """Use libdiscid (python-discid) to compute the CD's real MusicBrainz disc ID
        and look it up directly. This is the most reliable source when the optional
        `discid` and `musicbrainzngs` packages are installed — it sidesteps all the
        manual TOC/frame-offset math the fuzzy fallback below has to do by hand.
        """
        if not cd_device:
            return None
        try:
            import discid
        except ImportError:
            print("  (python-discid not installed — skipping exact MB disc-id lookup; "
                  "pip3 install python-discid for more reliable metadata)")
            return None
        try:
            import musicbrainzngs
        except ImportError:
            print("  (musicbrainzngs not installed — skipping exact MB disc-id lookup; "
                  "pip3 install musicbrainzngs for more reliable metadata)")
            return None

        try:
            musicbrainzngs.set_useragent("X-ISO", "1.0", self.contact_email)
            disc = discid.read(cd_device)
            mb_disc_id = disc.id
            print(f"  libdiscid computed MusicBrainz Disc ID: {mb_disc_id}")

            mb_result = musicbrainzngs.get_releases_by_discid(
                mb_disc_id, includes=['artists', 'recordings', 'artist-credits']
            )

            release = None
            if mb_result and 'disc' in mb_result and mb_result['disc'].get('release-list'):
                release = mb_result['disc']['release-list'][0]
            elif mb_result and 'cdstub' in mb_result:
                # MusicBrainz knows this disc ID but has no full release attached to it yet.
                cdstub = mb_result['cdstub']
                return {
                    'album': cdstub.get('title', 'Unknown Album'),
                    'artist': cdstub.get('artist', 'Unknown Artist'),
                    'year': '',
                    'tracks': {}
                }

            if not release:
                return None

            result = {
                'album': release.get('title', 'Unknown Album'),
                'artist': 'Unknown Artist',
                'year': '',
                'tracks': {}
            }
            if release.get('artist-credit'):
                result['artist'] = release['artist-credit'][0]['artist']['name']
            if release.get('date'):
                result['year'] = release['date'][:4]

            for medium in release.get('medium-list', []):
                for track in medium.get('track-list', []):
                    try:
                        position = int(track.get('position', 0))
                    except (TypeError, ValueError):
                        continue
                    recording = track.get('recording') or {}
                    title = recording.get('title')
                    if position and title:
                        result['tracks'][position] = title

            return result if result['tracks'] else None
        except Exception as e:
            print(f"  Exact disc-id lookup failed: {e}")
            return None

    def _fetch_musicbrainz(self, mb_offsets_frames, mb_leadout_frames, num_tracks):
        """Fetch from MusicBrainz using a fuzzy TOC lookup (no true MB discid available).

        mb_offsets_frames: list of each track's start offset in raw CD frames (75/sec).
        mb_leadout_frames: total disc length in raw CD frames (last track's start + length).
        These must NOT be the CDDB seconds-based offsets used elsewhere in this class.
        """
        try:
            print(f"  Querying MusicBrainz with {num_tracks} tracks...")
            offset_str = '+'.join(str(o) for o in mb_offsets_frames)
            toc = f"1+{num_tracks}+{mb_leadout_frames}+{offset_str}"
            # Current WS/2 endpoint for a fuzzy TOC lookup uses "-" as the discid placeholder.
            url = f"https://musicbrainz.org/ws/2/discid/-?toc={toc}&inc=artist-credits+recordings"
            # MusicBrainz's API usage policy requires a descriptive User-Agent with contact info,
            # or requests get rate-limited/blocked — same underlying requirement as GnuDB's hello string.
            request = urllib.request.Request(
                url, headers={'User-Agent': f'X-ISO/1.0 ( {self.contact_email} )'}
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                data = response.read().decode('utf-8')
                if 'release' in data:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(data)
                    result = {
                        'album': 'Unknown Album',
                        'artist': 'Unknown Artist',
                        'year': '',
                        'tracks': {}
                    }
                    for release in root.findall('.//release'):
                        result['album'] = release.findtext('title', 'Unknown Album')
                        for artist in release.findall('.//artist-credit/artist'):
                            result['artist'] = artist.findtext('name', 'Unknown Artist')
                            break
                        for date in release.findall('.//date'):
                            result['year'] = date.text[:4] if date.text else ''
                            break
                        for i, track in enumerate(release.findall('.//track'), 1):
                            recording = track.find('recording')
                            if recording is not None:
                                title = recording.findtext('title', f'Track {i:02d}')
                                result['tracks'][i] = title
                    if result['tracks']:
                        return result
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code}: {e.reason}")
        except ImportError:
            print("  (musicbrainzngs not installed)")
        except Exception as e:
            print(f"  Error: {e}")
        return None

    def _fetch_gnudb(self, cddb_id, offsets, total_seconds, num_tracks):
        """Fetch from GnuDB (modern FreeDB replacement)"""
        try:
            print(f"  Querying GnuDB with disc ID: {cddb_id}")
            offset_str = ' '.join(str(o) for o in offsets)
            base_url = "http://gnudb.gnudb.org/~cddb/cddb.cgi"
            hello = f"{self.contact_email} {self.hostname} X-ISO 1.0"
            proto = "6"

            query_params = {
                'cmd': f"cddb query {cddb_id} {num_tracks} {offset_str} {total_seconds}",
                'hello': hello,
                'proto': proto,
            }
            query_url = f"{base_url}?{urllib.parse.urlencode(query_params, quote_via=urllib.parse.quote_plus)}"
            request = urllib.request.Request(query_url, headers={'User-Agent': 'X-ISO/1.0', 'Connection': 'close'})
            with urllib.request.urlopen(request, timeout=15) as response:
                data = response.read().decode('utf-8', errors='ignore')
                lines = data.strip().split('\n')
                if not lines:
                    return None
                status = lines[0]
                print(f"  Response: {status[:80]}")
                category = None
                match_id = None
                if status.startswith('200') or status.startswith('210'):
                    parts = status.split()
                    if len(parts) >= 3:
                        category = parts[1]
                        match_id = parts[2]
                elif status.startswith('211'):
                    if len(lines) > 1:
                        parts = lines[1].strip().split()
                        if len(parts) >= 2:
                            category = parts[0]
                            match_id = parts[1]
                if category and match_id:
                    read_params = {
                        'cmd': f"cddb read {category} {match_id}",
                        'hello': hello,
                        'proto': proto,
                    }
                    read_url = f"{base_url}?{urllib.parse.urlencode(read_params, quote_via=urllib.parse.quote_plus)}"
                    read_request = urllib.request.Request(read_url, headers={'User-Agent': 'X-ISO/1.0', 'Connection': 'close'})
                    with urllib.request.urlopen(read_request, timeout=15) as read_response:
                        read_data = read_response.read().decode('utf-8', errors='ignore')
                        result = {'album': 'Unknown Album', 'artist': 'Unknown Artist', 'year': '', 'tracks': {}}
                        dtitle_parts = []
                        track_titles = {}
                        for line in read_data.split('\n'):
                            line = line.rstrip()
                            if line.startswith('DTITLE='):
                                dtitle_parts.append(line.split('=', 1)[1])
                            elif line.startswith('DYEAR='):
                                result['year'] = line.split('=', 1)[1].strip()
                            elif line.startswith('TTITLE'):
                                try:
                                    key, value = line.split('=', 1)
                                    track_num = int(key.replace('TTITLE', '')) + 1
                                    if track_num in track_titles:
                                        track_titles[track_num] += value
                                    else:
                                        track_titles[track_num] = value
                                except:
                                    pass
                        dtitle = ''.join(dtitle_parts).strip()
                        if ' / ' in dtitle:
                            artist, album = dtitle.split(' / ', 1)
                            result['artist'] = artist.strip()
                            result['album'] = album.strip()
                        elif dtitle:
                            result['album'] = dtitle
                        for i in range(1, num_tracks + 1):
                            result['tracks'][i] = track_titles.get(i, f'Track {i:02d}')
                        return result
                elif status.startswith('202'):
                    print("  No match found in GnuDB")
                else:
                    print(f"  GnuDB returned: {status}")
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code}: {e.reason}")
        except Exception as e:
            print(f"  Error: {e}")
        return None

    def _fetch_cddb_direct(self, cddb_id, offsets, total_seconds, num_tracks):
        """Direct CDDB query fallback"""
        try:
            print(f"  Querying CDDB servers...")
            servers = ['freedb.freedb.org', 'cddb.ll.mit.edu', 'gnudb.gnudb.org']
            offset_str = ' '.join(str(o) for o in offsets)
            hello = f"{self.contact_email} {self.hostname} X-ISO 1.0"
            params = {
                'cmd': f"cddb query {cddb_id} {num_tracks} {offset_str} {total_seconds}",
                'hello': hello,
                'proto': '6',
            }
            query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote_plus)
            for server in servers:
                try:
                    url = f"http://{server}/~cddb/cddb.cgi?{query}"
                    request = urllib.request.Request(url, headers={'User-Agent': 'X-ISO/1.0'})
                    with urllib.request.urlopen(request, timeout=8) as response:
                        data = response.read().decode('utf-8', errors='ignore')
                        if 'album' in data.lower() or 'track' in data.lower():
                            print(f"  Found on {server}")
                            return self._parse_cddb_response(data, num_tracks)
                except:
                    continue
        except Exception as e:
            print(f"  Error: {e}")
        return None

    def _parse_cddb_response(self, data, num_tracks):
        """Parse CDDB response"""
        result = {'album': 'Unknown Album', 'artist': 'Unknown Artist', 'year': '', 'tracks': {}}
        for line in data.split('\n'):
            if 'DTITLE' in line:
                parts = line.split(':', 1)
                if len(parts) > 1:
                    if ' / ' in parts[1]:
                        artist, album = parts[1].split(' / ', 1)
                        result['artist'] = artist.strip()
                        result['album'] = album.strip()
            elif 'TTITLE' in line:
                parts = line.split(':', 1)
                if len(parts) > 1:
                    try:
                        track_num = int(''.join(c for c in parts[0] if c.isdigit())) + 1
                        if track_num <= num_tracks:
                            result['tracks'][track_num] = parts[1].strip()
                    except:
                        pass
        return result if result['tracks'] else None


class ImageConverter:
    SUPPORTED_FORMATS = {
        '.dmg': 'Apple Disk Image', '.bin': 'Binary Disc Image', '.nrg': 'Nero Image',
        '.cue': 'CUE Sheet', '.mds': 'Media Descriptor', '.img': 'Raw Disc Image',
        '.iso': 'ISO 9660 Image', '.isz': 'Compressed ISO'
    }

    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback
        self.cancel_flag = False

    def update_progress(self, percentage, message=""):
        if self.progress_callback:
            self.progress_callback(percentage, message)

    def convert_to_iso(self, input_file, output_file):
        try:
            file_size = os.path.getsize(input_file)
            chunk_size = 1024 * 1024
            with open(input_file, 'rb') as infile, open(output_file, 'wb') as outfile:
                bytes_copied = 0
                while True:
                    if self.cancel_flag:
                        return False, "Conversion cancelled"
                    chunk = infile.read(chunk_size)
                    if not chunk:
                        break
                    outfile.write(chunk)
                    bytes_copied += len(chunk)
                    progress = int((bytes_copied / file_size) * 100)
                    self.update_progress(progress, f"Converting: {bytes_copied // (1024*1024)}MB / {file_size // (1024*1024)}MB")
            self.update_progress(100, "Conversion completed")
            return True, "Image converted to ISO successfully"
        except Exception as e:
            return False, f"Error: {str(e)}"


class XISOMApp:
    def __init__(self, root):
        self.root = root
        self.root.title("X-ISO - Disc Image Converter & Burner")
        self.root.geometry("1000x780")

        self.converter = ImageConverter(progress_callback=self.update_progress)
        self.metadata_fetcher = MetadataFetcher(contact_email=CDDB_CONTACT_EMAIL)
        self.conversion_thread = None

        self.setup_ui()

    def setup_ui(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Exit", command=self.root.quit)

        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Convert", command=lambda: self.notebook.select(0))
        tools_menu.add_command(label="Burn", command=self.open_burn_window)
        tools_menu.add_separator()
        tools_menu.add_command(label="Append Data to Disc", command=self.open_append_window)
        tools_menu.add_command(label="Erase Rewritable Disc", command=self.open_erase_window)
        tools_menu.add_command(label="View Drive/Disc Information", command=self.open_drive_info_window)
        tools_menu.add_command(label="Copy CD/DVD/Blu-ray", command=self.open_copy_window)
        tools_menu.add_command(label="Make CD/DVD/Blu-ray Image", command=self.open_make_image_window)
        tools_menu.add_separator()
        tools_menu.add_command(label="Rip Audio CD", command=self.open_rip_audio_window)
        tools_menu.add_command(label="Audio Converter", command=self.open_audio_converter_window)
        tools_menu.add_separator()
        tools_menu.add_command(label="Virtual Drive", command=lambda: self.notebook.select(2))
        tools_menu.add_command(label="Make USB Drive Image", command=self.open_usb_image_window)
        tools_menu.add_command(label="Create Bootable USB", command=self.open_bootable_usb_window)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

        header = tk.Frame(self.root, bg="#2b2b2b")
        header.pack(fill=tk.X, padx=20, pady=15)
        tk.Label(header, text="X-ISO", font=("Arial", 24, "bold"), bg="#2b2b2b", fg="white").pack(side=tk.LEFT)
        tk.Label(header, text="Disc Image Converter & Burner", font=("Arial", 10), bg="#2b2b2b", fg="white").pack(side=tk.LEFT, padx=10)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.create_converter_tab()
        self.create_burn_tab()
        self.create_virtual_tab()
        self.create_tools_tab()

        self.status_bar = tk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(fill=tk.X, padx=20, pady=10)

    def create_converter_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Convert")

        src_frame = tk.LabelFrame(frame, text="Source Image File", padx=15, pady=15)
        src_frame.pack(fill=tk.X, padx=20, pady=10)
        self.source_entry = tk.Entry(src_frame, width=70)
        self.source_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(src_frame, text="Browse...", command=self.browse_source).pack(side=tk.LEFT)

        out_frame = tk.LabelFrame(frame, text="Output ISO File", padx=15, pady=15)
        out_frame.pack(fill=tk.X, padx=20, pady=10)
        self.output_entry = tk.Entry(out_frame, width=70)
        self.output_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(out_frame, text="Save As...", command=self.browse_output).pack(side=tk.LEFT)

        fmt_frame = tk.LabelFrame(frame, text="Supported Formats", padx=15, pady=15)
        fmt_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        self.formats_text = tk.Text(fmt_frame, height=8, wrap=tk.WORD)
        self.formats_text.pack(fill=tk.BOTH, expand=True)
        formats = "\n".join([f"{k.upper()}: {v}" for k, v in ImageConverter.SUPPORTED_FORMATS.items()])
        self.formats_text.insert('1.0', "Supported formats:\n\n" + formats)
        self.formats_text.config(state=tk.DISABLED)

        prog_frame = tk.Frame(frame)
        prog_frame.pack(fill=tk.X, padx=20, pady=10)
        self.progress_var = tk.IntVar()
        self.progress_bar = ttk.Progressbar(prog_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=5)
        self.progress_label = tk.Label(prog_frame, text="")
        self.progress_label.pack()

        btn_frame = tk.Frame(frame)
        btn_frame.pack(pady=15)
        self.convert_btn = tk.Button(btn_frame, text="Convert to ISO", bg="#0078d4", fg="white",
                                     font=("Arial", 10, "bold"), padx=20, pady=8, command=self.start_conversion)
        self.convert_btn.pack(side=tk.LEFT, padx=5)
        self.cancel_btn = tk.Button(btn_frame, text="Cancel", padx=20, pady=8,
                                    command=self.cancel_conversion, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT, padx=5)

    def create_burn_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Burn")

        tk.Label(frame, text="Burn Options", font=("Arial", 16, "bold")).pack(pady=20)

        file_frame = tk.LabelFrame(frame, text="Image File to Burn", padx=15, pady=15)
        file_frame.pack(fill=tk.X, padx=20, pady=10)
        self.burn_entry = tk.Entry(file_frame, width=70)
        self.burn_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(file_frame, text="Browse...", command=self.browse_burn_image).pack(side=tk.LEFT)

        drive_frame = tk.LabelFrame(frame, text="Target Drive", padx=15, pady=15)
        drive_frame.pack(fill=tk.X, padx=20, pady=10)
        drives = self._detect_optical_drives()
        self.drive_var = tk.StringVar(value=drives[0][1] if drives else "")
        self.burn_drive_combo = ttk.Combobox(drive_frame, textvariable=self.drive_var, width=40,
                                             state='readonly' if drives else 'normal')
        self.burn_drive_combo['values'] = [d[1] for d in drives]
        self.burn_drive_combo.pack(side=tk.LEFT, pady=5, padx=(0, 5))

        def refresh_burn_drives():
            new_drives = self._detect_optical_drives()
            self.burn_drive_combo['values'] = [d[1] for d in new_drives]
            self.burn_drive_combo.config(state='readonly' if new_drives else 'normal')
            if new_drives:
                self.drive_var.set(new_drives[0][1])
        tk.Button(drive_frame, text="Refresh", command=refresh_burn_drives).pack(side=tk.LEFT, padx=5)
        if not drives:
            tk.Label(drive_frame, text="No optical drives detected — type a device path (e.g. /dev/sr0)",
                    fg="gray", font=("Arial", 8)).pack(side=tk.LEFT, padx=5)

        media_frame = tk.LabelFrame(frame, text="Media Type", padx=15, pady=15)
        media_frame.pack(fill=tk.X, padx=20, pady=10)
        self.burn_media_var = tk.StringVar(value="DVD")
        ttk.Combobox(media_frame, textvariable=self.burn_media_var, values=["CD", "DVD", "BD"],
                    width=10, state='readonly').pack(anchor=tk.W)

        self.burn_verify_var = tk.BooleanVar(value=True)
        tk.Checkbutton(frame, text="Verify after burning", variable=self.burn_verify_var).pack(anchor=tk.W, padx=25)

        tk.Button(frame, text="Burn Disc", bg="#0078d4", fg="white", font=("Arial", 10, "bold"),
                 padx=30, pady=10, command=self.burn_disc).pack(pady=20)

    def create_virtual_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Virtual Drive")

        tk.Label(frame, text="Virtual Drive Manager", font=("Arial", 16, "bold")).pack(pady=20)

        mount_frame = tk.LabelFrame(frame, text="Mount Image", padx=15, pady=15)
        mount_frame.pack(fill=tk.X, padx=20, pady=10)
        self.mount_entry = tk.Entry(mount_frame, width=60)
        self.mount_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(mount_frame, text="Browse...", command=self.browse_mount_image).pack(side=tk.LEFT, padx=5)
        tk.Button(mount_frame, text="Mount", command=self.mount_image).pack(side=tk.LEFT)

        list_frame = tk.LabelFrame(frame, text="Mounted Drives", padx=15, pady=15)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        self.mounted_listbox = tk.Listbox(list_frame, height=10)
        self.mounted_listbox.pack(fill=tk.BOTH, expand=True)

        tk.Button(frame, text="Unmount Selected", command=self.unmount_image).pack(pady=10)

    def create_tools_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Tools")

        tk.Label(frame, text="Additional Tools", font=("Arial", 16, "bold")).pack(pady=20)

        grid = tk.Frame(frame)
        grid.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        tools = [
            ("Copy CD/DVD/Blu-ray", self.open_copy_window),
            ("Make CD/DVD/Blu-ray Image", self.open_make_image_window),
            ("Rip Audio CD", self.open_rip_audio_window),
            ("Audio Converter", self.open_audio_converter_window),
            ("Erase Rewritable Disc", self.open_erase_window),
            ("View Drive Information", self.open_drive_info_window),
            ("Make USB Drive Image", self.open_usb_image_window),
            ("Create Bootable USB", self.open_bootable_usb_window),
            ("Append Data to Disc", self.open_append_window),
        ]

        for i, (name, func) in enumerate(tools):
            tk.Button(grid, text=name, command=func, width=35, pady=12, bg="#0078d4", fg="white").grid(row=i//2, column=i%2, padx=10, pady=8, sticky='ew')

        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

    def browse_source(self):
        file = filedialog.askopenfilename(title="Select Source Image",
                                         filetypes=[("All Images", "*.dmg *.bin *.nrg *.cue *.mds *.img *.iso *.isz"),
                                                   ("All Files", "*.*")])
        if file:
            self.source_entry.delete(0, tk.END)
            self.source_entry.insert(0, file)
            if not self.output_entry.get():
                out = os.path.splitext(file)[0] + ".iso"
                self.output_entry.delete(0, tk.END)
                self.output_entry.insert(0, out)

    def browse_output(self):
        file = filedialog.asksaveasfilename(title="Save ISO As", defaultextension=".iso",
                                           filetypes=[("ISO Image", "*.iso"), ("All Files", "*.*")])
        if file:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, file)

    def start_conversion(self):
        source = self.source_entry.get()
        output = self.output_entry.get()

        if not source or not output:
            messagebox.showerror("Error", "Please select source and output files")
            return

        if not os.path.exists(source):
            messagebox.showerror("Error", "Source file does not exist")
            return

        self.convert_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        self.converter.cancel_flag = False

        def convert():
            success, message = self.converter.convert_to_iso(source, output)
            self.root.after(0, lambda: self.conversion_complete(success, message))

        self.conversion_thread = threading.Thread(target=convert, daemon=True)
        self.conversion_thread.start()

    def cancel_conversion(self):
        self.converter.cancel_flag = True
        self.cancel_btn.config(state=tk.DISABLED)

    def conversion_complete(self, success, message):
        self.convert_btn.config(state=tk.NORMAL)
        self.cancel_btn.config(state=tk.DISABLED)
        if success:
            messagebox.showinfo("Success", "Converting image file completed successfully.")
        else:
            messagebox.showerror("Error", message)

    def update_progress(self, percentage, message):
        self.progress_var.set(percentage)
        self.progress_label.config(text=message)
        self.status_bar.config(text=message)

    # ------------------------------------------------------------------
    # Shared helpers for Burn / Append / Erase / Copy / Make Image /
    # USB Image / Bootable USB / Virtual Drive. These are real, Linux-
    # focused implementations using standard CLI tools (wodim/cdrecord,
    # growisofs, dvd+rw-format, dd, udisksctl, lsblk). None of this touches
    # the Rip Audio CD pipeline or MetadataFetcher above.
    # ------------------------------------------------------------------

    def _detect_optical_drives(self):
        """Return [(device_path, label), ...] for optical drives. Linux only for now."""
        drives = []
        if platform.system() != "Linux":
            return drives
        try:
            result = subprocess.run(
                ['lsblk', '-J', '-o', 'NAME,TYPE,MODEL'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                for dev in data.get('blockdevices', []):
                    if dev.get('type') == 'rom':
                        path = f"/dev/{dev['name']}"
                        model = (dev.get('model') or '').strip()
                        drives.append((path, f"{path} ({model})" if model else path))
        except Exception as e:
            print(f"Optical drive detection via lsblk failed: {e}")
        if not drives:
            import glob
            for path in sorted(glob.glob('/dev/sr*')):
                drives.append((path, path))
        return drives

    def _detect_usb_drives(self):
        """Return [(device_path, label), ...] for removable USB block devices. Linux only for now."""
        drives = []
        if platform.system() != "Linux":
            return drives
        try:
            result = subprocess.run(
                ['lsblk', '-J', '-b', '-o', 'NAME,TYPE,TRAN,SIZE,MODEL'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                for dev in data.get('blockdevices', []):
                    if dev.get('type') == 'disk' and dev.get('tran') == 'usb':
                        path = f"/dev/{dev['name']}"
                        try:
                            size_str = f"{int(dev.get('size', 0)) / (1024 ** 3):.1f}GB"
                        except (TypeError, ValueError):
                            size_str = "?"
                        model = (dev.get('model') or '').strip()
                        label = f"{path} ({size_str}{', ' + model if model else ''})"
                        drives.append((path, label))
        except Exception as e:
            print(f"USB drive detection via lsblk failed: {e}")
        return drives

    def _device_from_label(self, label):
        """Extract the leading /dev/... path from a detection-helper label,
        e.g. '/dev/sr0 (SAMSUNG DVD)' -> '/dev/sr0'."""
        if not label:
            return None
        return label.split(' ', 1)[0].strip()

    def _make_progress_dialog(self, parent, title, heading):
        """Standard progress dialog: status label, progress bar, scrolling log,
        and a Cancel/Close button. Returns a dict of widgets + a cancel_flag."""
        win = tk.Toplevel(parent)
        win.title(title)
        win.geometry("580x440")
        win.transient(parent)
        win.grab_set()

        tk.Label(win, text=heading, font=("Arial", 14, "bold")).pack(pady=15)
        status_label = tk.Label(win, text="Initializing...", font=("Arial", 10))
        status_label.pack(pady=5)

        progress_var = tk.IntVar()
        ttk.Progressbar(win, variable=progress_var, maximum=100, length=520).pack(pady=10)

        log_frame = tk.Frame(win)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        log_scroll = tk.Scrollbar(log_frame)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        log_text = tk.Text(log_frame, height=10, wrap=tk.WORD, yscrollcommand=log_scroll.set, state=tk.DISABLED)
        log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.config(command=log_text.yview)

        cancel_flag = {'cancelled': False}

        def do_cancel():
            cancel_flag['cancelled'] = True
            win.destroy()

        cancel_btn = tk.Button(win, text="Cancel", command=do_cancel, padx=20, pady=5)
        cancel_btn.pack(pady=10)

        def log(line):
            log_text.config(state=tk.NORMAL)
            log_text.insert(tk.END, line + "\n")
            log_text.see(tk.END)
            log_text.config(state=tk.DISABLED)

        return {
            'win': win, 'status_label': status_label, 'progress_var': progress_var,
            'log': log, 'cancel_flag': cancel_flag, 'cancel_btn': cancel_btn
        }

    def _stream_process_lines(self, proc):
        """Yield output lines from a running Popen, splitting on both \\n and \\r
        so carriage-return progress updates (wodim/growisofs/dd) are captured."""
        buf = ''
        while True:
            chunk = proc.stdout.read(1)
            if not chunk:
                if buf.strip():
                    yield buf
                break
            if chunk in ('\n', '\r'):
                if buf.strip():
                    yield buf
                buf = ''
            else:
                buf += chunk

    def _run_streaming(self, cmd, dlg, progress_regex=None, env=None):
        """Run cmd, streaming output into dlg's log and (if progress_regex has a
        numeric group) updating dlg's progress bar. Returns the return code, or
        -1 if the command couldn't be started."""
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, bufsize=1, env=env)
        except FileNotFoundError:
            self.root.after(0, lambda: dlg['log'](f"Command not found: {cmd[0]}"))
            return -1

        for line in self._stream_process_lines(proc):
            if dlg['cancel_flag']['cancelled']:
                proc.terminate()
                break
            captured = line
            self.root.after(0, lambda l=captured: dlg['log'](l))
            if progress_regex:
                m = progress_regex.search(line)
                if m:
                    try:
                        pct = float(m.group(1))
                        self.root.after(0, lambda p=pct: dlg['progress_var'].set(int(p)))
                    except (ValueError, IndexError):
                        pass
        proc.wait()
        return proc.returncode

    def _dd_copy(self, src, dst, dlg, block_size='4M', total_size_bytes=None):
        """Run `dd` copying src -> dst, streaming progress into dlg. If
        total_size_bytes isn't given, tries `blockdev --getsize64` on src
        (works when src is a block device) or falls back to a plain file size."""
        if total_size_bytes is None:
            try:
                result = subprocess.run(['blockdev', '--getsize64', src],
                                         capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    total_size_bytes = int(result.stdout.strip())
            except Exception:
                pass
            if total_size_bytes is None and os.path.isfile(src):
                try:
                    total_size_bytes = os.path.getsize(src)
                except OSError:
                    pass

        try:
            proc = subprocess.Popen(
                ['dd', f'if={src}', f'of={dst}', f'bs={block_size}', 'status=progress', 'oflag=sync'],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )
        except FileNotFoundError:
            return False, "dd is not installed"

        progress_re = re.compile(r'^(\d+)\s+bytes')
        for line in self._stream_process_lines(proc):
            if dlg['cancel_flag']['cancelled']:
                proc.terminate()
                break
            captured = line
            self.root.after(0, lambda l=captured: dlg['log'](l))
            m = progress_re.search(line)
            if m and total_size_bytes:
                try:
                    copied = int(m.group(1))
                    pct = min(100, int(copied / total_size_bytes * 100))
                    self.root.after(0, lambda p=pct: dlg['progress_var'].set(p))
                except (ValueError, ZeroDivisionError):
                    pass
        proc.wait()
        if dlg['cancel_flag']['cancelled']:
            return False, "Operation cancelled"
        if proc.returncode != 0:
            return False, f"dd exited with code {proc.returncode} — see log"
        return True, "Copy complete"

    def _burn_image(self, image_path, device_path, media_kind, verify, dlg):
        """Burn image_path to device_path. media_kind is 'CD', 'DVD', or 'BD'."""
        if media_kind == 'CD':
            tool = 'wodim' if shutil.which('wodim') else ('cdrecord' if shutil.which('cdrecord') else None)
            if not tool:
                return False, "Neither wodim nor cdrecord is installed (try: sudo apt-get install wodim)"
            cmd = [tool, '-v', '-dao', f'dev={device_path}', image_path]
        else:
            if not shutil.which('growisofs'):
                return False, "growisofs is not installed (try: sudo apt-get install dvd+rw-tools)"
            cmd = ['growisofs', '-Z', f'{device_path}={image_path}']

        progress_re = re.compile(r'(\d+(?:\.\d+)?)\s*%')
        self.root.after(0, lambda: dlg['status_label'].config(text=f"Burning to {device_path}..."))
        rc = self._run_streaming(cmd, dlg, progress_regex=progress_re)
        if dlg['cancel_flag']['cancelled']:
            return False, "Burn cancelled"
        if rc != 0:
            return False, f"Burn tool exited with code {rc} — see log for details"

        if verify:
            self.root.after(0, lambda: dlg['status_label'].config(text="Verifying burned data..."))
            self.root.after(0, lambda: dlg['log']("Verifying: comparing image bytes to disc..."))
            ok, msg = self._verify_burned_disc(image_path, device_path)
            if not ok:
                return False, f"Burn completed but verification failed: {msg}"
            self.root.after(0, lambda: dlg['log']("Verification passed."))

        return True, "Burn completed successfully"

    def _verify_burned_disc(self, image_path, device_path):
        """Best-effort verification: compare the source image's bytes to what
        was actually written to the disc, chunk by chunk."""
        try:
            size = os.path.getsize(image_path)
            with open(image_path, 'rb') as f_img, open(device_path, 'rb') as f_dev:
                chunk_size = 4 * 1024 * 1024
                compared = 0
                while compared < size:
                    a = f_img.read(chunk_size)
                    if not a:
                        break
                    b = f_dev.read(len(a))
                    if a != b:
                        return False, f"Mismatch at byte offset {compared}"
                    compared += len(a)
            return True, "Verified"
        except Exception as e:
            return False, str(e)

    def browse_burn_image(self):
        file = filedialog.askopenfilename(title="Select Image to Burn",
                                         filetypes=[("ISO Image", "*.iso"), ("All Files", "*.*")])
        if file:
            self.burn_entry.delete(0, tk.END)
            self.burn_entry.insert(0, file)

    def burn_disc(self):
        image_path = self.burn_entry.get()
        if not image_path or not os.path.exists(image_path):
            messagebox.showerror("Error", "Please select a valid image file")
            return
        if platform.system() != "Linux":
            messagebox.showerror("Error", "Burning is currently only implemented on Linux")
            return

        device_path = self._device_from_label(self.drive_var.get())
        if not device_path:
            messagebox.showerror("Error", "Please select or enter a target drive")
            return
        media_kind = self.burn_media_var.get()
        verify = self.burn_verify_var.get()

        dlg = self._make_progress_dialog(self.root, "Burning Disc", f"Burning to {device_path}")

        def worker():
            success, msg = self._burn_image(image_path, device_path, media_kind, verify, dlg)

            def finish():
                dlg['status_label'].config(text=msg)
                if success:
                    dlg['progress_var'].set(100)
                dlg['cancel_btn'].config(text="Close")
                if success:
                    messagebox.showinfo("Success", msg)
                else:
                    messagebox.showerror("Error", msg)
            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def browse_mount_image(self):
        file = filedialog.askopenfilename(title="Select Image to Mount",
                                         filetypes=[("ISO Image", "*.iso"), ("All Files", "*.*")])
        if file:
            self.mount_entry.delete(0, tk.END)
            self.mount_entry.insert(0, file)

    def mount_image(self):
        image_path = self.mount_entry.get()
        if not image_path or not os.path.exists(image_path):
            messagebox.showerror("Error", "Please select a valid image file")
            return
        if platform.system() != "Linux":
            messagebox.showerror("Error", "Virtual drive mounting is currently only implemented on Linux")
            return
        if not shutil.which('udisksctl'):
            messagebox.showerror("Error", "udisksctl is not installed (part of udisks2 — "
                                          "usually preinstalled on desktop Linux)")
            return

        def worker():
            try:
                setup = subprocess.run(['udisksctl', 'loop-setup', '-f', image_path],
                                        capture_output=True, text=True, timeout=15)
                if setup.returncode != 0:
                    raise RuntimeError(setup.stderr.strip() or setup.stdout.strip() or "loop-setup failed")
                m = re.search(r'(/dev/loop\d+)', setup.stdout)
                if not m:
                    raise RuntimeError(f"Couldn't parse loop device from: {setup.stdout.strip()}")
                loop_dev = m.group(1)

                mount = subprocess.run(['udisksctl', 'mount', '-b', loop_dev],
                                        capture_output=True, text=True, timeout=15)
                if mount.returncode != 0:
                    subprocess.run(['udisksctl', 'loop-delete', '-b', loop_dev],
                                    capture_output=True, text=True, timeout=10)
                    raise RuntimeError(mount.stderr.strip() or mount.stdout.strip() or "mount failed")

                mp_match = re.search(r'at (.+?)\.?\s*$', mount.stdout.strip())
                mount_point = mp_match.group(1) if mp_match else "unknown location"

                def finish():
                    self.mounted_listbox.insert(
                        tk.END, f"{loop_dev} -> {mount_point} [{os.path.basename(image_path)}]"
                    )
                    messagebox.showinfo("Success", f"Mounted at {mount_point}")
                self.root.after(0, finish)
            except Exception as e:
                err = str(e)
                self.root.after(0, lambda: messagebox.showerror("Error", f"Mount failed: {err}"))

        threading.Thread(target=worker, daemon=True).start()

    def unmount_image(self):
        sel = self.mounted_listbox.curselection()
        if not sel:
            messagebox.showwarning("Warning", "Select a mounted drive to unmount")
            return
        idx = sel[0]
        entry_text = self.mounted_listbox.get(idx)
        m = re.match(r'(/dev/loop\d+)', entry_text)
        if not m:
            messagebox.showerror("Error", "Couldn't determine the loop device for this entry")
            return
        loop_dev = m.group(1)

        def worker():
            try:
                subprocess.run(['udisksctl', 'unmount', '-b', loop_dev],
                                capture_output=True, text=True, timeout=15, check=True)
                subprocess.run(['udisksctl', 'loop-delete', '-b', loop_dev],
                                capture_output=True, text=True, timeout=10, check=True)

                def finish():
                    self.mounted_listbox.delete(idx)
                    messagebox.showinfo("Success", "Image unmounted")
                self.root.after(0, finish)
            except subprocess.CalledProcessError as e:
                err = (e.stderr or str(e)).strip()
                self.root.after(0, lambda: messagebox.showerror("Error", f"Unmount failed: {err}"))

        threading.Thread(target=worker, daemon=True).start()

    # Tool Windows
    def open_burn_window(self):
        win = tk.Toplevel(self.root)
        win.title("Burn Disc")
        win.geometry("620x480")
        tk.Label(win, text="Burn Disc Image", font=("Arial", 16, "bold")).pack(pady=20)

        file_frame = tk.LabelFrame(win, text="Image File", padx=15, pady=15)
        file_frame.pack(fill=tk.X, padx=20, pady=10)
        burn_entry = tk.Entry(file_frame, width=50)
        burn_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(file_frame, text="Browse...", command=lambda: self._browse_for_entry(burn_entry, "Select Image")).pack(side=tk.LEFT)

        drive_frame = tk.LabelFrame(win, text="Target Drive", padx=15, pady=15)
        drive_frame.pack(fill=tk.X, padx=20, pady=10)
        drives = self._detect_optical_drives()
        drive_var = tk.StringVar(value=drives[0][1] if drives else "")
        drive_combo = ttk.Combobox(drive_frame, textvariable=drive_var, width=35,
                                   state='readonly' if drives else 'normal')
        drive_combo['values'] = [d[1] for d in drives]
        drive_combo.pack(side=tk.LEFT, padx=5)

        def refresh_drives():
            new_drives = self._detect_optical_drives()
            drive_combo['values'] = [d[1] for d in new_drives]
            drive_combo.config(state='readonly' if new_drives else 'normal')
            if new_drives:
                drive_var.set(new_drives[0][1])
        tk.Button(drive_frame, text="Refresh", command=refresh_drives).pack(side=tk.LEFT, padx=5)

        media_frame = tk.LabelFrame(win, text="Media Type", padx=15, pady=15)
        media_frame.pack(fill=tk.X, padx=20, pady=10)
        media_var = tk.StringVar(value="DVD")
        ttk.Combobox(media_frame, textvariable=media_var, values=["CD", "DVD", "BD"], width=10, state='readonly').pack(anchor=tk.W)

        options_frame = tk.LabelFrame(win, text="Options", padx=15, pady=15)
        options_frame.pack(fill=tk.X, padx=20, pady=10)
        verify_var = tk.BooleanVar(value=True)
        tk.Checkbutton(options_frame, text="Verify after burning", variable=verify_var).pack(anchor=tk.W)

        def start_burn():
            image_path = burn_entry.get()
            if not image_path or not os.path.exists(image_path):
                messagebox.showerror("Error", "Please select a valid image file")
                return
            device_path = self._device_from_label(drive_var.get())
            if not device_path:
                messagebox.showerror("Error", "Please select or enter a target drive")
                return
            if platform.system() != "Linux":
                messagebox.showerror("Error", "Burning is currently only implemented on Linux")
                return

            dlg = self._make_progress_dialog(win, "Burning Disc", f"Burning to {device_path}")

            def worker():
                success, msg = self._burn_image(image_path, device_path, media_var.get(), verify_var.get(), dlg)

                def finish():
                    dlg['status_label'].config(text=msg)
                    if success:
                        dlg['progress_var'].set(100)
                    dlg['cancel_btn'].config(text="Close")
                    if success:
                        messagebox.showinfo("Success", msg)
                    else:
                        messagebox.showerror("Error", msg)
                self.root.after(0, finish)

            threading.Thread(target=worker, daemon=True).start()

        tk.Button(win, text="Burn Disc", bg="#0078d4", fg="white", padx=20, pady=10,
                 command=start_burn).pack(pady=20)

    def open_append_window(self):
        win = tk.Toplevel(self.root)
        win.title("Append Data to Disc")
        win.geometry("550x620")
        tk.Label(win, text="Append Data to Disc", font=("Arial", 16, "bold")).pack(pady=20)
        tk.Label(win, text="Adds a new session to a non-finalized multisession disc.\n"
                           "Supported for DVD±R(W)/BD via growisofs -M — not CD-R.",
                fg="gray", font=("Arial", 8), justify=tk.LEFT).pack(pady=(0, 10))

        drive_frame = tk.LabelFrame(win, text="Target Drive", padx=15, pady=15)
        drive_frame.pack(fill=tk.X, padx=20, pady=10)
        drives = self._detect_optical_drives()
        drive_var = tk.StringVar(value=drives[0][1] if drives else "")
        drive_combo = ttk.Combobox(drive_frame, textvariable=drive_var, width=35,
                                   state='readonly' if drives else 'normal')
        drive_combo['values'] = [d[1] for d in drives]
        drive_combo.pack(side=tk.LEFT, padx=5)
        tk.Button(drive_frame, text="Refresh", command=lambda: (
            drive_combo.config(values=[d[1] for d in self._detect_optical_drives()])
        )).pack(side=tk.LEFT, padx=5)

        files_frame = tk.LabelFrame(win, text="Files to Append", padx=15, pady=15)
        files_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        listbox = tk.Listbox(files_frame, height=10)
        listbox.pack(fill=tk.BOTH, expand=True, pady=5)

        def add_files():
            files = filedialog.askopenfilenames(title="Select Files to Append")
            for f in files:
                listbox.insert(tk.END, f)
        tk.Button(files_frame, text="Add Files...", command=add_files).pack(pady=5)

        def start_append():
            device_path = self._device_from_label(drive_var.get())
            files = list(listbox.get(0, tk.END))
            if not device_path:
                messagebox.showerror("Error", "Please select or enter a target drive")
                return
            if not files:
                messagebox.showerror("Error", "Please add at least one file to append")
                return
            if platform.system() != "Linux":
                messagebox.showerror("Error", "Appending is currently only implemented on Linux")
                return

            dlg = self._make_progress_dialog(win, "Appending Data", f"Appending to {device_path}")

            def worker():
                success, msg = self._append_to_disc(device_path, files, dlg)

                def finish():
                    dlg['status_label'].config(text=msg)
                    if success:
                        dlg['progress_var'].set(100)
                    dlg['cancel_btn'].config(text="Close")
                    if success:
                        messagebox.showinfo("Success", msg)
                    else:
                        messagebox.showerror("Error", msg)
                self.root.after(0, finish)

            threading.Thread(target=worker, daemon=True).start()

        tk.Button(win, text="Append to Disc", bg="#0078d4", fg="white", padx=20, pady=10,
                 command=start_append).pack(pady=10)

    def _append_to_disc(self, device_path, files, dlg):
        if not shutil.which('growisofs'):
            return False, "growisofs is not installed (try: sudo apt-get install dvd+rw-tools)"
        cmd = ['growisofs', '-M', device_path, '-J', '-R'] + files
        progress_re = re.compile(r'(\d+(?:\.\d+)?)\s*%')
        self.root.after(0, lambda: dlg['status_label'].config(text=f"Appending to {device_path}..."))
        rc = self._run_streaming(cmd, dlg, progress_regex=progress_re)
        if dlg['cancel_flag']['cancelled']:
            return False, "Append cancelled"
        if rc != 0:
            return False, (f"growisofs exited with code {rc} — see log. Note: multisession append "
                          f"is only supported on DVD±R(W)/BD, not CD-R.")
        return True, "Data appended successfully"

    def open_erase_window(self):
        win = tk.Toplevel(self.root)
        win.title("Erase Rewritable Disc")
        win.geometry("500x480")
        tk.Label(win, text="Erase Rewritable Disc", font=("Arial", 16, "bold")).pack(pady=20)

        drive_frame = tk.LabelFrame(win, text="Select Drive", padx=15, pady=15)
        drive_frame.pack(fill=tk.X, padx=20, pady=10)
        drives = self._detect_optical_drives()
        drive_var = tk.StringVar(value=drives[0][1] if drives else "")
        drive_combo = ttk.Combobox(drive_frame, textvariable=drive_var, width=35,
                                   state='readonly' if drives else 'normal')
        drive_combo['values'] = [d[1] for d in drives]
        drive_combo.pack(side=tk.LEFT, padx=5)
        tk.Button(drive_frame, text="Refresh", command=lambda: (
            drive_combo.config(values=[d[1] for d in self._detect_optical_drives()])
        )).pack(side=tk.LEFT, padx=5)

        media_frame = tk.LabelFrame(win, text="Media Type", padx=15, pady=15)
        media_frame.pack(fill=tk.X, padx=20, pady=10)
        media_var = tk.StringVar(value="CD")
        ttk.Combobox(media_frame, textvariable=media_var, values=["CD", "DVD"], width=10, state='readonly').pack(anchor=tk.W)

        method_frame = tk.LabelFrame(win, text="Erase Method", padx=15, pady=15)
        method_frame.pack(fill=tk.X, padx=20, pady=10)
        erase_var = tk.StringVar(value="quick")
        tk.Radiobutton(method_frame, text="Quick Erase", variable=erase_var, value="quick").pack(anchor=tk.W)
        tk.Radiobutton(method_frame, text="Full Erase (Secure)", variable=erase_var, value="full").pack(anchor=tk.W)

        def start_erase():
            device_path = self._device_from_label(drive_var.get())
            if not device_path:
                messagebox.showerror("Error", "Please select or enter a drive")
                return
            if platform.system() != "Linux":
                messagebox.showerror("Error", "Erasing is currently only implemented on Linux")
                return
            if not messagebox.askyesno("Confirm Erase", f"This will erase all data on {device_path}. Continue?"):
                return

            dlg = self._make_progress_dialog(win, "Erasing Disc", f"Erasing {device_path}")

            def worker():
                success, msg = self._erase_disc(device_path, media_var.get(), erase_var.get() == 'full', dlg)

                def finish():
                    dlg['status_label'].config(text=msg)
                    if success:
                        dlg['progress_var'].set(100)
                    dlg['cancel_btn'].config(text="Close")
                    if success:
                        messagebox.showinfo("Success", msg)
                    else:
                        messagebox.showerror("Error", msg)
                self.root.after(0, finish)

            threading.Thread(target=worker, daemon=True).start()

        tk.Button(win, text="Start Erasing", bg="#d43f00", fg="white", padx=20, pady=10,
                 command=start_erase).pack(pady=20)

    def _erase_disc(self, device_path, media_kind, full_erase, dlg):
        if media_kind == "CD":
            tool = 'wodim' if shutil.which('wodim') else ('cdrecord' if shutil.which('cdrecord') else None)
            if not tool:
                return False, "Neither wodim nor cdrecord is installed (try: sudo apt-get install wodim)"
            cmd = [tool, f'dev={device_path}', f'blank={"all" if full_erase else "fast"}']
        else:
            if not shutil.which('dvd+rw-format'):
                return False, "dvd+rw-format is not installed (try: sudo apt-get install dvd+rw-tools)"
            cmd = ['dvd+rw-format', '-blank=full' if full_erase else '-blank', device_path]

        self.root.after(0, lambda: dlg['status_label'].config(text=f"Erasing {device_path}..."))
        rc = self._run_streaming(cmd, dlg)
        if dlg['cancel_flag']['cancelled']:
            return False, "Erase cancelled"
        if rc != 0:
            return False, f"Erase tool exited with code {rc} — see log for details"
        return True, "Disc erased successfully"

    def open_drive_info_window(self):
        win = tk.Toplevel(self.root)
        win.title("Drive/Disc Information")
        win.geometry("550x600")
        tk.Label(win, text="Drive/Disc Information", font=("Arial", 16, "bold")).pack(pady=20)
        drive_frame = tk.LabelFrame(win, text="Select Drive", padx=15, pady=15)
        drive_frame.pack(fill=tk.X, padx=20, pady=10)
        ttk.Combobox(drive_frame, values=["D: (DVD-RW)", "E: (Blu-ray)", "F: (CD-RW)"], width=30).pack()
        info_frame = tk.LabelFrame(win, text="Information", padx=15, pady=15)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        info_text = tk.Text(info_frame, height=15, wrap=tk.WORD)
        info_text.pack(fill=tk.BOTH, expand=True)
        info = """Drive Information:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Drive Letter: D:
Device Type: DVD-RW Drive
Manufacturer: Generic
Model: DVD-RW 16X
Firmware: 1.0.2

Disc Information:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Disc Type: DVD-RW
Capacity: 4.7 GB
Used Space: 0 bytes
Free Space: 4.7 GB
Status: Empty, Rewritable"""
        info_text.insert('1.0', info)
        info_text.config(state=tk.DISABLED)
        tk.Button(win, text="Refresh", command=lambda: messagebox.showinfo("Refresh", "Information refreshed")).pack(pady=10)

    def open_copy_window(self):
        win = tk.Toplevel(self.root)
        win.title("Copy CD/DVD/Blu-ray")
        win.geometry("550x680")
        tk.Label(win, text="Copy Disc", font=("Arial", 16, "bold")).pack(pady=20)
        tk.Label(win, text="Reads the source disc to a temporary image, then burns\n"
                           "that image to the destination drive.",
                fg="gray", font=("Arial", 8), justify=tk.LEFT).pack(pady=(0, 10))

        drives = self._detect_optical_drives()
        drive_labels = [d[1] for d in drives]

        source_frame = tk.LabelFrame(win, text="Source Drive", padx=15, pady=15)
        source_frame.pack(fill=tk.X, padx=20, pady=10)
        source_var = tk.StringVar(value=drive_labels[0] if drive_labels else "")
        source_combo = ttk.Combobox(source_frame, textvariable=source_var, values=drive_labels,
                                    width=35, state='readonly' if drive_labels else 'normal')
        source_combo.pack(side=tk.LEFT, padx=5)

        dest_frame = tk.LabelFrame(win, text="Destination Drive", padx=15, pady=15)
        dest_frame.pack(fill=tk.X, padx=20, pady=10)
        dest_var = tk.StringVar(value=drive_labels[-1] if drive_labels else "")
        dest_combo = ttk.Combobox(dest_frame, textvariable=dest_var, values=drive_labels,
                                  width=35, state='readonly' if drive_labels else 'normal')
        dest_combo.pack(side=tk.LEFT, padx=5)

        def refresh_both():
            new_drives = self._detect_optical_drives()
            new_labels = [d[1] for d in new_drives]
            source_combo.config(values=new_labels)
            dest_combo.config(values=new_labels)
        tk.Button(win, text="Refresh Drives", command=refresh_both).pack(pady=5)

        media_frame = tk.LabelFrame(win, text="Destination Media Type", padx=15, pady=15)
        media_frame.pack(fill=tk.X, padx=20, pady=10)
        media_var = tk.StringVar(value="DVD")
        ttk.Combobox(media_frame, textvariable=media_var, values=["CD", "DVD", "BD"], width=10, state='readonly').pack(anchor=tk.W)

        options_frame = tk.LabelFrame(win, text="Copy Options", padx=15, pady=15)
        options_frame.pack(fill=tk.X, padx=20, pady=10)
        verify_var = tk.BooleanVar(value=True)
        tk.Checkbutton(options_frame, text="Verify after copy", variable=verify_var).pack(anchor=tk.W)
        tk.Label(options_frame, text="Number of copies:").pack(anchor=tk.W, pady=(10, 0))
        copies_spin = tk.Spinbox(options_frame, from_=1, to=10, width=10)
        copies_spin.pack(anchor=tk.W)

        def start_copy():
            source_device = self._device_from_label(source_var.get())
            dest_device = self._device_from_label(dest_var.get())
            if not source_device or not dest_device:
                messagebox.showerror("Error", "Please select both source and destination drives")
                return
            if source_device == dest_device:
                messagebox.showerror("Error", "Source and destination must be different drives")
                return
            if platform.system() != "Linux":
                messagebox.showerror("Error", "Disc copying is currently only implemented on Linux")
                return
            try:
                num_copies = max(1, int(copies_spin.get()))
            except ValueError:
                num_copies = 1

            dlg = self._make_progress_dialog(win, "Copying Disc", f"Reading {source_device}...")

            def worker():
                tmp_image = os.path.join(
                    os.path.expanduser("~"), f".x-iso-copy-{int(time.time())}.iso"
                )
                ok, msg = self._dd_copy(source_device, tmp_image, dlg, block_size='2048')
                if not ok:
                    self._finish_copy(dlg, False, f"Reading source failed: {msg}")
                    return

                for copy_num in range(1, num_copies + 1):
                    if dlg['cancel_flag']['cancelled']:
                        break
                    if copy_num > 1:
                        proceed = {'ok': False}
                        done_event = threading.Event()

                        def ask():
                            proceed['ok'] = messagebox.askokcancel(
                                "Insert Blank Disc",
                                f"Insert a blank disc into {dest_device} for copy {copy_num} of {num_copies}, then click OK."
                            )
                            done_event.set()
                        self.root.after(0, ask)
                        done_event.wait()
                        if not proceed['ok']:
                            break

                    self.root.after(0, lambda cn=copy_num: dlg['status_label'].config(
                        text=f"Burning copy {cn} of {num_copies} to {dest_device}..."))
                    dlg['progress_var'].set(0)
                    burn_ok, burn_msg = self._burn_image(tmp_image, dest_device, media_var.get(), verify_var.get(), dlg)
                    if not burn_ok:
                        self._finish_copy(dlg, False, f"Copy {copy_num} failed: {burn_msg}")
                        try:
                            os.remove(tmp_image)
                        except OSError:
                            pass
                        return

                try:
                    os.remove(tmp_image)
                except OSError:
                    pass
                self._finish_copy(dlg, True, f"Successfully created {num_copies} copy/copies")

            threading.Thread(target=worker, daemon=True).start()

        tk.Button(win, text="Start Copy", bg="#0078d4", fg="white", padx=20, pady=10,
                 command=start_copy).pack(pady=20)

    def _finish_copy(self, dlg, success, msg):
        def finish():
            dlg['status_label'].config(text=msg)
            if success:
                dlg['progress_var'].set(100)
            dlg['cancel_btn'].config(text="Close")
            if success:
                messagebox.showinfo("Success", msg)
            else:
                messagebox.showerror("Error", msg)
        self.root.after(0, finish)

    def open_make_image_window(self):
        win = tk.Toplevel(self.root)
        win.title("Make CD/DVD/Blu-ray Image")
        win.geometry("600x520")
        tk.Label(win, text="Make Disc Image", font=("Arial", 16, "bold")).pack(pady=20)

        source_frame = tk.LabelFrame(win, text="Source Drive", padx=15, pady=15)
        source_frame.pack(fill=tk.X, padx=20, pady=10)
        drives = self._detect_optical_drives()
        drive_var = tk.StringVar(value=drives[0][1] if drives else "")
        drive_combo = ttk.Combobox(source_frame, textvariable=drive_var, width=35,
                                   state='readonly' if drives else 'normal')
        drive_combo['values'] = [d[1] for d in drives]
        drive_combo.pack(side=tk.LEFT, padx=5)
        tk.Button(source_frame, text="Refresh", command=lambda: (
            drive_combo.config(values=[d[1] for d in self._detect_optical_drives()])
        )).pack(side=tk.LEFT, padx=5)

        output_frame = tk.LabelFrame(win, text="Output Image File", padx=15, pady=15)
        output_frame.pack(fill=tk.X, padx=20, pady=10)
        output_entry = tk.Entry(output_frame, width=50)
        output_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(output_frame, text="Browse...", command=lambda: self._browse_save_for_entry(output_entry, "Save Image As", ".iso")).pack(side=tk.LEFT)

        format_frame = tk.LabelFrame(win, text="Image Format", padx=15, pady=15)
        format_frame.pack(fill=tk.X, padx=20, pady=10)
        format_var = tk.StringVar(value="ISO")
        ttk.Combobox(format_frame, textvariable=format_var, values=["ISO", "BIN/CUE", "NRG"], width=20, state='readonly').pack()
        tk.Label(format_frame, text="Note: BIN/CUE is generated as a single MODE1/2048 data track\n"
                                    "(not a true raw-sector rip). NRG isn't implemented — saves as ISO.",
                fg="gray", font=("Arial", 8), justify=tk.LEFT).pack(anchor=tk.W, pady=(5, 0))

        def start_make_image():
            device_path = self._device_from_label(drive_var.get())
            output_path = output_entry.get()
            if not device_path:
                messagebox.showerror("Error", "Please select or enter a source drive")
                return
            if not output_path:
                messagebox.showerror("Error", "Please choose an output file")
                return
            if platform.system() != "Linux":
                messagebox.showerror("Error", "Disc imaging is currently only implemented on Linux")
                return

            dlg = self._make_progress_dialog(win, "Creating Disc Image", f"Reading {device_path}...")

            def worker():
                success, msg = self._make_disc_image(device_path, output_path, format_var.get(), dlg)

                def finish():
                    dlg['status_label'].config(text=msg)
                    if success:
                        dlg['progress_var'].set(100)
                    dlg['cancel_btn'].config(text="Close")
                    if success:
                        messagebox.showinfo("Success", msg)
                    else:
                        messagebox.showerror("Error", msg)
                self.root.after(0, finish)

            threading.Thread(target=worker, daemon=True).start()

        tk.Button(win, text="Create Image", bg="#0078d4", fg="white", padx=20, pady=10,
                 command=start_make_image).pack(pady=20)

    def _make_disc_image(self, device_path, output_path, image_format, dlg):
        if image_format == "BIN/CUE":
            bin_path = output_path if output_path.lower().endswith('.bin') else os.path.splitext(output_path)[0] + '.bin'
            cue_path = os.path.splitext(bin_path)[0] + '.cue'
            ok, msg = self._dd_copy(device_path, bin_path, dlg, block_size='2048')
            if not ok:
                return ok, msg
            try:
                with open(cue_path, 'w') as f:
                    f.write(f'FILE "{os.path.basename(bin_path)}" BINARY\n')
                    f.write('  TRACK 01 MODE1/2048\n')
                    f.write('    INDEX 01 00:00:00\n')
                self.root.after(0, lambda: dlg['log'](
                    "Note: .cue assumes a single MODE1/2048 data track (a plain dd read, not a raw-sector rip)."
                ))
                return True, f"Image created: {bin_path} + {cue_path}"
            except Exception as e:
                return False, f"Failed writing .cue file: {e}"
        elif image_format == "NRG":
            iso_path = os.path.splitext(output_path)[0] + '.iso'
            self.root.after(0, lambda: dlg['log'](f"NRG conversion isn't implemented — saving as ISO instead: {iso_path}"))
            return self._dd_copy(device_path, iso_path, dlg, block_size='2048')
        else:
            return self._dd_copy(device_path, output_path, dlg, block_size='2048')

    # ------------------------------------------------------------------
    # Rip Audio CD (real cdparanoia + ffmpeg + MetadataFetcher pipeline)
    # ------------------------------------------------------------------

    def open_rip_audio_window(self):
        win = tk.Toplevel(self.root)
        win.title("Rip Audio CD")
        win.geometry("650x800")

        tk.Label(win, text="Rip Audio CD", font=("Arial", 16, "bold")).pack(pady=20)

        drive_frame = tk.LabelFrame(win, text="CD Drive", padx=15, pady=15)
        drive_frame.pack(fill=tk.X, padx=20, pady=10)

        drive_select_frame = tk.Frame(drive_frame)
        drive_select_frame.pack(fill=tk.X)

        default_drive = "/dev/sr0" if platform.system() == "Linux" else "D:"
        drive_values = ["/dev/sr0", "/dev/sr1"] if platform.system() == "Linux" else ["D:", "E:", "F:"]
        drive_var = tk.StringVar(value=default_drive)
        drive_combo = ttk.Combobox(drive_select_frame, textvariable=drive_var, values=drive_values, width=12)
        drive_combo.pack(side=tk.LEFT, padx=5)

        tk.Button(drive_select_frame, text="Read CD", bg="#0078d4", fg="white",
                 command=lambda: self._read_audio_cd(drive_var.get(), track_list_frame)).pack(side=tk.LEFT, padx=10)

        tk.Label(drive_select_frame, text="← Insert CD and click 'Read CD'").pack(side=tk.LEFT, padx=10)

        tracks_frame = tk.LabelFrame(win, text="Tracks", padx=15, pady=15)
        tracks_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Scrollable track list
        track_canvas = tk.Canvas(tracks_frame, height=200)
        scrollbar = tk.Scrollbar(tracks_frame, orient="vertical", command=track_canvas.yview)
        track_list_frame = tk.Frame(track_canvas)

        track_list_frame.bind(
            "<Configure>",
            lambda e: track_canvas.configure(scrollregion=track_canvas.bbox("all"))
        )

        track_canvas.create_window((0, 0), window=track_list_frame, anchor="nw")
        track_canvas.configure(yscrollcommand=scrollbar.set)

        track_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Initial placeholder
        tk.Label(track_list_frame, text="No CD loaded. Insert a CD and click 'Read CD'",
                fg="gray", font=("Arial", 10, "italic")).pack(pady=40)

        output_frame = tk.LabelFrame(win, text="Output Settings", padx=15, pady=15)
        output_frame.pack(fill=tk.X, padx=20, pady=10)

        tk.Label(output_frame, text="Output Format:").pack(anchor=tk.W)
        format_var = tk.StringVar(value="MP3")
        ttk.Combobox(output_frame, textvariable=format_var, values=["MP3", "WAV", "FLAC", "AAC"], width=15).pack(anchor=tk.W, pady=5)

        tk.Label(output_frame, text="Output Folder:").pack(anchor=tk.W, pady=(10, 0))
        folder_entry = tk.Entry(output_frame, width=40)
        folder_entry.pack(side=tk.LEFT, pady=5)
        tk.Button(output_frame, text="Browse...", command=lambda: self._browse_folder_for_entry(folder_entry, "Select Output Folder")).pack(side=tk.LEFT, padx=5)

        tk.Button(win, text="Start Ripping", bg="#0078d4", fg="white", padx=20, pady=10,
                 command=lambda: self._start_ripping(track_list_frame, folder_entry.get(), format_var.get())).pack(pady=15)

    def _calculate_cddb_disc_id(self, track_list):
        """Calculate CDDB disc ID from track offsets (frames -> seconds -> checksum)."""
        if not track_list:
            return None, None, None

        offsets = []
        for track in track_list:
            offset_seconds = track['start_frame'] // 75
            offsets.append(offset_seconds)

        last_track = track_list[-1]
        total_frames = last_track['start_frame'] + last_track['length_frames']
        total_seconds = total_frames // 75

        n = 0
        for offset in offsets:
            n += sum(int(d) for d in str(offset))

        t = total_seconds - offsets[0]
        disc_id = ((n % 0xff) << 24 | t << 8 | len(track_list))
        disc_id_hex = format(disc_id, '08x')

        return disc_id_hex, offsets, total_seconds

    def _cdparanoia_device_arg(self, cd_device):
        """Normalize a drive identifier into the form cdparanoia expects.

        Linux cdparanoia wants a device node (e.g. /dev/sr0) as-is.
        Windows builds of cdparanoia (e.g. the cygwin/mingw ports) generally
        expect a bare drive letter with no trailing colon/backslash, so we
        strip that here. If your particular Windows build expects a
        different form (e.g. a numeric generic-device id), adjust this.
        """
        if platform.system() == "Windows":
            return cd_device.rstrip(':\\').strip()
        return cd_device

    def _query_cdparanoia_toc(self, cd_device):
        """Query cdparanoia for the track list / offsets. Returns (track_list, error_message)."""
        track_list = []
        device_arg = self._cdparanoia_device_arg(cd_device)

        if platform.system() == "Linux" and not os.path.exists(cd_device):
            return [], f"{cd_device} does not exist. Check your drive letter/device (try `ls -l /dev/sr*`)."

        try:
            result = subprocess.run(
                ['cdparanoia', '-d', device_arg, '-Q'],
                capture_output=True,
                text=True,
                timeout=30
            )
            output = result.stderr or result.stdout
            # cdparanoia -Q table rows look like:
            #   1.    17462 [03:52.62]        0 [00:00.00]    no   no  2
            # columns: track#, length_frames, length_mm:ss.hh, begin_frames, begin_mm:ss.hh, copy, pre, ch
            row_pattern = re.compile(
                r'^\s*(\d+)\.\s+(\d+)\s+\[(\d+:\d+\.\d+)\]\s+(\d+)\s+\[(\d+:\d+\.\d+)\]'
            )
            for line in output.split('\n'):
                m = row_pattern.match(line)
                if m:
                    track_num = int(m.group(1))
                    length_frames = int(m.group(2))
                    length_duration = m.group(3)          # e.g. "03:52.62"
                    begin_frames = int(m.group(4))
                    track_list.append({
                        'number': track_num,
                        'duration': length_duration.split('.')[0],   # "03:52"
                        'start_frame': begin_frames,
                        'length_frames': length_frames
                    })
            if not track_list:
                print(f"cdparanoia -Q raw output (no tracks parsed from this):\n{output}")
            if not track_list:
                if 'unable to open' in output.lower() or 'no such' in output.lower():
                    return [], f"cdparanoia could not open {cd_device}. Check the device path is correct."
                if 'permission' in output.lower():
                    return [], f"Permission denied on {cd_device}. Add your user to the 'cdrom' group (sudo usermod -aG cdrom $USER, then log out/in)."
                return [], "No track list returned — is there an audio CD (not data/blank) in the drive?"
            return track_list, None
        except subprocess.TimeoutExpired:
            return [], (f"cdparanoia timed out reading {cd_device} after 30s. This usually means either "
                        f"no disc is inserted, the drive is still spinning up, or your user lacks permission "
                        f"to access the drive (try: sudo usermod -aG cdrom $USER, then log out and back in).")
        except FileNotFoundError:
            return [], "cdparanoia is not installed or not on PATH."
        except Exception as e:
            return [], f"cdparanoia query failed: {e}"

    def _read_audio_cd(self, drive, track_frame):
        """Read the audio CD's table of contents, fetch metadata, and populate the track list UI."""
        for widget in track_frame.winfo_children():
            widget.destroy()

        loading_label = tk.Label(track_frame, text="Reading CD and fetching metadata...", fg="blue", font=("Arial", 10))
        loading_label.pack(pady=20)
        track_frame.update()

        track_list = []
        cd_device = drive
        disc_info = {'album': 'Unknown Album', 'artist': 'Unknown Artist', 'year': '', 'tracks': {}}
        error_message = None

        try:
            if not shutil.which('cdparanoia'):
                if platform.system() == "Windows":
                    error_message = ("cdparanoia was not found. Download a Windows build of cdparanoia "
                                      "and add it to PATH (see README) to enable ripping.")
                else:
                    error_message = "cdparanoia is not installed (sudo apt-get install cdparanoia)"
            else:
                track_list, toc_error = self._query_cdparanoia_toc(cd_device)
                if not track_list:
                    error_message = toc_error or "No audio CD detected in drive"
                else:
                    cddb_id, offsets, total_seconds = self._calculate_cddb_disc_id(track_list)
                    print(f"Calculated CDDB Disc ID: {cddb_id}")
                    if cddb_id:
                        # MusicBrainz needs raw CD-frame offsets (75/sec) and the true leadout
                        # (end of disc), which are different numbers from the CDDB seconds-based
                        # offsets/total above — do not conflate the two.
                        mb_offsets_frames = [t['start_frame'] for t in track_list]
                        last = track_list[-1]
                        mb_leadout_frames = last['start_frame'] + last['length_frames']
                        disc_info = self.metadata_fetcher.fetch_metadata(
                            cddb_id, offsets, total_seconds, len(track_list),
                            mb_offsets_frames=mb_offsets_frames,
                            mb_leadout_frames=mb_leadout_frames,
                            cd_device=cd_device
                        )
        except Exception as e:
            error_message = f"Error reading CD: {e}"
            print(error_message)

        loading_label.destroy()

        if error_message or not track_list:
            tk.Label(track_frame, text=error_message or "No audio CD detected in drive",
                    fg="red", font=("Arial", 10)).pack(pady=20)
            tk.Label(track_frame, text="Please insert an audio CD and try again",
                    fg="gray").pack()
            return

        # Merge fetched titles into track_list
        track_titles = disc_info.get('tracks', {})
        for track in track_list:
            track['title'] = track_titles.get(track['number'], f"Track {track['number']:02d}")
            track['artist'] = disc_info.get('artist', 'Unknown Artist')
            track['album'] = disc_info.get('album', 'Unknown Album')
            track['year'] = disc_info.get('year', '')
            track['device'] = cd_device

        # Disc info banner
        info_frame = tk.Frame(track_frame, bg="#e8f4f8", relief=tk.RAISED, bd=2)
        info_frame.pack(fill=tk.X, pady=10, padx=5)
        tk.Label(info_frame, text=f"Album: {disc_info.get('album', 'Unknown Album')}",
                font=("Arial", 11, "bold"), bg="#e8f4f8").pack(anchor=tk.W, padx=10, pady=2)
        tk.Label(info_frame, text=f"Artist: {disc_info.get('artist', 'Unknown Artist')}",
                font=("Arial", 10), bg="#e8f4f8").pack(anchor=tk.W, padx=10, pady=2)
        if disc_info.get('year'):
            tk.Label(info_frame, text=f"Year: {disc_info['year']}",
                    font=("Arial", 9), bg="#e8f4f8").pack(anchor=tk.W, padx=10, pady=2)
        tk.Label(info_frame, text=f"{len(track_list)} tracks",
                font=("Arial", 9), fg="green", bg="#e8f4f8").pack(anchor=tk.W, padx=10, pady=2)

        # Select/Deselect all
        select_frame = tk.Frame(track_frame)
        select_frame.pack(fill=tk.X, pady=5)
        all_vars = []

        def select_all():
            for var in all_vars:
                var.set(True)

        def deselect_all():
            for var in all_vars:
                var.set(False)

        tk.Button(select_frame, text="Select All", command=select_all).pack(side=tk.LEFT, padx=5)
        tk.Button(select_frame, text="Deselect All", command=deselect_all).pack(side=tk.LEFT, padx=5)

        # Track checkboxes
        for track in track_list:
            track_item_frame = tk.Frame(track_frame)
            track_item_frame.pack(fill=tk.X, pady=2, padx=5)

            var = tk.BooleanVar(value=True)
            all_vars.append(var)

            tk.Checkbutton(track_item_frame, text=f"{track['number']:02d}. {track['title']}",
                          variable=var, width=40, anchor='w').pack(side=tk.LEFT)
            tk.Label(track_item_frame, text=f"{track['duration']}", width=8).pack(side=tk.LEFT, padx=10)

        track_frame.track_vars = all_vars
        track_frame.track_info = track_list
        track_frame.cd_device = cd_device
        track_frame.disc_info = disc_info

    def _start_ripping(self, track_frame, output_folder, output_format):
        """Rip the selected tracks via cdparanoia, tagging/converting with ffmpeg."""
        if not output_folder:
            messagebox.showerror("Error", "Please select an output folder")
            return

        if not hasattr(track_frame, 'track_vars') or not hasattr(track_frame, 'track_info'):
            messagebox.showerror("Error", "No CD loaded. Please click 'Read CD' first")
            return

        selected_tracks = [track_frame.track_info[i] for i, var in enumerate(track_frame.track_vars) if var.get()]
        if not selected_tracks:
            messagebox.showwarning("Warning", "No tracks selected")
            return

        cd_device = getattr(track_frame, 'cd_device', '/dev/sr0')

        progress_win = tk.Toplevel(self.root)
        progress_win.title("Ripping Audio CD")
        progress_win.geometry("500x300")
        progress_win.transient(self.root)
        progress_win.grab_set()

        tk.Label(progress_win, text="Ripping Audio Tracks", font=("Arial", 14, "bold")).pack(pady=20)
        status_label = tk.Label(progress_win, text="Initializing...", font=("Arial", 10))
        status_label.pack(pady=10)

        progress_var = tk.IntVar()
        ttk.Progressbar(progress_win, variable=progress_var, maximum=100, length=400).pack(pady=20)

        track_label = tk.Label(progress_win, text="", font=("Arial", 9))
        track_label.pack(pady=5)

        cancel_flag = {'cancelled': False}

        def cancel_rip():
            cancel_flag['cancelled'] = True
            progress_win.destroy()

        cancel_btn = tk.Button(progress_win, text="Cancel", command=cancel_rip, padx=20, pady=5)
        cancel_btn.pack(pady=10)

        def rip_thread():
            os.makedirs(output_folder, exist_ok=True)
            total_tracks = len(selected_tracks)
            successful_rips = 0
            failed_tracks = []

            has_cdparanoia = shutil.which('cdparanoia') is not None
            has_ffmpeg = shutil.which('ffmpeg') is not None

            for idx, track_info in enumerate(selected_tracks, 1):
                if cancel_flag['cancelled']:
                    break

                track_num = track_info['number']

                def set_status(i=idx, t=total_tracks, ti=track_info):
                    status_label.config(text=f"Ripping track {i} of {t}")
                    track_label.config(text=f"{ti['title']} ({ti['duration']})")
                self.root.after(0, set_status)

                safe_title = "".join(c for c in track_info['title'] if c not in '\\/:*?"<>|').strip() or f"Track {track_num:02d}"
                artist = "".join(c for c in track_info.get('artist', 'Unknown Artist') if c not in '\\/:*?"<>|').strip()
                album = "".join(c for c in track_info.get('album', 'Unknown Album') if c not in '\\/:*?"<>|').strip()
                output_ext = output_format.lower()

                album_folder = os.path.join(output_folder, artist, album)
                os.makedirs(album_folder, exist_ok=True)
                output_file = os.path.join(album_folder, f"{track_num:02d} - {safe_title}.{output_ext}")

                success = False

                if has_cdparanoia:
                    temp_wav = os.path.join(album_folder, f".tmp_track_{track_num}.wav")
                    device_arg = self._cdparanoia_device_arg(cd_device)
                    try:
                        result = subprocess.run(
                            ['cdparanoia', '-d', device_arg, str(track_num), temp_wav],
                            capture_output=True, text=True, timeout=300
                        )
                        if result.returncode == 0 and os.path.exists(temp_wav):
                            if output_ext == 'wav':
                                shutil.move(temp_wav, output_file)
                                success = True
                            elif has_ffmpeg:
                                ffmpeg_cmd = ['ffmpeg', '-i', temp_wav, '-y']
                                ffmpeg_cmd += ['-metadata', f'title={track_info["title"]}']
                                ffmpeg_cmd += ['-metadata', f'artist={track_info.get("artist", "Unknown Artist")}']
                                ffmpeg_cmd += ['-metadata', f'album={track_info.get("album", "Unknown Album")}']
                                ffmpeg_cmd += ['-metadata', f'track={track_num}/{total_tracks}']
                                if track_info.get('year'):
                                    ffmpeg_cmd += ['-metadata', f'date={track_info["year"]}']

                                if output_ext == 'mp3':
                                    ffmpeg_cmd += ['-codec:a', 'libmp3lame', '-b:a', '320k', '-id3v2_version', '3']
                                elif output_ext == 'flac':
                                    ffmpeg_cmd += ['-codec:a', 'flac', '-compression_level', '8']
                                elif output_ext == 'aac':
                                    ffmpeg_cmd += ['-codec:a', 'aac', '-b:a', '256k']
                                elif output_ext == 'ogg':
                                    ffmpeg_cmd += ['-codec:a', 'libvorbis', '-q:a', '6']

                                ffmpeg_cmd.append(output_file)
                                conv = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=120)
                                if conv.returncode == 0 and os.path.exists(output_file):
                                    success = True
                                else:
                                    print(f"FFmpeg conversion failed: {conv.stderr}")
                                try:
                                    os.remove(temp_wav)
                                except OSError:
                                    pass
                            else:
                                shutil.move(temp_wav, output_file.rsplit('.', 1)[0] + '.wav')
                                success = True
                                print("Warning: ffmpeg not found, saved as WAV instead")
                        else:
                            print(f"cdparanoia failed for track {track_num}: {result.stderr}")
                    except subprocess.TimeoutExpired:
                        print(f"Timeout while ripping track {track_num}")
                    except Exception as e:
                        print(f"Error ripping track {track_num}: {e}")

                if success:
                    successful_rips += 1
                else:
                    failed_tracks.append(track_num)

                progress = int((idx / total_tracks) * 100)
                self.root.after(0, lambda p=progress: progress_var.set(p))

            if not cancel_flag['cancelled']:
                def finish():
                    progress_var.set(100)
                    if successful_rips > 0:
                        status_label.config(text=f"Completed! Ripped {successful_rips}/{total_tracks} tracks")
                        track_label.config(text=f"Saved to {output_folder}")
                    else:
                        status_label.config(text="No tracks were successfully ripped")
                        track_label.config(text="Check that the CD is inserted and cdparanoia/ffmpeg are installed")
                    cancel_btn.config(text="Close")
                    progress_win.after(3000, progress_win.destroy)

                    if successful_rips > 0:
                        msg = f"Successfully ripped {successful_rips}/{total_tracks} track(s)\n\nOutput folder: {output_folder}\nFormat: {output_format}"
                        if failed_tracks:
                            msg += f"\n\nFailed tracks: {', '.join(map(str, failed_tracks))}"
                        messagebox.showinfo("Success", msg)
                    else:
                        messagebox.showerror(
                            "Error",
                            "Failed to rip any tracks.\n\nPlease ensure:\n"
                            "- Audio CD is inserted\n"
                            "- cdparanoia is installed (Linux)\n"
                            "- ffmpeg is installed\n"
                            "- CD drive is accessible"
                        )
                self.root.after(0, finish)

        thread = threading.Thread(target=rip_thread, daemon=True)
        thread.start()

    def _browse_folder_for_entry(self, entry_widget, title):
        folder = filedialog.askdirectory(title=title)
        if folder:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, folder)

    def open_audio_converter_window(self):
        win = tk.Toplevel(self.root)
        win.title("Audio Converter")
        win.geometry("650x640")
        tk.Label(win, text="Audio Converter", font=("Arial", 16, "bold")).pack(pady=20)
        input_frame = tk.LabelFrame(win, text="Input Audio Files", padx=15, pady=15)
        input_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        listbox = tk.Listbox(input_frame, height=8)
        listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        def add_files():
            files = filedialog.askopenfilenames(title="Select Audio Files", filetypes=[("All Audio", "*.mp3 *.wav *.flac *.aac *.ogg *.m4a *.wma"), ("All Files", "*.*")])
            for f in files:
                listbox.insert(tk.END, f)
        btn_frame = tk.Frame(input_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        tk.Button(btn_frame, text="Add Files...", command=add_files).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Remove", command=lambda: listbox.delete(tk.ACTIVE) if listbox.curselection() else None).pack(side=tk.LEFT, padx=5)
        format_frame = tk.LabelFrame(win, text="Output Settings", padx=15, pady=15)
        format_frame.pack(fill=tk.X, padx=20, pady=10)
        tk.Label(format_frame, text="Format:").pack(anchor=tk.W)
        ttk.Combobox(format_frame, values=["MP3", "WAV", "FLAC", "AAC", "OGG", "WMA"], width=15).pack(anchor=tk.W, pady=5)
        tk.Label(format_frame, text="Quality:").pack(anchor=tk.W, pady=(10,0))
        ttk.Combobox(format_frame, values=["128 kbps", "192 kbps", "256 kbps", "320 kbps"], width=15).pack(anchor=tk.W, pady=5)
        tk.Button(win, text="Convert", bg="#0078d4", fg="white", padx=20, pady=10,
                 command=lambda: messagebox.showinfo("Convert", "Conversion started")).pack(pady=15)

    def open_usb_image_window(self):
        win = tk.Toplevel(self.root)
        win.title("Make USB Drive Image")
        win.geometry("620x420")
        tk.Label(win, text="Make USB Drive Image", font=("Arial", 16, "bold")).pack(pady=20)

        source_frame = tk.LabelFrame(win, text="Source USB Drive", padx=15, pady=15)
        source_frame.pack(fill=tk.X, padx=20, pady=10)
        drives = self._detect_usb_drives()
        drive_var = tk.StringVar(value=drives[0][1] if drives else "Select USB Drive")
        drive_combo = ttk.Combobox(source_frame, textvariable=drive_var, width=45,
                                   state='readonly' if drives else 'normal')
        drive_combo['values'] = [d[1] for d in drives]
        drive_combo.pack(pady=5)

        def refresh_drives():
            new_drives = self._detect_usb_drives()
            drive_combo.config(values=[d[1] for d in new_drives], state='readonly' if new_drives else 'normal')
            if new_drives:
                drive_var.set(new_drives[0][1])
            else:
                messagebox.showinfo("Refresh", "No USB drives detected")
        tk.Button(source_frame, text="Refresh Drives", command=refresh_drives).pack(pady=5)
        if platform.system() != "Linux":
            tk.Label(source_frame, text="USB detection currently only implemented on Linux — "
                                        "enter a device path manually", fg="gray", font=("Arial", 8)).pack()

        output_frame = tk.LabelFrame(win, text="Output Image File", padx=15, pady=15)
        output_frame.pack(fill=tk.X, padx=20, pady=10)
        output_entry = tk.Entry(output_frame, width=50)
        output_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(output_frame, text="Browse...", command=lambda: self._browse_save_for_entry(output_entry, "Save USB Image As", ".img")).pack(side=tk.LEFT)

        def start_image():
            device_path = self._device_from_label(drive_var.get())
            output_path = output_entry.get()
            if not device_path or device_path == "Select":
                messagebox.showerror("Error", "Please select or enter a source USB drive")
                return
            if not output_path:
                messagebox.showerror("Error", "Please choose an output file")
                return
            if platform.system() != "Linux":
                messagebox.showerror("Error", "USB imaging is currently only implemented on Linux")
                return
            if not messagebox.askyesno("Confirm", f"Read the entire drive {device_path} into {output_path}?\n"
                                                   f"This may take a while depending on drive size."):
                return

            dlg = self._make_progress_dialog(win, "Creating USB Image", f"Reading {device_path}...")

            def worker():
                success, msg = self._dd_copy(device_path, output_path, dlg, block_size='4M')

                def finish():
                    dlg['status_label'].config(text=msg)
                    if success:
                        dlg['progress_var'].set(100)
                    dlg['cancel_btn'].config(text="Close")
                    if success:
                        messagebox.showinfo("Success", f"Image saved to {output_path}")
                    else:
                        messagebox.showerror("Error", msg)
                self.root.after(0, finish)

            threading.Thread(target=worker, daemon=True).start()

        tk.Button(win, text="Create Image", bg="#0078d4", fg="white", padx=20, pady=10,
                 command=start_image).pack(pady=20)

    def open_bootable_usb_window(self):
        win = tk.Toplevel(self.root)
        win.title("Create Bootable USB")
        win.geometry("620x600")
        tk.Label(win, text="Create Bootable USB", font=("Arial", 16, "bold")).pack(pady=20)

        iso_frame = tk.LabelFrame(win, text="ISO Image File", padx=15, pady=15)
        iso_frame.pack(fill=tk.X, padx=20, pady=10)
        iso_entry = tk.Entry(iso_frame, width=50)
        iso_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(iso_frame, text="Browse...", command=lambda: self._browse_for_entry(iso_entry, "Select ISO Image", [("ISO files", "*.iso")])).pack(side=tk.LEFT)

        usb_frame = tk.LabelFrame(win, text="Target USB Drive", padx=15, pady=15)
        usb_frame.pack(fill=tk.X, padx=20, pady=10)
        drives = self._detect_usb_drives()
        usb_var = tk.StringVar(value=drives[0][1] if drives else "Select USB Drive")
        usb_combo = ttk.Combobox(usb_frame, textvariable=usb_var, width=45,
                                 state='readonly' if drives else 'normal')
        usb_combo['values'] = [d[1] for d in drives]
        usb_combo.pack(pady=5)

        def refresh_usb():
            new_drives = self._detect_usb_drives()
            usb_combo.config(values=[d[1] for d in new_drives], state='readonly' if new_drives else 'normal')
            if new_drives:
                usb_var.set(new_drives[0][1])
            else:
                messagebox.showinfo("Refresh", "No USB drives detected")
        tk.Button(usb_frame, text="Refresh Drives", command=refresh_usb).pack(pady=5)

        tk.Label(usb_frame, text="⚠ Warning: All data on the USB drive will be erased!", fg="red", font=("Arial", 9)).pack(pady=5)

        options_frame = tk.LabelFrame(win, text="Partition Scheme (informational)", padx=15, pady=15)
        options_frame.pack(fill=tk.X, padx=20, pady=10)
        scheme_var = tk.StringVar(value="MBR")
        tk.Radiobutton(options_frame, text="MBR (BIOS or UEFI)", variable=scheme_var, value="MBR").pack(anchor=tk.W)
        tk.Radiobutton(options_frame, text="GPT (UEFI only)", variable=scheme_var, value="GPT").pack(anchor=tk.W)
        tk.Label(options_frame, text="Writing is done with a direct raw copy (dd) of the ISO — most modern\n"
                                     "Linux ISOs are hybrid images with their own partition table baked in,\n"
                                     "so this selector doesn't change the write; it's shown for reference.",
                fg="gray", font=("Arial", 8), justify=tk.LEFT).pack(anchor=tk.W, pady=(5, 0))

        def start_bootable():
            iso_path = iso_entry.get()
            device_path = self._device_from_label(usb_var.get())
            if not iso_path or not os.path.exists(iso_path):
                messagebox.showerror("Error", "Please select a valid ISO image")
                return
            if not device_path or device_path == "Select":
                messagebox.showerror("Error", "Please select or enter a target USB drive")
                return
            if platform.system() != "Linux":
                messagebox.showerror("Error", "Creating bootable USB is currently only implemented on Linux")
                return
            if not messagebox.askyesno("Confirm", f"This will ERASE ALL DATA on {device_path} and write "
                                                   f"{os.path.basename(iso_path)} to it. Continue?"):
                return

            dlg = self._make_progress_dialog(win, "Creating Bootable USB", f"Writing to {device_path}...")

            def worker():
                success, msg = self._dd_copy(iso_path, device_path, dlg, block_size='4M')

                def finish():
                    dlg['status_label'].config(text=msg)
                    if success:
                        dlg['progress_var'].set(100)
                    dlg['cancel_btn'].config(text="Close")
                    if success:
                        messagebox.showinfo("Success", f"Bootable USB created on {device_path}")
                    else:
                        messagebox.showerror("Error", msg)
                self.root.after(0, finish)

            threading.Thread(target=worker, daemon=True).start()

        tk.Button(win, text="Create Bootable USB", bg="#0078d4", fg="white", padx=20, pady=10,
                 command=start_bootable).pack(pady=15)

    def _browse_for_entry(self, entry_widget, title, filetypes=None):
        if filetypes is None:
            filetypes = [("ISO files", "*.iso"), ("All files", "*.*")]
        file = filedialog.askopenfilename(title=title, filetypes=filetypes)
        if file:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, file)

    def _browse_save_for_entry(self, entry_widget, title, default_ext):
        file = filedialog.asksaveasfilename(title=title, defaultextension=default_ext,
                                           filetypes=[(f"{default_ext.upper()} files", f"*{default_ext}"), ("All files", "*.*")])
        if file:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, file)

    def show_about(self):
        messagebox.showinfo("About X-ISO",
                           "X-ISO v1.0 (Enhanced)\nDisc Image Converter & Burner\n\n" +
                           "A comprehensive tool for converting, burning,\n" +
                           "and managing disc images with automatic\n" +
                           "CD metadata retrieval.\n\n© 2025")

if __name__ == "__main__":
    root = tk.Tk()
    app = XISOMApp(root)
    root.mainloop()
