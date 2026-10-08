# Colagem de texto e identificação de arquivos — 0.10.3

Data: 2026-10-08. Correção sobre a 0.10.2.

## Reprodução

Na identificação automática de anexos, uma frase de 420 caracteres era consultada
como nome de arquivo. `Path.is_file()` levantava `OSError` com errno 36 no ambiente
Linux de teste, encerrando a colagem protegida e o terminal. Pelo Ctrl+V, a mesma
falha era capturada pelo worker, mas o texto não entrava no campo. Uma string de
180 caracteres acentuados também reproduzia o limite em bytes do nome de arquivo.

## Correção

`clipboard.pasted_paths` só confirma anexos se a lista inteira for de arquivos
existentes. Erros de consulta ao sistema de arquivos, URI inválida e expansão de
home indisponível retornam ao texto literal. Nenhuma preparação parcial é iniciada.
A preparação e a validação dos arquivos confirmados mantêm seu fluxo existente.

## Validação

Os testes existentes foram ampliados, sem criar novos métodos de teste:

- Colagem protegida e Ctrl+V preservam texto longo, Unicode, multilinha, aspas
  incompletas, URI inválida e home inexistente, inserindo no cursor sem enviar.
- Lista de URIs com um arquivo válido e outro inválido não prepara anexos parciais.
- Arquivos reais com espaços e listas locais continuam anexando normalmente.
- Curses/PTY reais recebem uma colagem longa com acentos e quebra de linha; o CLI
  permanece aberto, não envia ao modelo nem prepara anexos, e continua editável.
  O fluxo existente roda em cor, NO_COLOR, movimento reduzido e terminal legado.

`python3 -m unittest discover -s tests -v`: 536 testes, 530 aprovados e 6 ignorados
por dependerem de desktop/clipboard específicos; sem falhas. As amostras do teste
são sintéticas e não contêm o conteúdo da mensagem privada que originou o relato.

Build wheel/sdist, `twine check --strict` e `scripts/check_dist.py` aprovados para
0.10.3: 73 recursos presentes e instalação limpa fora do diretório fonte.
