#!/usr/bin/env python3
"""Avaliação reproduzível do harness: roda tarefas pequenas em cópias descartáveis e mede o resultado.

Cada pasta em evals/ tem task.json ({"prompt", "check", "timeout"}) e files/ com o projeto inicial.
O agente trabalha numa cópia temporária, no modo auto com sandbox (sem rede, sem gravar fora da
cópia) e com toda confirmação recusada; depois o comando `check` decide se a tarefa passou.

    python scripts/eval_agent.py --model anthropic/claude-sonnet-4.5
    python scripts/eval_agent.py --backend claude --task fix-failing-test --repeat 3 --json out.jsonl

Compare duas versões do harness (ou dois valores de CENTAUR_CONTEXT_BUDGET, READ_DEFAULT etc.)
pelas colunas de sucesso, chamadas, tokens e custo. Cada execução consome créditos do backend.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from centaur_cli import sandbox  # noqa: E402
from centaur_cli.agent import run_turn  # noqa: E402
from centaur_cli.history import ChatStore  # noqa: E402
from centaur_cli.tools import ProjectTools, stop_background  # noqa: E402


def load_task(directory):
    directory = Path(directory)
    task = json.loads((directory / 'task.json').read_text(encoding='utf-8'))
    if (not isinstance(task.get('prompt'), str) or not task['prompt'].strip()
            or not isinstance(task.get('check'), str) or not task['check'].strip()):
        raise ValueError(f'{directory.name}: task.json precisa de "prompt" e "check".')
    return {'name': directory.name, 'prompt': task['prompt'], 'check': task['check'],
            'timeout': int(task.get('timeout', 120)), 'files': directory / 'files'}


def run_task(task, client, model, *, backend='openrouter', effort='default', isolated=True):
    """Executa uma tarefa numa cópia temporária; devolve as métricas, nunca levanta por falha do agente."""
    with tempfile.TemporaryDirectory(prefix='centaur-eval-') as temporary:
        root = Path(temporary, 'project').resolve()
        shutil.copytree(task['files'], root) if task['files'].is_dir() else root.mkdir()
        environment = {'CENTAUR_SANDBOX': '1'} if isolated else {}
        previous = {key: os.environ.get(key) for key in environment}
        os.environ.update(environment)
        store = ChatStore(root)
        chat = store.new(model, backend=backend)
        chat.update(effort=effort, messages=[{'role': 'user', 'content': task['prompt']}])
        # Isolado: o que o sandbox não cobre é recusado. Sem isolamento, o modelo roda comandos nesta máquina.
        tools = ProjectTools(root, lambda _: False, protected_keys=getattr(client, 'secrets', ()),
                             approval_mode='auto' if isolated else 'never')
        calls, original = [], tools.execute
        def execute(name, arguments):
            calls.append(name)
            return original(name, arguments)
        tools.execute = execute
        started, error = time.monotonic(), None
        try:
            run_turn(chat, client, tools, store, lambda: None)
        except Exception as failure:  # Uma avaliação registra a falha e segue para a próxima tarefa.
            error = f'{type(failure).__name__}: {failure}'[:300]
        finally:
            stop_background(root)
            for key, value in previous.items():
                os.environ.pop(key, None) if value is None else os.environ.__setitem__(key, value)
        elapsed = time.monotonic() - started
        try:
            check = subprocess.run(task['check'], shell=True, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, timeout=task['timeout'])
            passed, detail = check.returncode == 0, check.stdout.decode('utf-8', errors='replace')[-400:]
        except subprocess.TimeoutExpired:
            passed, detail = False, 'check excedeu o tempo'
        spend = chat.get('spend') if isinstance(chat.get('spend'), dict) else {}
        return {'task': task['name'], 'passed': passed, 'error': error,
                'requests': sum(message.get('role') == 'assistant' for message in chat['messages']),
                'tool_calls': len(calls), 'input': spend.get('input', 0), 'cached': spend.get('cached', 0),
                'output': spend.get('output', 0), 'cost': spend.get('cost', 0), 'seconds': round(elapsed, 1),
                'compacted': bool(chat.get('compaction')), 'check': '' if passed else detail}


def table(results):
    lines = [f'{"tarefa":28} {"ok":>3} {"cham.":>5} {"ferr.":>5} {"entrada":>9} {"saída":>7} {"US$":>7} {"s":>6}']
    for row in results:
        lines.append(f'{row["task"][:28]:28} {"✓" if row["passed"] else "✗":>3} {row["requests"]:>5} {row["tool_calls"]:>5} '
                     f'{row["input"]:>9} {row["output"]:>7} {row["cost"]:>7.3f} {row["seconds"]:>6}')
    passed = sum(row['passed'] for row in results)
    lines.append(f'{passed}/{len(results)} passaram · {sum(row["requests"] for row in results)} chamadas · '
                 f'entrada {sum(row["input"] for row in results)} · saída {sum(row["output"] for row in results)} · '
                 f'US$ {sum(row["cost"] for row in results):.3f}')
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Avalia o harness em tarefas reproduzíveis (consome créditos).')
    parser.add_argument('--backend', default='openrouter', choices=('openrouter', 'codex', 'claude'))
    parser.add_argument('--model', default='', help='Modelo principal; vazio usa o padrão do backend')
    parser.add_argument('--effort', default='default')
    parser.add_argument('--task', action='append', help='Nome de uma pasta em evals/; repita para várias (padrão: todas)')
    parser.add_argument('--tasks-dir', default=str(ROOT / 'evals'))
    parser.add_argument('--repeat', type=int, default=1, help='Execuções por tarefa; modelos variam entre execuções')
    parser.add_argument('--json', help='Acrescentar uma linha JSON por execução a este arquivo')
    parser.add_argument('--unsafe-no-sandbox', action='store_true',
                        help='Rodar sem sandbox (modo never): o modelo executa comandos nesta máquina')
    options = parser.parse_args(argv)
    directories = sorted(path for path in Path(options.tasks_dir).iterdir() if (path / 'task.json').is_file())
    if options.task:
        directories = [path for path in directories if path.name in options.task]
    if not directories:
        parser.error('Nenhuma tarefa encontrada.')
    if not options.unsafe_no_sandbox:
        os.environ['CENTAUR_SANDBOX'] = '1'
        if sandbox.wrap(Path(options.tasks_dir), 'true') is None:
            parser.error('Sandbox indisponível (requer Linux com bubblewrap). Instale o bwrap ou, numa máquina '
                         'descartável, use --unsafe-no-sandbox.')
    from centaur_cli.backends import create_client
    client = create_client(options.backend, options.model, allow_setup=False, include_credits=False)
    if callable(getattr(client, 'model_catalog', None)):
        try:
            client.model_catalog()  # Janelas de contexto e níveis de effort.
        except RuntimeError:
            pass
    results = []
    for directory in directories:
        for _ in range(max(1, options.repeat)):
            row = run_task(load_task(directory), client, options.model, backend=options.backend, effort=options.effort,
                           isolated=not options.unsafe_no_sandbox)
            results.append(row)
            print(f'{"✓" if row["passed"] else "✗"} {row["task"]} · {row["requests"]} chamadas · {row["seconds"]}s'
                  + (f' · {row["error"]}' if row['error'] else ''), flush=True)
            if options.json:
                with open(options.json, 'a', encoding='utf-8') as output:
                    output.write(json.dumps({**row, 'model': options.model, 'backend': options.backend}, ensure_ascii=False) + '\n')
    print(table(results))
    return 0 if all(row['passed'] for row in results) else 1


if __name__ == '__main__':
    sys.exit(main())
