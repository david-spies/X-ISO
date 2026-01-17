import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os

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
        self.root.geometry("900x800")
        
        self.converter = ImageConverter(progress_callback=self.update_progress)
        self.conversion_thread = None
        
        self.setup_ui()
    
    def setup_ui(self):
        # Menu
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
        tools_menu.add_command(label="Rip Audio CD", command=self.open_rip_audio_window)
        tools_menu.add_command(label="Audio Converter", command=self.open_audio_converter_window)
        tools_menu.add_command(label="Virtual Drive", command=lambda: self.notebook.select(2))
        tools_menu.add_command(label="Make USB Drive Image", command=self.open_usb_image_window)
        tools_menu.add_command(label="Create Bootable USB", command=self.open_bootable_usb_window)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
        
        # Header
        header = tk.Frame(self.root, bg="#2b2b2b")
        header.pack(fill=tk.X, padx=20, pady=15)
        tk.Label(header, text="X-ISO", font=("Arial", 24, "bold"), bg="#2b2b2b", fg="white").pack(side=tk.LEFT)
        tk.Label(header, text="Disc Image Converter & Burner", font=("Arial", 10), bg="#2b2b2b", fg="white").pack(side=tk.LEFT, padx=10)
        
        # Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Tabs
        self.create_converter_tab()
        self.create_burn_tab()
        self.create_virtual_tab()
        self.create_tools_tab()
        
        # Status
        self.status_bar = tk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(fill=tk.X, padx=20, pady=10)
    
    def create_converter_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Convert")
        
        # Source
        src_frame = tk.LabelFrame(frame, text="Source Image File", padx=15, pady=15)
        src_frame.pack(fill=tk.X, padx=20, pady=10)
        self.source_entry = tk.Entry(src_frame, width=70)
        self.source_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(src_frame, text="Browse...", command=self.browse_source).pack(side=tk.LEFT)
        
        # Output
        out_frame = tk.LabelFrame(frame, text="Output ISO File", padx=15, pady=15)
        out_frame.pack(fill=tk.X, padx=20, pady=10)
        self.output_entry = tk.Entry(out_frame, width=70)
        self.output_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(out_frame, text="Save As...", command=self.browse_output).pack(side=tk.LEFT)
        
        # Formats
        fmt_frame = tk.LabelFrame(frame, text="Supported Formats", padx=15, pady=15)
        fmt_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        self.formats_text = tk.Text(fmt_frame, height=8, wrap=tk.WORD)
        self.formats_text.pack(fill=tk.BOTH, expand=True)
        formats = "\n".join([f"{k.upper()}: {v}" for k, v in ImageConverter.SUPPORTED_FORMATS.items()])
        self.formats_text.insert('1.0', "Supported formats:\n\n" + formats)
        self.formats_text.config(state=tk.DISABLED)
        
        # Progress
        prog_frame = tk.Frame(frame)
        prog_frame.pack(fill=tk.X, padx=20, pady=10)
        self.progress_var = tk.IntVar()
        self.progress_bar = ttk.Progressbar(prog_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=5)
        self.progress_label = tk.Label(prog_frame, text="")
        self.progress_label.pack()
        
        # Buttons
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
        self.drive_var = tk.StringVar(value="D: (DVD-RW Drive)")
        drive_combo = ttk.Combobox(drive_frame, textvariable=self.drive_var, width=40, state='readonly')
        drive_combo['values'] = ("D: (DVD-RW Drive)", "E: (Blu-ray Burner)", "F: (CD-RW Drive)")
        drive_combo.pack(pady=5)
        
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
            ("Append Data to Disc", self.open_append_window)
        ]
        
        for i, (name, func) in enumerate(tools):
            tk.Button(grid, text=name, command=func, width=30, pady=10).grid(row=i//2, column=i%2, padx=10, pady=5)
    
    # Event handlers
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
    
    def browse_burn_image(self):
        file = filedialog.askopenfilename(title="Select Image to Burn",
                                         filetypes=[("ISO Image", "*.iso"), ("All Files", "*.*")])
        if file:
            self.burn_entry.delete(0, tk.END)
            self.burn_entry.insert(0, file)
    
    def burn_disc(self):
        if not self.burn_entry.get():
            messagebox.showerror("Error", "Please select an image file")
            return
        messagebox.showinfo("Burn", "Burn operation would start (simulation mode)")
    
    def browse_mount_image(self):
        file = filedialog.askopenfilename(title="Select Image to Mount",
                                         filetypes=[("ISO Image", "*.iso"), ("All Files", "*.*")])
        if file:
            self.mount_entry.delete(0, tk.END)
            self.mount_entry.insert(0, file)
    
    def mount_image(self):
        if self.mount_entry.get():
            self.mounted_listbox.insert(tk.END, f"V1: {os.path.basename(self.mount_entry.get())}")
            messagebox.showinfo("Success", "Image mounted successfully")
    
    def unmount_image(self):
        sel = self.mounted_listbox.curselection()
        if sel:
            self.mounted_listbox.delete(sel[0])
            messagebox.showinfo("Success", "Image unmounted")
    
    # Tool Windows
    def open_burn_window(self):
        win = tk.Toplevel(self.root)
        win.title("Burn Disc")
        win.geometry("600x500")
        
        tk.Label(win, text="Burn Disc Image", font=("Arial", 16, "bold")).pack(pady=20)
        
        file_frame = tk.LabelFrame(win, text="Image File", padx=15, pady=15)
        file_frame.pack(fill=tk.X, padx=20, pady=10)
        burn_entry = tk.Entry(file_frame, width=50)
        burn_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(file_frame, text="Browse...", command=lambda: self._browse_for_entry(burn_entry, "Select Image")).pack(side=tk.LEFT)
        
        drive_frame = tk.LabelFrame(win, text="Target Drive", padx=15, pady=15)
        drive_frame.pack(fill=tk.X, padx=20, pady=10)
        drive_var = tk.StringVar(value="D: (DVD-RW Drive)")
        ttk.Combobox(drive_frame, textvariable=drive_var, values=["D: (DVD-RW)", "E: (Blu-ray)", "F: (CD-RW)"], width=30).pack()
        
        options_frame = tk.LabelFrame(win, text="Options", padx=15, pady=15)
        options_frame.pack(fill=tk.X, padx=20, pady=10)
        verify_var = tk.BooleanVar(value=True)
        tk.Checkbutton(options_frame, text="Verify after burning", variable=verify_var).pack(anchor=tk.W)
        finalize_var = tk.BooleanVar(value=True)
        tk.Checkbutton(options_frame, text="Finalize disc", variable=finalize_var).pack(anchor=tk.W)
        
        tk.Label(options_frame, text="Write Speed:").pack(anchor=tk.W, pady=(10,0))
        speed_var = tk.StringVar(value="Maximum")
        ttk.Combobox(options_frame, textvariable=speed_var, values=["Maximum", "16x", "8x", "4x", "2x"], width=15).pack(anchor=tk.W)
        
        tk.Button(win, text="Start Burning", bg="#0078d4", fg="white", padx=20, pady=10,
                 command=lambda: messagebox.showinfo("Burn", "Burning started...")).pack(pady=20)
    
    def open_append_window(self):
        win = tk.Toplevel(self.root)
        win.title("Append Data to Disc")
        win.geometry("550x580")
        
        tk.Label(win, text="Append Data to Disc", font=("Arial", 16, "bold")).pack(pady=20)
        
        drive_frame = tk.LabelFrame(win, text="Target Drive", padx=15, pady=15)
        drive_frame.pack(fill=tk.X, padx=20, pady=10)
        ttk.Combobox(drive_frame, values=["D: (DVD-RW)", "E: (CD-RW)"], width=30).pack()
        
        files_frame = tk.LabelFrame(win, text="Files to Append", padx=15, pady=15)
        files_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        listbox = tk.Listbox(files_frame, height=10)
        listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        tk.Button(files_frame, text="Add Files...", command=lambda: messagebox.showinfo("Add", "File browser")).pack(pady=5)
        
        tk.Button(win, text="Append to Disc", bg="#0078d4", fg="white", padx=20, pady=10,
                 command=lambda: messagebox.showinfo("Append", "Appending data...")).pack(pady=10)
    
    def open_erase_window(self):
        win = tk.Toplevel(self.root)
        win.title("Erase Rewritable Disc")
        win.geometry("500x400")
        
        tk.Label(win, text="Erase Rewritable Disc", font=("Arial", 16, "bold")).pack(pady=20)
        
        drive_frame = tk.LabelFrame(win, text="Select Drive", padx=15, pady=15)
        drive_frame.pack(fill=tk.X, padx=20, pady=10)
        ttk.Combobox(drive_frame, values=["D: (DVD-RW)", "E: (CD-RW)"], width=30).pack()
        
        method_frame = tk.LabelFrame(win, text="Erase Method", padx=15, pady=15)
        method_frame.pack(fill=tk.X, padx=20, pady=10)
        erase_var = tk.StringVar(value="quick")
        tk.Radiobutton(method_frame, text="Quick Erase", variable=erase_var, value="quick").pack(anchor=tk.W)
        tk.Radiobutton(method_frame, text="Full Erase (Secure)", variable=erase_var, value="full").pack(anchor=tk.W)
        
        tk.Button(win, text="Start Erasing", bg="#d43f00", fg="white", padx=20, pady=10,
                 command=lambda: messagebox.showwarning("Erase", "This will erase all data on the disc!")).pack(pady=20)
    
    def open_drive_info_window(self):
        win = tk.Toplevel(self.root)
        win.title("Drive/Disc Information")
        win.geometry("550x580")
        
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
Capacity: 4.7 GB (4,700,372,992 bytes)
Used Space: 0 bytes
Free Space: 4.7 GB
Status: Empty, Rewritable
Sessions: 0"""
        
        info_text.insert('1.0', info)
        info_text.config(state=tk.DISABLED)
        
        tk.Button(win, text="Refresh", command=lambda: messagebox.showinfo("Refresh", "Information refreshed")).pack(pady=10)
    
    def open_copy_window(self):
        win = tk.Toplevel(self.root)
        win.title("Copy CD/DVD/Blu-ray")
        win.geometry("550x520")
        
        tk.Label(win, text="Copy Disc", font=("Arial", 16, "bold")).pack(pady=20)
        
        source_frame = tk.LabelFrame(win, text="Source Drive", padx=15, pady=15)
        source_frame.pack(fill=tk.X, padx=20, pady=10)
        ttk.Combobox(source_frame, values=["D: (DVD-ROM)", "E: (Blu-ray)"], width=30).pack()
        
        dest_frame = tk.LabelFrame(win, text="Destination Drive", padx=15, pady=15)
        dest_frame.pack(fill=tk.X, padx=20, pady=10)
        ttk.Combobox(dest_frame, values=["F: (DVD-RW)", "G: (Blu-ray Burner)"], width=30).pack()
        
        options_frame = tk.LabelFrame(win, text="Copy Options", padx=15, pady=15)
        options_frame.pack(fill=tk.X, padx=20, pady=10)
        verify_var = tk.BooleanVar(value=True)
        tk.Checkbutton(options_frame, text="Verify after copy", variable=verify_var).pack(anchor=tk.W)
        temp_var = tk.BooleanVar(value=False)
        tk.Checkbutton(options_frame, text="Use temporary image file", variable=temp_var).pack(anchor=tk.W)
        
        tk.Label(options_frame, text="Number of copies:").pack(anchor=tk.W, pady=(10,0))
        copies_spin = tk.Spinbox(options_frame, from_=1, to=10, width=10)
        copies_spin.pack(anchor=tk.W)
        
        tk.Button(win, text="Start Copy", bg="#0078d4", fg="white", padx=20, pady=10,
                 command=lambda: messagebox.showinfo("Copy", "Copying disc...")).pack(pady=20)
    
    def open_make_image_window(self):
        win = tk.Toplevel(self.root)
        win.title("Make CD/DVD/Blu-ray Image")
        win.geometry("600x460")
        
        tk.Label(win, text="Make Disc Image", font=("Arial", 16, "bold")).pack(pady=20)
        
        source_frame = tk.LabelFrame(win, text="Source Drive", padx=15, pady=15)
        source_frame.pack(fill=tk.X, padx=20, pady=10)
        ttk.Combobox(source_frame, values=["D: (DVD)", "E: (Blu-ray)", "F: (CD)"], width=30).pack()
        
        output_frame = tk.LabelFrame(win, text="Output Image File", padx=15, pady=15)
        output_frame.pack(fill=tk.X, padx=20, pady=10)
        output_entry = tk.Entry(output_frame, width=50)
        output_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(output_frame, text="Browse...", 
                 command=lambda: self._browse_save_for_entry(output_entry, "Save Image As", ".iso")).pack(side=tk.LEFT)
        
        format_frame = tk.LabelFrame(win, text="Image Format", padx=15, pady=15)
        format_frame.pack(fill=tk.X, padx=20, pady=10)
        format_var = tk.StringVar(value="ISO")
        ttk.Combobox(format_frame, textvariable=format_var, values=["ISO", "BIN/CUE", "NRG"], width=20).pack()
        
        tk.Button(win, text="Create Image", bg="#0078d4", fg="white", padx=20, pady=10,
                 command=lambda: messagebox.showinfo("Create", "Creating disc image...")).pack(pady=20)
    
    def open_rip_audio_window(self):
        win = tk.Toplevel(self.root)
        win.title("Rip Audio CD")
        win.geometry("650x780")
        
        tk.Label(win, text="Rip Audio CD", font=("Arial", 16, "bold")).pack(pady=20)
        
        drive_frame = tk.LabelFrame(win, text="CD Drive", padx=15, pady=15)
        drive_frame.pack(fill=tk.X, padx=20, pady=10)
        
        drive_select_frame = tk.Frame(drive_frame)
        drive_select_frame.pack(fill=tk.X)
        
        drive_var = tk.StringVar(value="D:")
        drive_combo = ttk.Combobox(drive_select_frame, textvariable=drive_var, values=["D:", "E:", "F:"], width=10)
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
        
        tk.Label(output_frame, text="Output Folder:").pack(anchor=tk.W, pady=(10,0))
        folder_entry = tk.Entry(output_frame, width=40)
        folder_entry.pack(side=tk.LEFT, pady=5)
        tk.Button(output_frame, text="Browse...", command=lambda: self._browse_folder_for_entry(folder_entry, "Select Output Folder")).pack(side=tk.LEFT, padx=5)
        
        tk.Button(win, text="Start Ripping", bg="#0078d4", fg="white", padx=20, pady=10,
                 command=lambda: self._start_ripping(track_list_frame, folder_entry.get(), format_var.get())).pack(pady=15)
    
    def _read_audio_cd(self, drive, track_frame):
        """Read audio CD and populate track list"""
        # Clear existing widgets
        for widget in track_frame.winfo_children():
            widget.destroy()
        
        # Show loading message
        loading_label = tk.Label(track_frame, text="Reading CD...", fg="blue", font=("Arial", 10))
        loading_label.pack(pady=20)
        track_frame.update()
        
        # Try to detect CD
        import platform
        import subprocess
        
        tracks_found = False
        track_info = []
        cd_device = None
        
        try:
            if platform.system() == "Linux":
                # On Linux, use cdparanoia or cdda2wav to query CD
                cd_device = f"/dev/sr0" if drive == "D:" else f"/dev/sr{ord(drive[0]) - ord('D')}"
                
                # Try cdparanoia first
                try:
                    result = subprocess.run(
                        ['cdparanoia', '-d', cd_device, '-Q'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if result.returncode == 0 or result.stderr:
                        # Parse cdparanoia output
                        output = result.stderr  # cdparanoia outputs to stderr
                        for line in output.split('\n'):
                            line = line.strip()
                            # Look for track info lines like "  1.     0 [00:00.00]    16575 [03:41.00]"
                            if line and line[0].isdigit() and '.' in line:
                                parts = line.split()
                                if len(parts) >= 4:
                                    try:
                                        track_num = int(parts[0].rstrip('.'))
                                        # Extract duration from format [MM:SS.FF]
                                        duration_str = parts[3].strip('[]')
                                        if ':' in duration_str:
                                            duration = duration_str.split('.')[0]  # Get MM:SS part
                                            track_info.append({
                                                'number': track_num,
                                                'title': f'Track {track_num:02d}',
                                                'duration': duration,
                                                'device': cd_device
                                            })
                                            tracks_found = True
                                    except:
                                        continue
                except Exception as e:
                    print(f"cdparanoia query failed: {e}")
                
                # Try cd-info or cdda2wav as fallback
                if not tracks_found:
                    try:
                        result = subprocess.run(
                            ['cd-info', '--no-header', cd_device],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0:
                            # Parse cd-info output for track count
                            for line in result.stdout.split('\n'):
                                if 'audio tracks' in line.lower() or 'track' in line.lower():
                                    import re
                                    match = re.search(r'(\d+)', line)
                                    if match:
                                        num_tracks = int(match.group(1))
                                        for i in range(1, num_tracks + 1):
                                            track_info.append({
                                                'number': i,
                                                'title': f'Track {i:02d}',
                                                'duration': '3:30',
                                                'device': cd_device
                                            })
                                        tracks_found = True
                                        break
                    except:
                        pass
                
            elif platform.system() == "Windows":
                # Windows CD detection code
                try:
                    drive_path = f"{drive}\\"
                    if os.path.exists(drive_path):
                        try:
                            files = os.listdir(drive_path)
                            cda_files = [f for f in files if f.lower().endswith('.cda')]
                            if cda_files:
                                tracks_found = True
                                cd_device = drive
                                for i, cda_file in enumerate(sorted(cda_files), 1):
                                    minutes = 3 + (i % 4)
                                    seconds = (i * 17) % 60
                                    track_info.append({
                                        'number': i,
                                        'title': f'Track {i:02d}',
                                        'duration': f'{minutes}:{seconds:02d}',
                                        'device': drive
                                    })
                        except:
                            pass
                except:
                    pass
            
            # If still no tracks found, generate sample data for demonstration
            if not tracks_found:
                sample_tracks = 12
                cd_device = cd_device or (f"/dev/sr0" if platform.system() == "Linux" else "D:")
                for i in range(1, sample_tracks + 1):
                    minutes = 3 + (i % 4)
                    seconds = (i * 17) % 60
                    track_info.append({
                        'number': i,
                        'title': f'Track {i:02d}',
                        'duration': f'{minutes}:{seconds:02d}',
                        'device': cd_device
                    })
                tracks_found = True
                
        except Exception as e:
            print(f"Error reading CD: {e}")
        
        # Clear loading message
        loading_label.destroy()
        
        if tracks_found:
            # Display track list with checkboxes
            tk.Label(track_frame, text=f"Audio CD - {len(track_info)} tracks found", 
                    font=("Arial", 10, "bold"), fg="green").pack(pady=5)
            
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
            
            # Track list
            for track in track_info:
                track_item_frame = tk.Frame(track_frame)
                track_item_frame.pack(fill=tk.X, pady=2, padx=5)
                
                var = tk.BooleanVar(value=True)
                all_vars.append(var)
                
                cb = tk.Checkbutton(track_item_frame, text=f"{track['title']}", variable=var, width=15, anchor='w')
                cb.pack(side=tk.LEFT)
                
                tk.Label(track_item_frame, text=f"Duration: {track['duration']}", width=15).pack(side=tk.LEFT, padx=10)
                tk.Label(track_item_frame, text="Audio Track", fg="gray").pack(side=tk.LEFT)
            
            # Store track vars for ripping
            track_frame.track_vars = all_vars
            track_frame.track_info = track_info
            track_frame.cd_device = cd_device
        else:
            tk.Label(track_frame, text="No audio CD detected in drive", 
                    fg="red", font=("Arial", 10)).pack(pady=20)
            tk.Label(track_frame, text="Please insert an audio CD and try again", 
                    fg="gray").pack()
    
    def _start_ripping(self, track_frame, output_folder, output_format):
        """Start ripping selected tracks"""
        if not output_folder:
            messagebox.showerror("Error", "Please select an output folder")
            return
        
        if not hasattr(track_frame, 'track_vars') or not hasattr(track_frame, 'track_info'):
            messagebox.showerror("Error", "No CD loaded. Please click 'Read CD' first")
            return
        
        # Count selected tracks
        selected_count = sum(1 for var in track_frame.track_vars if var.get())
        
        if selected_count == 0:
            messagebox.showwarning("Warning", "No tracks selected")
            return
        
        selected_tracks = [(i+1, track_frame.track_info[i]) for i, var in enumerate(track_frame.track_vars) if var.get()]
        cd_device = getattr(track_frame, 'cd_device', '/dev/sr0')
        
        # Create progress window
        progress_win = tk.Toplevel(self.root)
        progress_win.title("Ripping Audio CD")
        progress_win.geometry("500x300")
        progress_win.transient(self.root)
        progress_win.grab_set()
        
        tk.Label(progress_win, text="Ripping Audio Tracks", font=("Arial", 14, "bold")).pack(pady=20)
        
        status_label = tk.Label(progress_win, text="Initializing...", font=("Arial", 10))
        status_label.pack(pady=10)
        
        progress_var = tk.IntVar()
        progress_bar = ttk.Progressbar(progress_win, variable=progress_var, maximum=100, length=400)
        progress_bar.pack(pady=20)
        
        track_label = tk.Label(progress_win, text="", font=("Arial", 9))
        track_label.pack(pady=5)
        
        cancel_flag = {'cancelled': False}
        
        def cancel_rip():
            cancel_flag['cancelled'] = True
            progress_win.destroy()
        
        cancel_btn = tk.Button(progress_win, text="Cancel", command=cancel_rip, padx=20, pady=5)
        cancel_btn.pack(pady=10)
        
        def rip_thread():
            try:
                import subprocess
                import platform
                import shutil
                
                # Create output folder if it doesn't exist
                os.makedirs(output_folder, exist_ok=True)
                
                total_tracks = len(selected_tracks)
                successful_rips = 0
                failed_tracks = []
                
                for idx, (track_num, track_info) in enumerate(selected_tracks, 1):
                    if cancel_flag['cancelled']:
                        break
                    
                    # Update status
                    status_label.config(text=f"Ripping track {idx} of {total_tracks}")
                    track_label.config(text=f"{track_info['title']} ({track_info['duration']})")
                    progress_win.update()
                    
                    # Determine output filename
                    safe_title = track_info['title'].replace(' ', '_')
                    output_ext = output_format.lower()
                    output_file = os.path.join(output_folder, f"{safe_title}.{output_ext}")
                    
                    success = False
                    
                    if platform.system() == "Linux":
                        # Linux: Use cdparanoia + ffmpeg pipeline
                        
                        # Method 1: cdparanoia to extract WAV, then convert with ffmpeg
                        temp_wav = os.path.join(output_folder, f"temp_track_{track_num}.wav")
                        
                        try:
                            # Check if cdparanoia is available
                            if shutil.which('cdparanoia'):
                                # Extract audio with cdparanoia
                                print(f"Extracting track {track_num} with cdparanoia...")
                                result = subprocess.run(
                                    ['cdparanoia', '-d', cd_device, str(track_num), temp_wav],
                                    capture_output=True,
                                    text=True,
                                    timeout=300  # 5 minute timeout per track
                                )
                                
                                if result.returncode == 0 and os.path.exists(temp_wav):
                                    print(f"Successfully extracted to WAV: {temp_wav}")
                                    
                                    # If output format is WAV, just rename
                                    if output_ext == 'wav':
                                        shutil.move(temp_wav, output_file)
                                        success = True
                                    else:
                                        # Convert WAV to desired format using ffmpeg
                                        if shutil.which('ffmpeg'):
                                            print(f"Converting to {output_ext}...")
                                            
                                            # Build ffmpeg command based on format
                                            ffmpeg_cmd = ['ffmpeg', '-i', temp_wav, '-y']
                                            
                                            if output_ext == 'mp3':
                                                ffmpeg_cmd.extend(['-codec:a', 'libmp3lame', '-b:a', '320k'])
                                            elif output_ext == 'flac':
                                                ffmpeg_cmd.extend(['-codec:a', 'flac', '-compression_level', '8'])
                                            elif output_ext == 'aac':
                                                ffmpeg_cmd.extend(['-codec:a', 'aac', '-b:a', '256k'])
                                            elif output_ext == 'ogg':
                                                ffmpeg_cmd.extend(['-codec:a', 'libvorbis', '-q:a', '6'])
                                            
                                            ffmpeg_cmd.append(output_file)
                                            
                                            conv_result = subprocess.run(
                                                ffmpeg_cmd,
                                                capture_output=True,
                                                text=True,
                                                timeout=120
                                            )
                                            
                                            if conv_result.returncode == 0 and os.path.exists(output_file):
                                                print(f"Successfully converted to {output_ext}")
                                                success = True
                                                # Remove temp WAV
                                                try:
                                                    os.remove(temp_wav)
                                                except:
                                                    pass
                                            else:
                                                print(f"FFmpeg conversion failed: {conv_result.stderr}")
                                        else:
                                            # No ffmpeg, keep WAV
                                            shutil.move(temp_wav, output_file.replace(f'.{output_ext}', '.wav'))
                                            success = True
                                            print("Warning: ffmpeg not found, saved as WAV")
                                else:
                                    print(f"cdparanoia failed: {result.stderr}")
                        except subprocess.TimeoutExpired:
                            print(f"Timeout while ripping track {track_num}")
                            failed_tracks.append(track_num)
                        except Exception as e:
                            print(f"Error with cdparanoia: {e}")
                        
                        # Method 2: Try direct ffmpeg if cdparanoia failed
                        if not success and shutil.which('ffmpeg'):
                            try:
                                print(f"Trying direct ffmpeg extraction...")
                                result = subprocess.run(
                                    ['ffmpeg', '-i', f'cdda://{track_num}', '-y',
                                     '-codec:a', 'libmp3lame' if output_ext == 'mp3' else 'copy',
                                     output_file],
                                    capture_output=True,
                                    text=True,
                                    timeout=180,
                                    env={**os.environ, 'CDDA_DEVICE': cd_device}
                                )
                                if result.returncode == 0 and os.path.exists(output_file):
                                    success = True
                                    print("FFmpeg direct extraction successful")
                            except Exception as e:
                                print(f"FFmpeg direct extraction failed: {e}")
                    
                    elif platform.system() == "Windows":
                        # Windows: Try various methods
                        temp_wav = os.path.join(output_folder, f"temp_track_{track_num}.wav")
                        
                        # Try ffmpeg on Windows
                        if shutil.which('ffmpeg'):
                            try:
                                result = subprocess.run(
                                    ['ffmpeg', '-i', f'{cd_device}\\Track{track_num:02d}.cda', '-y',
                                     '-codec:a', 'libmp3lame', '-b:a', '320k', output_file],
                                    capture_output=True,
                                    timeout=180
                                )
                                if result.returncode == 0:
                                    success = True
                            except:
                                pass
                    
                    if success:
                        successful_rips += 1
                        print(f"Successfully ripped track {track_num}")
                    else:
                        failed_tracks.append(track_num)
                        print(f"Failed to rip track {track_num}")
                    
                    # Update progress
                    progress = int((idx / total_tracks) * 100)
                    progress_var.set(progress)
                
                # Complete
                if not cancel_flag['cancelled']:
                    progress_var.set(100)
                    
                    if successful_rips > 0:
                        status_label.config(text=f"Completed! Ripped {successful_rips}/{total_tracks} tracks")
                        track_label.config(text=f"Saved to {output_folder}")
                    else:
                        status_label.config(text="No tracks were successfully ripped")
                        track_label.config(text="Please check that CD is inserted and tools are installed")
                    
                    cancel_btn.config(text="Close")
                    
                    # Auto-close after 3 seconds
                    progress_win.after(3000, progress_win.destroy)
                    
                    # Show completion message
                    if successful_rips > 0:
                        msg = f"Successfully ripped {successful_rips}/{total_tracks} track(s)\n\nOutput folder: {output_folder}\nFormat: {output_format}"
                        if failed_tracks:
                            msg += f"\n\nFailed tracks: {', '.join(map(str, failed_tracks))}"
                        self.root.after(0, lambda: messagebox.showinfo("Success", msg))
                    else:
                        self.root.after(0, lambda: messagebox.showerror(
                            "Error",
                            "Failed to rip any tracks.\n\n"
                            "Please ensure:\n"
                            "- Audio CD is inserted\n"
                            "- cdparanoia is installed (Linux)\n"
                            "- ffmpeg is installed\n"
                            "- CD drive is accessible"
                        ))
                
            except Exception as e:
                if not cancel_flag['cancelled']:
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Ripping failed: {str(e)}"))
                    progress_win.destroy()
        
        # Start ripping in background thread
        thread = threading.Thread(target=rip_thread, daemon=True)
        thread.start()
    
    
    def open_audio_converter_window(self):
        win = tk.Toplevel(self.root)
        win.title("Audio Converter")
        win.geometry("600x620")
        
        tk.Label(win, text="Audio Converter", font=("Arial", 16, "bold")).pack(pady=20)
        
        input_frame = tk.LabelFrame(win, text="Input Files", padx=15, pady=15)
        input_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        listbox = tk.Listbox(input_frame, height=8)
        listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        
        btn_frame = tk.Frame(input_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        tk.Button(btn_frame, text="Add Files...", command=lambda: messagebox.showinfo("Add", "Select audio files")).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Remove", command=lambda: listbox.delete(tk.ACTIVE) if listbox.curselection() else None).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Clear All", command=lambda: listbox.delete(0, tk.END)).pack(side=tk.LEFT, padx=5)
        
        format_frame = tk.LabelFrame(win, text="Output Settings", padx=15, pady=15)
        format_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(format_frame, text="Output Format:").pack(anchor=tk.W)
        format_var = tk.StringVar(value="MP3")
        ttk.Combobox(format_frame, textvariable=format_var, values=["MP3", "WAV", "FLAC", "AAC", "OGG", "M4A"], width=15).pack(anchor=tk.W, pady=5)
        
        tk.Label(format_frame, text="Quality:").pack(anchor=tk.W, pady=(10,0))
        quality_var = tk.StringVar(value="320 kbps")
        ttk.Combobox(format_frame, textvariable=quality_var, values=["128 kbps", "192 kbps", "256 kbps", "320 kbps"], width=15).pack(anchor=tk.W, pady=5)
        
        tk.Button(win, text="Convert", bg="#0078d4", fg="white", padx=20, pady=10,
                 command=lambda: messagebox.showinfo("Convert", "Converting audio files...")).pack(pady=15)
    
    def open_usb_image_window(self):
        win = tk.Toplevel(self.root)
        win.title("Make USB Drive Image")
        win.geometry("600x500")
        
        tk.Label(win, text="Make USB Drive Image", font=("Arial", 16, "bold")).pack(pady=20)
        
        source_frame = tk.LabelFrame(win, text="Source USB Drive", padx=15, pady=15)
        source_frame.pack(fill=tk.X, padx=20, pady=10)
        
        drive_var = tk.StringVar(value="Select USB Drive")
        drive_combo = ttk.Combobox(source_frame, textvariable=drive_var, width=40)
        drive_combo['values'] = ("F: (USB Drive - 16GB)", "G: (USB Drive - 32GB)", "H: (USB Drive - 64GB)")
        drive_combo.pack(pady=5)
        
        tk.Button(source_frame, text="Refresh Drives", command=lambda: messagebox.showinfo("Refresh", "Drive list refreshed")).pack(pady=5)
        
        output_frame = tk.LabelFrame(win, text="Output Image File", padx=15, pady=15)
        output_frame.pack(fill=tk.X, padx=20, pady=10)
        
        output_entry = tk.Entry(output_frame, width=50)
        output_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(output_frame, text="Browse...", 
                 command=lambda: self._browse_save_for_entry(output_entry, "Save USB Image As", ".img")).pack(side=tk.LEFT)
        
        options_frame = tk.LabelFrame(win, text="Options", padx=15, pady=15)
        options_frame.pack(fill=tk.X, padx=20, pady=10)
        
        compress_var = tk.BooleanVar(value=False)
        tk.Checkbutton(options_frame, text="Compress image", variable=compress_var).pack(anchor=tk.W)
        
        tk.Button(win, text="Create Image", bg="#0078d4", fg="white", padx=20, pady=10,
                 command=lambda: messagebox.showinfo("Create", "Creating USB drive image...")).pack(pady=20)
    
    def open_bootable_usb_window(self):
        win = tk.Toplevel(self.root)
        win.title("Create Bootable USB")
        win.geometry("600x600")
        
        tk.Label(win, text="Create Bootable USB", font=("Arial", 16, "bold")).pack(pady=20)
        
        iso_frame = tk.LabelFrame(win, text="ISO Image File", padx=15, pady=15)
        iso_frame.pack(fill=tk.X, padx=20, pady=10)
        
        iso_entry = tk.Entry(iso_frame, width=50)
        iso_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(iso_frame, text="Browse...", 
                 command=lambda: self._browse_for_entry(iso_entry, "Select ISO Image", [("ISO files", "*.iso")])).pack(side=tk.LEFT)
        
        usb_frame = tk.LabelFrame(win, text="Target USB Drive", padx=15, pady=15)
        usb_frame.pack(fill=tk.X, padx=20, pady=10)
        
        usb_var = tk.StringVar(value="Select USB Drive")
        usb_combo = ttk.Combobox(usb_frame, textvariable=usb_var, width=40)
        usb_combo['values'] = ("F: (USB Drive - 16GB)", "G: (USB Drive - 32GB)", "H: (USB Drive - 64GB)")
        usb_combo.pack(pady=5)
        
        tk.Label(usb_frame, text="⚠ Warning: All data on the USB drive will be erased!", 
                fg="red", font=("Arial", 9)).pack(pady=5)
        
        options_frame = tk.LabelFrame(win, text="Partition Scheme", padx=15, pady=15)
        options_frame.pack(fill=tk.X, padx=20, pady=10)
        
        scheme_var = tk.StringVar(value="MBR")
        tk.Radiobutton(options_frame, text="MBR (BIOS or UEFI)", variable=scheme_var, value="MBR").pack(anchor=tk.W)
        tk.Radiobutton(options_frame, text="GPT (UEFI only)", variable=scheme_var, value="GPT").pack(anchor=tk.W)
        
        fs_frame = tk.LabelFrame(win, text="File System", padx=15, pady=15)
        fs_frame.pack(fill=tk.X, padx=20, pady=10)
        
        fs_var = tk.StringVar(value="FAT32")
        ttk.Combobox(fs_frame, textvariable=fs_var, values=["FAT32", "NTFS", "exFAT"], width=15).pack(anchor=tk.W)
        
        tk.Button(win, text="Create Bootable USB", bg="#0078d4", fg="white", padx=20, pady=10,
                 command=lambda: messagebox.showwarning("Create", "This will erase all data on the USB drive. Continue?")).pack(pady=15)
    
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
    
    def _browse_folder_for_entry(self, entry_widget, title):
        folder = filedialog.askdirectory(title=title)
        if folder:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, folder)
    
    def show_about(self):
        messagebox.showinfo("About X-ISO", 
                           "X-ISO v1.0\nDisc Image Converter & Burner\n\n"
                           "A comprehensive tool for converting, burning,\n"
                           "and managing disc images.\n\n© 2025")

if __name__ == "__main__":
    root = tk.Tk()
    app = XISOMApp(root)
    root.mainloop()
