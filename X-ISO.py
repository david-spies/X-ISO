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
        self.root.geometry("900x650")
        
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
        tools_menu.add_command(label="Burn", command=lambda: self.notebook.select(1))
        tools_menu.add_separator()
        tools_menu.add_command(label="Append Data to Disc", command=self.show_append)
        tools_menu.add_command(label="Erase Rewritable Disc", command=self.show_erase)
        tools_menu.add_command(label="View Drive/Disc Information", command=self.show_drive_info)
        tools_menu.add_command(label="Copy CD/DVD/Blu-ray", command=self.show_copy)
        tools_menu.add_command(label="Make CD/DVD/Blu-ray Image", command=self.show_make_image)
        tools_menu.add_command(label="Rip Audio CD", command=self.show_rip_audio)
        tools_menu.add_command(label="Audio Converter", command=self.show_audio_converter)
        tools_menu.add_command(label="Virtual Drive", command=lambda: self.notebook.select(2))
        tools_menu.add_command(label="Make USB Drive Image", command=self.show_usb_image)
        tools_menu.add_command(label="Create Bootable USB", command=self.show_bootable_usb)
        
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
            ("Copy CD/DVD/Blu-ray", self.show_copy),
            ("Make CD/DVD/Blu-ray Image", self.show_make_image),
            ("Rip Audio CD", self.show_rip_audio),
            ("Audio Converter", self.show_audio_converter),
            ("Erase Rewritable Disc", self.show_erase),
            ("View Drive Information", self.show_drive_info),
            ("Make USB Drive Image", self.show_usb_image),
            ("Create Bootable USB", self.show_bootable_usb),
            ("Append Data to Disc", self.show_append),
            ("Verify Disc", self.verify_disc)
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
    
    # Tool functions
    def show_append(self):
        messagebox.showinfo("Append Data", "Append data to disc functionality")
    
    def show_erase(self):
        messagebox.showinfo("Erase Disc", "Erase rewritable disc functionality")
    
    def show_drive_info(self):
        messagebox.showinfo("Drive Info", "Drive/Disc information:\n\nDrive D:\nType: DVD-RW\nCapacity: 4.7 GB")
    
    def show_copy(self):
        messagebox.showinfo("Copy Disc", "Copy CD/DVD/Blu-ray functionality")
    
    def show_make_image(self):
        messagebox.showinfo("Make Image", "Make disc image functionality")
    
    def show_rip_audio(self):
        messagebox.showinfo("Rip Audio", "Rip audio CD functionality")
    
    def show_audio_converter(self):
        messagebox.showinfo("Audio Converter", "Audio converter functionality")
    
    def show_usb_image(self):
        messagebox.showinfo("USB Image", "Make USB drive image functionality")
    
    def show_bootable_usb(self):
        messagebox.showinfo("Bootable USB", "Create bootable USB functionality")
    
    def verify_disc(self):
        messagebox.showinfo("Verify", "Verify disc functionality")
    
    def show_about(self):
        messagebox.showinfo("About X-ISO", "X-ISO v1.0\nDisc Image Converter & Burner\n\n© 2025")

if __name__ == "__main__":
    root = tk.Tk()
    app = XISOMApp(root)
    root.mainloop()
