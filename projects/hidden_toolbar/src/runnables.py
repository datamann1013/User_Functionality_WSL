import os
import subprocess
import sys
import gi
import logging
import traceback
from .utils import load_usage_data, add_last_used, toggle_favourite, is_favourite

logging.basicConfig(level=logging.DEBUG)

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

# Try to use Windows color theme, fallback to dark theme
css = """
window, listbox, entry, button {
    background-color: #23272e;
    color: #e6e6e6;
}
listbox row:selected, listbox row:selected label {
    background-color: #444b5a;
    color: #ffffff;
}
entry {
    background-color: #2b2b2b;
    color: #e6e6e6;
    border-radius: 4px;
    border: 1px solid #444b5a;
    padding: 4px;
}
button {
    background-color: #444b5a;
    color: #e6e6e6;
    border-radius: 4px;
    border: none;
    padding: 6px 12px;
}
"""

class ProgramLauncher(Gtk.Window):
    def __init__(self, programs):
        try:
            logging.debug(f"Initializing ProgramLauncher with {len(programs)} programs")
            super().__init__(title="Program Launcher")
            self.set_default_size(500, 600)  # Fixed window size
            self.set_position(Gtk.WindowPosition.CENTER)
            self.set_border_width(12)
            self.set_resizable(False)
            self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
            self.set_keep_above(True)
            self.set_decorated(True)
            logging.debug("Window properties set.")

            css_provider = Gtk.CssProvider()
            css_provider.load_from_data(css.encode())
            Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            self.add(vbox)

            # Search bar at the top
            self.entry = Gtk.Entry()
            self.entry.set_placeholder_text("Search for a program...")
            self.entry.connect("changed", self.on_search)
            vbox.pack_start(self.entry, False, False, 0)

            # Scrolled window for the listbox
            scrolled = Gtk.ScrolledWindow()
            scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            scrolled.set_min_content_height(400)
            scrolled.set_max_content_height(500)
            vbox.pack_start(scrolled, True, True, 0)

            self.listbox = Gtk.ListBox()
            self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
            self.listbox.connect("row-activated", self.on_row_activated)
            scrolled.add(self.listbox)

            self.button = Gtk.Button(label="Launch")
            self.button.connect("clicked", self.on_launch)
            vbox.pack_start(self.button, False, False, 0)

            self.programs = programs
            self.filtered_programs = self.programs.copy()
            self.usage_data = load_usage_data()
            self.populate_listbox()
        except Exception as e:
            logging.error(f"Exception in ProgramLauncher.__init__: {e}\n{traceback.format_exc()}")
            raise

    def get_display_programs(self):
        # Get last used and favourites from usage data
        last_used = [p for p in self.usage_data.get('last_used', []) if p in self.programs][:5]
        favourites = [p for p in self.usage_data.get('favourites', []) if p in self.programs and p not in last_used][:5]
        # Others: not in last_used or favourites
        others = [p for p in self.programs if p not in last_used and p not in favourites]
        # Sort: special chars/numbers first, then A-Z
        def sort_key(x):
            if x and not x[0].isalpha():
                return (0, x.lower())
            return (1, x.lower())
        others = sorted(others, key=sort_key)[:10]
        return last_used, favourites, others

    def populate_listbox(self):
        try:
            logging.debug(f"Populating listbox with custom sections")
            for child in self.listbox.get_children():
                self.listbox.remove(child)
            last_used, favourites, others = self.get_display_programs()
            def add_section(title, items):
                if items:
                    header = Gtk.Label(label=f"--- {title} ---", xalign=0)
                    header.set_justify(Gtk.Justification.LEFT)
                    header.set_markup(f'<b>{title}</b>')
                    row = Gtk.ListBoxRow()
                    row.add(header)
                    row.set_sensitive(False)
                    self.listbox.add(row)
                    for prog in items:
                        row = Gtk.ListBoxRow()
                        label = Gtk.Label(label=prog + (" ★" if is_favourite(prog) else ""), xalign=0)
                        row.add(label)
                        self.listbox.add(row)
            add_section("Last Used", last_used)
            add_section("Favourites", favourites)
            add_section("Others", others)
            self.listbox.show_all()
            logging.debug("Listbox populated and shown.")
        except Exception as e:
            logging.error(f"Exception in populate_listbox: {e}\n{traceback.format_exc()}")
            raise

    def on_search(self, entry):
        text = entry.get_text().lower()
        logging.debug(f"Search text changed: '{text}'")
        self.filtered_programs = [p for p in self.programs if text in p.lower()]
        self.usage_data = load_usage_data()
        self.populate_listbox()

    def on_row_activated(self, listbox, row):
        idx = row.get_index()
        # Skip section headers
        widget = row.get_child()
        if isinstance(widget, Gtk.Label) and widget.get_text().startswith("---"):
            return
        # Find the program name from the label
        prog = widget.get_text().replace(" ★", "").strip()
        logging.debug(f"Row activated: {prog}")
        if prog in self.programs:
            add_last_used(prog)
            self.launch_program(prog)

    def on_launch(self, button):
        selected = self.listbox.get_selected_row()
        logging.debug(f"Launch button clicked. Selected row: {selected}")
        if selected:
            widget = selected.get_child()
            if isinstance(widget, Gtk.Label) and widget.get_text().startswith("---"):
                return
            prog = widget.get_text().replace(" ★", "").strip()
            if prog in self.programs:
                add_last_used(prog)
                self.launch_program(prog)

    def launch_program(self, prog):
        logging.debug(f"Launching program: {prog}")
        try:
            subprocess.Popen([prog])
        except Exception as e:
            logging.error(f"Failed to launch {prog}: {e}")
            dialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.ERROR, Gtk.ButtonsType.OK,
                                      f"Failed to launch {prog}: {e}")
            dialog.run()
            dialog.destroy()

def show_launcher(programs):
    logging.debug("Calling show_launcher")
    win = ProgramLauncher(programs)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
