"""Runner de avaliações: as tarefas começam falhando e as métricas refletem a execução."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

from centaur_cli.openrouter import ModelReply

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('eval_agent', ROOT / 'scripts' / 'eval_agent.py')
eval_agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eval_agent)


def client(*replies):
    fake = Mock(backend='openrouter', secrets=(), supports_cancellation=False, supports_streaming=False,
                supports_progress=False, context_windows={})
    fake.complete.side_effect = list(replies)
    return fake


class EvalTests(unittest.TestCase):
    def tasks(self):
        return [eval_agent.load_task(path) for path in sorted((ROOT / 'evals').iterdir()) if (path / 'task.json').is_file()]

    def test_every_bundled_task_fails_until_the_agent_does_the_work(self):
        tasks = self.tasks()
        self.assertGreaterEqual(len(tasks), 3)
        for task in tasks:
            row = eval_agent.run_task(task, client({'role': 'assistant', 'content': 'Nada a fazer.'}), 'main', isolated=False)
            self.assertFalse(row['passed'], task['name'])
            self.assertEqual((row['requests'], row['tool_calls'], row['error']), (1, 0, None))

    def test_a_correct_fix_passes_and_usage_is_reported(self):
        task = next(task for task in self.tasks() if task['name'] == 'fix-failing-test')
        edit = {'id': 'e', 'type': 'function', 'function': {'name': 'edit_file', 'arguments': json.dumps({
            'path': 'intervals.py', 'old_string': 'start < merged[-1][1]:\n            merged[-1][1] = end',
            'new_string': 'start <= merged[-1][1]:\n            merged[-1][1] = max(merged[-1][1], end)'})}}
        usage = {'prompt_tokens': 100, 'completion_tokens': 10, 'cost': 0.01}
        row = eval_agent.run_task(task, client(
            ModelReply({'role': 'assistant', 'content': None, 'tool_calls': [edit]}, usage=usage),
            ModelReply({'role': 'assistant', 'content': 'Corrigido.'}, usage=usage)), 'main', isolated=False)
        self.assertTrue(row['passed'], row['check'])
        self.assertEqual((row['requests'], row['tool_calls'], row['input'], row['output'], row['cost']), (2, 1, 200, 20, 0.02))
        self.assertIn('1/1 passaram', eval_agent.table([row]))

    def test_an_agent_failure_is_recorded_instead_of_stopping_the_run(self):
        failing = client()
        failing.complete.side_effect = RuntimeError('OpenRouter HTTP 500')
        row = eval_agent.run_task(self.tasks()[0], failing, 'main', isolated=False)
        self.assertFalse(row['passed'])
        self.assertIn('HTTP 500', row['error'])


if __name__ == '__main__':
    unittest.main()
