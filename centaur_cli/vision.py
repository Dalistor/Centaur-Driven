"""Transporte de quadros efêmeros aos CLIs nativos, sem JSON de imagem no prompt."""

import base64
import json


def split_images(messages, max_images=3):
    conversation, images = [], []
    for message in messages:
        content = message.get('content')
        if not isinstance(content, list):
            conversation.append(message)
            continue
        text = []
        for block in content:
            if block['type'] == 'text':
                text.append(block['text'])
            elif block['type'] == 'image_url':
                url = block['image_url']['url']
                if not url.startswith('data:image/png;base64,') or len(url) > 12_000_000:
                    raise ValueError('Quadro deve ser PNG local de até 9 MB.')
                data = base64.b64decode(url.split(',', 1)[1], validate=True)
                if not data.startswith(b'\x89PNG\r\n\x1a\n'):
                    raise ValueError('Quadro PNG inválido.')
                images.append(data)
                text.append(f'[Imagem anexada {len(images)}]')
            else:
                raise ValueError('Este backend não aceita o tipo de anexo recebido.')
        conversation.append(dict(message, content='\n'.join(text)))
    if len(images) > max_images:
        raise ValueError('Há imagens demais no contexto ativo; use $compact antes de /retry.' if max_images != 3 else 'Use até três quadros recentes por decisão.')
    return conversation, images


def native_input(backend, directory, arguments, prompt, images):
    if not images:
        return arguments, prompt
    if backend == 'codex':
        flags = []
        for index, data in enumerate(images):
            path = directory / f'frame-{index + 1}.png'
            path.write_bytes(data)
            path.chmod(0o600)
            flags += ['--image', str(path)]
        return [*arguments[:-1], *flags, arguments[-1]], prompt
    content = [{'type': 'text', 'text': prompt}]
    content += [{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png',
                                           'data': base64.b64encode(data).decode('ascii')}} for data in images]
    return [*arguments, '--input-format', 'stream-json'], json.dumps({
        'type': 'user', 'message': {'role': 'user', 'content': content}}, ensure_ascii=False) + '\n'
