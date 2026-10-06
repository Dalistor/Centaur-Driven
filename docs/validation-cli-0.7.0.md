# Validação Centaur CLI 0.7.0

Data: 2026-10-06. Ambiente local: Linux, Python 3.11, terminal POSIX descartável.

## Verificações locais

- `python3 -m unittest discover -s tests -q`: 310 testes, aprovados; dois testes de desktop opt-in omitidos localmente.
- Curses real em PTY, nos modos colorido, monocromático e movimento reduzido: Shift+Enter Kitty/xterm, Ctrl+J, quebra visual, colagem multilinha sem envio, resize 80 × 24 → 40 × 12, envio único, `$compact` e continuação com resumo/histórico persistido.
- Compactação: lotes de ferramentas intactos, nenhuma ferramenta disponível à chamada de resumo, histórico completo preservado, cancelamento/falha de gravação sem aplicar memória, repetição incremental, fragmentação e exclusão de imagens/raciocínio privado.
- Codex: executável simulado verifica o handshake stdio e apenas `account/rateLimits/read`, remoção das chaves OpenRouter e encerramento do App Server.
- Claude: stream público simulado verifica resposta estruturada final, eventos de cota, tokens de cache e exclusão de eventos privados.
- Fast: flags e capacidades nativas, versão mínima Claude, endpoints OpenRouter Fast/priority, tier efetivo/fallback e preferência independente de effort. Modelo, effort e velocidade mantêm o chat no mesmo backend.
- Rodapé com contexto/cotas, ausência de saldos inventados e resize até 40 × 12.
- `git diff --check`, `compileall`, auditoria de design strict e lint DESIGN: sem erros; auditoria/lint sem avisos.
- Build wheel/sdist, `twine check --strict`, `scripts/check_dist.py`: 64 recursos conferidos, instalação limpa fora do checkout e comandos básicos aprovados.

## Limites da verificação

As contas autenticadas reais de Codex/Claude e requisições pagas OpenRouter não foram
usadas no ambiente local. Os testes de adaptador usam executáveis e respostas simulados;
o teste de interação usa curses e um terminal reais. Suporte de Fast e exposição de cotas
continuam dependendo do CLI, modelo, autenticação e conta. Claude fornece o último evento
observado, não um saldo monetário consultado em tempo real.

O workflow de publicação executa a suíte em Linux/Python 3.10 e 3.13 e macOS/Python 3.13,
além dos dois testes opt-in em um desktop Linux Xvfb descartável. A publicação PyPI é um
job separado e exige um Trusted Publisher configurado para este projeto e workflow.
