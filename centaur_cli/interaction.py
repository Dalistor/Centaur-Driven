"""Perguntas do agente e cancelamento compartilhado entre executores."""

import curses


class TurnCancelled(RuntimeError):
    pass


ASK_USER = {'type': 'function', 'function': {
    'name': 'ask_user',
    'description': 'Perguntar ao usuário quando uma decisão necessária não puder ser inferida. Não use para aprovar ferramentas.',
    'parameters': {'type': 'object', 'additionalProperties': False,
                   'properties': {'question': {'type': 'string', 'maxLength': 600},
                                  'options': {'type': 'array', 'maxItems': 3,
                                              'items': {'type': 'string', 'maxLength': 160}}},
                   'required': ['question', 'options']}}}


def validate_question(arguments):
    question, options = arguments['question'], arguments['options']
    if not isinstance(question, str) or not question.strip() or len(question) > 600:
        raise ValueError('Pergunta deve ter 1 a 600 caracteres.')
    if (not isinstance(options, list) or len(options) > 3
            or any(not isinstance(option, str) or not option.strip() or len(option) > 160 for option in options)
            or len(set(options)) != len(options)):
        raise ValueError('Use até três opções distintas, com 1 a 160 caracteres.')
    return question.strip(), options


class QuestionPicker:
    def __init__(self, question, options, answer):
        self.question, self.options, self.answer = question, options, answer
        self.selected = 0
        self.text = ''
        self.cursor = 0
        self.error = ''
        self.scroll = None
        self.view_start = 0

    @property
    def custom(self):
        return self.selected == len(self.options)

    def handle(self, key, secrets=()):
        if key == '\x1b':
            return {'status': 'skipped', 'answer': None}
        if key in (curses.KEY_UP, curses.KEY_DOWN, '\t'):
            delta = -1 if key == curses.KEY_UP else 1
            self.selected = (self.selected + delta) % (len(self.options) + 1)
            self.scroll = None
        elif key == curses.KEY_PPAGE:
            self.scroll = max(0, self.view_start - 3)
        elif key == curses.KEY_NPAGE:
            self.scroll = self.view_start + 3
        elif key in ('\n', '\r', curses.KEY_ENTER):
            value = self.text.strip() if self.custom else self.options[self.selected]
            if not value:
                self.error = 'Digite sua resposta ou escolha uma opção.'
            elif any(secret and secret in value for secret in secrets):
                self.error = 'Chave detectada: resposta não enviada.'
            else:
                return {'status': 'answered', 'answer': value}
        elif self.custom:
            if key == curses.KEY_LEFT:
                self.cursor = max(0, self.cursor - 1)
            elif key == curses.KEY_RIGHT:
                self.cursor = min(len(self.text), self.cursor + 1)
            elif key == curses.KEY_HOME:
                self.cursor = 0
            elif key == curses.KEY_END:
                self.cursor = len(self.text)
            elif key in (curses.KEY_BACKSPACE, '\x7f', '\b') and self.cursor:
                self.text = self.text[:self.cursor - 1] + self.text[self.cursor:]
                self.cursor -= 1
            elif key == curses.KEY_DC:
                self.text = self.text[:self.cursor] + self.text[self.cursor + 1:]
            elif key == '\x15':
                self.text, self.cursor = '', 0
            elif isinstance(key, str) and key.isprintable() and len(self.text) < 4000:
                self.text = self.text[:self.cursor] + key + self.text[self.cursor:]
                self.cursor += 1
            self.error = ''
