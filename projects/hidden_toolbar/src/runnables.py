import os
import subprocess
import sys
import gi

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
        super().__init__(title="Program Launcher")
        self.set_default_size(500, 600)  # Reduce height to avoid Gdk-WARNING
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_border_width(12)
        self.set_resizable(False)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_keep_above(True)
        self.set_decorated(True)

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add(vbox)

        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Search for a program...")
        self.entry.connect("changed", self.on_search)
        vbox.pack_start(self.entry, False, False, 0)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.connect("row-activated", self.on_row_activated)
        vbox.pack_start(self.listbox, True, True, 0)

        self.button = Gtk.Button(label="Launch")
        self.button.connect("clicked", self.on_launch)
        vbox.pack_start(self.button, False, False, 0)

        self.programs = programs
        self.filtered_programs = self.programs.copy()
        self.populate_listbox()

    def populate_listbox(self):
        for child in self.listbox.get_children():
            self.listbox.remove(child)
        for prog in self.filtered_programs:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=prog, xalign=0)
            row.add(label)
            self.listbox.add(row)
        self.listbox.show_all()

    def on_search(self, entry):
        text = entry.get_text().lower()
        self.filtered_programs = [p for p in self.programs if text in p.lower()]
        self.populate_listbox()

    def on_row_activated(self, listbox, row):
        idx = row.get_index()
        if 0 <= idx < len(self.filtered_programs):
            self.launch_program(self.filtered_programs[idx])

    def on_launch(self, button):
        selected = self.listbox.get_selected_row()
        if selected:
            idx = selected.get_index()
            if 0 <= idx < len(self.filtered_programs):
                self.launch_program(self.filtered_programs[idx])

    def launch_program(self, prog):
        try:
            subprocess.Popen([prog])
        except Exception as e:
            dialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.ERROR, Gtk.ButtonsType.OK,
                                      f"Failed to launch {prog}: {e}")
            dialog.run()
            dialog.destroy()

def show_launcher(programs):
    win = ProgramLauncher(programs)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
