"""Seleção de skills no token que está sendo digitado."""

import re

from . import skill_catalog

TOKEN = re.compile(r'(?<!\S)([$@])([\w.-]*)$')
LOCAL_COMMANDS = ('compact', 'config', 'credits', 'status')


class SkillCompletion:
    def __init__(self, root):
        self.root = root
        self.context = None
        self.selected = 0
        self.dismissed = None
        self.options = []

    def update(self, draft):
        if self.dismissed is not None and draft != self.dismissed:
            self.dismissed = None
        match = TOKEN.search(draft)
        context = (match.start(), match.group(1), match.group(2)) if match else None
        if context != self.context:
            self.selected = 0
            self.context = context
        self.options = []
        if not match or self.dismissed == draft:
            return
        names = sorted([*skill_catalog.names(), *LOCAL_COMMANDS]) if match.group(1) == '$' else skill_catalog.additional_names(self.root)
        self.options = [name for name in names if name.casefold().startswith(match.group(2).casefold())]
        self.selected = min(self.selected, max(0, len(self.options) - 1))

    @property
    def visible(self):
        return self.context is not None and self.options != []

    def choose(self, draft):
        if not self.visible:
            return draft
        start, prefix, _ = self.context
        return draft[:start] + prefix + self.options[self.selected] + ' '

    def local_command(self, draft):
        return (self.visible and self.context[1] == '$'
                and not draft[:self.context[0]].strip()
                and '\n' not in draft
                and self.options[self.selected] in LOCAL_COMMANDS)

    def dismiss(self, draft):
        self.dismissed = draft
        self.options = []
