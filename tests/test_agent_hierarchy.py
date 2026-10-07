import curses
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from centaur_cli.agent_tree import AgentTree
from centaur_cli.history import ChatStore
from centaur_cli.terminal import Terminal
from test_terminal_settings import Screen


class AgentHierarchyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.store = ChatStore(self.root)
        self.terminal = Terminal(self.root, 'fixture', self.store, None)
        self.terminal.chat['title'] = 'Coordenador principal'
        self.store.save(self.terminal.chat)

    def child(self, parent, title):
        store = ChatStore(self.root)
        store.directory = self.root / '.centaur' / 'agents' / parent['id']
        child = store.new('fixture')
        child.update(parent_id=parent['id'], title=title)
        store.save(child)
        self.terminal.registry.set(child['id'], 'running')
        return child

    def test_recursive_tree_groups_children_with_parent_and_preserves_selection(self):
        parent = self.terminal.chat
        first = self.child(parent, 'Executor A')
        grandchild = self.child(first, 'Executor neto')
        second = self.child(parent, 'Executor B')
        self.terminal.open_chats('agents')
        self.assertEqual([c['id'] for c in self.terminal.chats], [parent['id'], first['id'], grandchild['id'], second['id']])
        self.assertEqual(self.terminal.agent_tree.prefix(first), '├─↳ ')
        self.assertEqual(self.terminal.agent_tree.prefix(grandchild), '│  └─↳ ')
        self.assertEqual(self.terminal.agent_tree.prefix(second), '└─↳ ')
        self.terminal.selected = 2
        self.terminal.refresh_browser()
        self.assertEqual(self.terminal.chats[self.terminal.selected]['id'], grandchild['id'])

    def test_sidebar_and_preview_identify_principal_and_immediate_parent(self):
        parent = self.terminal.chat
        first = self.child(parent, 'Executor A')
        grandchild = self.child(first, 'Executor neto')
        self.terminal.refresh_agents()
        screen = Screen((38, 180))
        self.terminal.draw(screen)
        self.assertIn('Coordenador principal', screen.text())
        self.assertIn('└─↳ Executor neto', screen.text())
        self.terminal.open_chats('agents')
        self.terminal.agent_preview = next(c for c in self.terminal.chats if c['id'] == grandchild['id'])
        screen = Screen((30, 140))
        self.terminal.draw(screen)
        self.assertIn('PRINCIPAL · Coordenador principal', screen.text())
        self.assertIn('Pai · Executor A', screen.text())
        self.terminal.session_contexts[parent['id']] = object()
        with patch.object(self.terminal, 'switch_chat') as switch:
            self.terminal.handle_browser('\n')
        self.assertEqual(switch.call_args.args[0]['id'], parent['id'])

    def test_nested_waiting_agent_click_routes_to_local_principal(self):
        parent = self.terminal.chat
        child = self.child(parent, 'Pai')
        grandchild = self.child(child, 'Neto')
        self.terminal.registry.set(grandchild['id'], 'waiting_input')
        self.terminal.live_chats[parent['id']] = parent
        self.terminal.session_states[parent['id']]['approval'] = ('Confirmar', object())
        self.terminal.refresh_agents()
        self.terminal.draw(Screen((40, 180)))
        left, top, _, _, _ = next(hit for hit in self.terminal.agent_panel_hits if hit[-1]['id'] == grandchild['id'])
        with patch('centaur_cli.terminal.curses.getmouse', return_value=(0, left + 2, top + 1, 0, curses.BUTTON1_PRESSED)), \
                patch.object(self.terminal, 'switch_chat') as switch:
            self.terminal.handle_mouse()
        self.assertEqual(switch.call_args.args[0]['id'], parent['id'])

    def test_cycles_missing_ancestors_and_deep_histories_do_not_recurse_forever(self):
        a = {'id': 'a'*32, 'parent_id': 'b'*32, 'title': 'A'}
        b = {'id': 'b'*32, 'parent_id': 'a'*32, 'title': 'B'}
        tree = AgentTree([a, b])
        self.assertEqual(len(tree.ordered()), 2)
        self.assertLessEqual(len(tree.lineage(a)), 2)
        missing = AgentTree([a]).principal(a)
        self.assertEqual(missing['id'], b['id'])
        self.assertIn('indisponível', missing['title'])
        records = [{'id': f'{i:032x}', 'title': str(i), **({'parent_id': f'{i-1:032x}'} if i else {})} for i in range(1100)]
        tree = AgentTree(records)
        self.assertEqual(len(tree.ordered()), 1100)
        self.assertEqual(tree.principal(records[-1])['id'], records[0]['id'])
        self.assertLess(len(tree.prefix(records[-1])), 18)

    def test_delegations_in_one_batch_show_sibling_arrows(self):
        self.terminal.chat['messages'] = [{'role': 'assistant', 'tool_calls': [
            {'id': str(i), 'function': {'name': 'delegate_task', 'arguments': '{"title":"Task"}'}} for i in range(2)]}]
        text = '\n'.join(self.terminal.lines(80))
        self.assertIn('├─↳ ○ Delegando Task', text)
        self.assertIn('└─↳ ○ Delegando Task', text)

    def test_narrow_tree_keeps_keyboard_navigation_and_no_overflow(self):
        child = self.child(self.terminal.chat, 'Executor ' * 20)
        self.terminal.open_chats('agents')
        self.terminal.handle_browser(curses.KEY_DOWN)
        self.assertEqual(self.terminal.chats[self.terminal.selected]['id'], child['id'])
        self.terminal.handle_browser('\n')
        screen = Screen((12, 40))
        self.terminal.draw(screen)
        self.assertIn('PRINCIPAL', screen.text())
        self.assertEqual(self.terminal.agent_preview['id'], child['id'])

    def test_preview_context_belongs_to_child_and_does_not_count_parent_draft(self):
        parent = self.terminal.chat
        child = self.child(parent, 'Executor')
        self.terminal.client = type('Client', (), {'context_windows': {'fixture': 1000}})()
        child['context_usage'] = {'used': 900, 'history_estimate': 1, 'model': 'fixture'}
        parent['context_usage'] = {'used': 100, 'history_estimate': 1, 'model': 'fixture'}
        self.terminal.draft = 'Rascunho do principal' * 100
        self.terminal.browser, self.terminal.agent_preview = True, child
        label, style = self.terminal.context_label(80)
        self.assertTrue(label.startswith('Agente '))
        self.assertIn('10% livre', label)
        self.assertEqual(style, 'warning')


if __name__ == '__main__':
    unittest.main()
