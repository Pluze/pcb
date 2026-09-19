"""External desktop interface to the same PCB CLI used by humans and agents."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

# A directly opened file enters the public launcher, which selects KiCad's wx runtime.
if __name__ == '__main__' and not __package__:
    os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve().parents[2] / 'pcb'), *sys.argv[1:], 'gui'])

from .cli import REPOSITORY, TOOL_ROOT, find_runtime
from .presentation import RUNNING, artifact_label, summarize

ACTIONS = {
    'Finish design': ['finish'],
    'Route candidate': ['route'],
    'Review board': ['review'],
    'Build U4 + DXF + Gerber': ['build'],
    'Verify delivery': ['verify'],
}


def command_for(action, design, candidate_only=False):
    command = [*ACTIONS[action], '--design', design]
    if action == 'Finish design' and candidate_only:
        command.append('--candidate-only')
    return command


def collect_paths(value):
    """Collect concrete receipt artifacts for the human results list."""
    paths = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ('png', 'svg', 'drc', 'report', 'candidate', 'details', 'backup') and isinstance(item, str):
                path = Path(item)
                if path.exists():
                    paths.append(path)
            elif isinstance(item, (dict, list)):
                paths.extend(collect_paths(item))
    elif isinstance(value, list):
        for item in value:
            paths.extend(collect_paths(item))
    return list(dict.fromkeys(paths))


def show_gui(root=REPOSITORY):
    """Open the external workflow window for saved repository designs."""
    import wx
    python = find_runtime(None, 'PCB_KICAD_PYTHON', [
        '/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3',
        sys.executable,
    ])
    root = Path(root).resolve()
    designs = [p.parent.name for p in sorted((root / 'Designs').glob('*/*.kicad_pcb')) if p.stem == p.parent.name]

    class ToolDialog(wx.Dialog):
        def __init__(self):
            super().__init__(None, title='PCB Tools — KiCad workflow', size=(900, 860),
                             style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
            self.busy = False
            self.paths = []
            self.route_receipt = None
            self.started = 0
            panel = wx.Panel(self)
            layout = wx.BoxSizer(wx.VERTICAL)
            title = wx.StaticText(panel, label='PCB Tools')
            title.SetFont(wx.Font(20, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            layout.Add(title, 0, wx.ALL, 14)
            layout.Add(wx.StaticText(panel, label='1. Save your work in KiCad     2. Choose a project     3. Run a workflow below'), 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 14)
            self.design = wx.Choice(panel, choices=designs)
            self.design.SetSelection(0 if designs else wx.NOT_FOUND)
            self.design.Bind(wx.EVT_CHOICE, self.select_design)
            layout.Add(self.design, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 14)
            self.buttons = []

            def action_button(parent, label, action):
                button = wx.Button(parent, label=label)
                button.Bind(wx.EVT_BUTTON, lambda event: self.start(command_for(action, self.design.GetStringSelection(), self.candidate_only.GetValue())))
                self.buttons.append(button)
                return button

            complete = action_button(panel, 'Run complete workflow', 'Finish design')
            complete.SetMinSize((-1, 36))
            layout.Add(complete, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 14)
            layout.Add(wx.StaticText(panel, label='Checks the schematic, creates new routing, applies it, and builds all production formats.'),
                       0, wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, 14)
            steps = wx.BoxSizer(wx.HORIZONTAL)
            check = wx.StaticBoxSizer(wx.VERTICAL, panel, '1 · Check design')
            check.Add(wx.StaticText(check.GetStaticBox(), label='Inspect the saved board\nwithout changing it.'), 0, wx.ALL, 8)
            check.Add(action_button(check.GetStaticBox(), 'Check board', 'Review board'), 0, wx.EXPAND | wx.ALL, 8)
            routing = wx.StaticBoxSizer(wx.VERTICAL, panel, '2 · Route and review')
            routing.Add(wx.StaticText(routing.GetStaticBox(), label='Create a candidate, inspect it,\nthen apply the reviewed route.'), 0, wx.ALL, 8)
            routing.Add(action_button(routing.GetStaticBox(), 'Create routing candidate', 'Route candidate'), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
            self.adopt = wx.Button(routing.GetStaticBox(), label='Apply reviewed route')
            self.adopt.Enable(False)
            self.adopt.Bind(wx.EVT_BUTTON, self.apply_route)
            routing.Add(self.adopt, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
            production = wx.StaticBoxSizer(wx.VERTICAL, panel, '3 · Production files')
            production.Add(wx.StaticText(production.GetStaticBox(), label='Build U4, LightBurn DXF\nand fabricator Gerber together.'), 0, wx.ALL, 8)
            production.Add(action_button(production.GetStaticBox(), 'Build production files', 'Build U4 + DXF + Gerber'), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
            production.Add(action_button(production.GetStaticBox(), 'Verify existing files', 'Verify delivery'), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
            for group in (check, routing, production):
                steps.Add(group, 1, wx.EXPAND | wx.RIGHT, 8)
            layout.Add(steps, 0, wx.EXPAND | wx.ALL, 14)
            self.candidate_only = wx.CheckBox(panel, label='Pause complete workflow after routing so I can inspect the candidate before applying it')
            self.candidate_only.SetValue(False)
            layout.Add(self.candidate_only, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 14)
            self.status = wx.StaticText(panel, label='Ready · Close the board editor before applying a route; reopen it afterward.')
            layout.Add(self.status, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 14)
            self.progress = wx.Gauge(panel, range=100)
            layout.Add(self.progress, 0, wx.EXPAND | wx.ALL, 14)
            self.summary = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
            self.summary.SetValue('Choose a design and an operation. Results and suggested next steps appear here.')
            layout.Add(self.summary, 2, wx.EXPAND | wx.LEFT | wx.RIGHT, 14)
            self.details = wx.CollapsiblePane(panel, label='Technical details')
            details_panel = self.details.GetPane()
            details_layout = wx.BoxSizer(wx.VERTICAL)
            self.log = wx.TextCtrl(details_panel, size=(-1, 140), style=wx.TE_MULTILINE | wx.TE_READONLY)
            details_layout.Add(self.log, 1, wx.EXPAND)
            details_panel.SetSizer(details_layout)
            self.details.Bind(wx.EVT_COLLAPSIBLEPANE_CHANGED, lambda event: self.Layout())
            layout.Add(self.details, 0, wx.EXPAND | wx.ALL, 14)
            self.artifacts = wx.ListBox(panel)
            self.artifacts.Bind(wx.EVT_LISTBOX_DCLICK, self.open_artifact)
            layout.Add(self.artifacts, 1, wx.EXPAND | wx.ALL, 14)
            footer = wx.BoxSizer(wx.HORIZONTAL)
            open_button = wx.Button(panel, label='Open selected result')
            open_button.Bind(wx.EVT_BUTTON, self.open_artifact)
            output_button = wx.Button(panel, label='Open production files')
            output_button.Bind(wx.EVT_BUTTON, lambda event: wx.LaunchDefaultApplication(str(root / 'Designs' / self.design.GetStringSelection() / 'fabrication')))
            help_button = wx.Button(panel, label='Tool guide')
            help_button.Bind(wx.EVT_BUTTON, lambda event: wx.LaunchDefaultApplication(str(TOOL_ROOT / 'README.md')))
            for button in (open_button, output_button, help_button):
                footer.Add(button, 0, wx.RIGHT, 8)
            layout.Add(footer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 14)
            panel.SetSizer(layout)
            outer = wx.BoxSizer(wx.VERTICAL)
            outer.Add(panel, 1, wx.EXPAND)
            self.SetSizer(outer)
            self.SetMinSize((860, 780))
            self.timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self.tick, self.timer)
            self.Bind(wx.EVT_CLOSE, self.close)

        def select_design(self, event):
            self.route_receipt = None
            self.adopt.Enable(False)
            self.paths = []
            self.artifacts.Clear()
            self.summary.SetValue('Choose an operation for this design.')
            self.status.SetLabel('Ready')
            self.log.Clear()

        def tick(self, event):
            self.progress.Pulse()

        def close(self, event):
            if self.busy:
                self.status.SetLabel('Workflow running; close the window when it completes.')
                event.Veto()
            else:
                self.EndModal(wx.ID_CLOSE)

        def start(self, command):
            if self.busy:
                return
            if not self.design.GetStringSelection():
                self.status.SetLabel('Select a saved repository design.')
                return
            self.command = command
            self.busy = True
            self.paths = []
            self.artifacts.Clear()
            self.summary.SetValue(RUNNING[command[0]])
            self.log.Clear()
            self.details.Collapse(True)
            self.started = time.monotonic()
            self.route_receipt = None
            for button in self.buttons:
                button.Enable(False)
            self.adopt.Enable(False)
            self.design.Enable(False)
            self.status.SetLabel(RUNNING[command[0]])
            self.log.AppendText('\n$ pcb ' + ' '.join(command) + '\n')
            self.timer.Start(150)
            threading.Thread(target=self.run_command, args=(command,), daemon=True).start()

        def run_command(self, command):
            env = {**os.environ, 'PYTHONPATH': str(TOOL_ROOT.parent), 'PYTHONDONTWRITEBYTECODE': '1'}
            try:
                with tempfile.TemporaryFile(mode='w+') as output:
                    process = subprocess.Popen([str(python), '-m', 'pcbflow', '--root', str(root), '--json', *command],
                                               cwd=root, env=env, stdout=output, stderr=subprocess.PIPE, text=True)
                    for line in process.stderr:
                        wx.CallAfter(self.log.AppendText, line)
                    code = process.wait()
                    output.seek(0)
                    text = output.read()
                try:
                    result = json.loads(text)
                except ValueError:
                    result = {'status': 'fail', 'error': text}
            except OSError as error:
                result, code = {'status': 'fail', 'error': str(error)}, 2
            wx.CallAfter(self.completed, result, code)

        def completed(self, result, code):
            self.timer.Stop()
            self.progress.SetValue(100 if code == 0 else 0)
            self.busy = False
            for button in self.buttons:
                button.Enable(True)
            self.design.Enable(True)
            elapsed = round(time.monotonic() - self.started, 1)
            self.log.AppendText(json.dumps(result, indent=2) + '\n')
            self.paths = collect_paths(result)
            evidence = []
            details = result.get('details')
            if details:
                for receipt in Path(details).glob('*.json'):
                    data = json.loads(receipt.read_text())
                    evidence.append(data)
                    self.paths.extend(collect_paths(data))
                    if isinstance(data, dict) and 'candidate' in data and 'inputs' in data:
                        self.route_receipt = receipt
            title, summary = summarize(self.command, result, evidence, code)
            self.status.SetLabel(f'{title} · {elapsed} s')
            self.summary.SetValue(summary)
            if self.command[0] in ('build', 'verify', 'finish'):
                fabrication = root / 'Designs' / self.design.GetStringSelection() / 'fabrication'
                self.paths.extend(p for p in (fabrication / kind for kind in ('u4', 'lightburn', 'gerber')) if p.is_dir())
            self.paths = list(dict.fromkeys(self.paths))
            self.artifacts.Set([artifact_label(path) for path in self.paths])
            if self.paths:
                self.artifacts.SetSelection(0)
            self.adopt.Enable(self.route_receipt is not None)

        def apply_route(self, event):
            self.start(['adopt', '--design', self.design.GetStringSelection(), '--receipt', str(self.route_receipt)])

        def open_artifact(self, event):
            selection = self.artifacts.GetSelection()
            if selection != wx.NOT_FOUND:
                wx.LaunchDefaultApplication(str(self.paths[selection]))

    dialog = ToolDialog()
    dialog.ShowModal()
    dialog.Destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=REPOSITORY)
    args = parser.parse_args()
    import wx
    app = wx.App(False)
    show_gui(args.root)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
