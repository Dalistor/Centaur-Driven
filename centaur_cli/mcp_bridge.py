"""Servidor MCP mínimo (stdio) que encaminha chamadas de ferramenta ao processo Centaur.

É iniciado pelo CLI nativo (Claude/Codex) como um arquivo avulso, fora do pacote:
use somente a biblioteca padrão e nenhum import relativo. As ferramentas continuam
sendo executadas, aprovadas e registradas pelo Centaur, do outro lado do socket.
"""

import itertools
import json
import os
import socket
import sys
import threading


def main(path):
    link = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    link.connect(path)
    output_lock, link_lock = threading.Lock(), threading.Lock()
    waiting, ready, state, numbers = {}, threading.Event(), {'tools': []}, itertools.count(1)

    def forward(value):
        with link_lock:
            link.sendall((json.dumps(value, ensure_ascii=False) + '\n').encode('utf-8'))

    def respond(identifier, result=None, error=None):
        message = {'jsonrpc': '2.0', 'id': identifier}
        message.update({'error': error} if error is not None else {'result': result})
        with output_lock:
            sys.stdout.write(json.dumps(message, ensure_ascii=False) + '\n')
            sys.stdout.flush()

    def receive():
        try:
            for line in link.makefile('r', encoding='utf-8'):
                message = json.loads(line)
                if message.get('op') == 'tools':
                    state['tools'] = message['tools']
                    ready.set()
                elif message.get('op') == 'result':
                    slot = waiting.pop(message.get('id'), None)
                    if slot:
                        slot['value'] = message
                        slot['done'].set()
        finally:
            os._exit(0)  # O Centaur encerrou a sessão: nada mais pode ser respondido.

    def call(identifier, params):
        number, slot = next(numbers), {'done': threading.Event()}
        waiting[number] = slot
        forward({'op': 'call', 'id': number, 'name': params.get('name'), 'arguments': params.get('arguments') or {}})
        slot['done'].wait()
        respond(identifier, {'content': [{'type': 'text', 'text': str(slot['value'].get('text', ''))}],
                             'isError': bool(slot['value'].get('error'))})

    threading.Thread(target=receive, daemon=True).start()
    forward({'op': 'hello'})
    for line in sys.stdin:
        try:
            request = json.loads(line)
        except ValueError:
            continue
        if not isinstance(request, dict):
            continue
        method, identifier, params = request.get('method'), request.get('id'), request.get('params') or {}
        if method == 'initialize':
            respond(identifier, {'protocolVersion': params.get('protocolVersion', '2024-11-05'),
                                 'capabilities': {'tools': {}}, 'serverInfo': {'name': 'centaur', 'version': '1'}})
        elif method == 'tools/list':
            ready.wait(10)
            respond(identifier, {'tools': state['tools']})
        elif method == 'tools/call':
            threading.Thread(target=call, args=(identifier, params), daemon=True).start()
        elif method == 'ping':
            respond(identifier, {})
        elif identifier is not None:
            respond(identifier, error={'code': -32601, 'message': 'Method not found'})


if __name__ == '__main__':
    main(sys.argv[1])
