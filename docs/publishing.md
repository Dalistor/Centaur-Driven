# Publicação do Centaur CLI

O pacote público se chama `centaur-cli` e instala o comando `centaur`. Requer Python 3.10+
e Linux/macOS com curses. A versão tem uma única fonte: `centaur_cli.__version__`.

## Canal de distribuição

A distribuição é a release do GitHub: cada versão publica wheel, código-fonte e `SHA256SUMS`
sob a tag `cli-v<versão>`. O `install.sh` da raiz baixa o wheel da release mais recente,
confere o checksum e instala com uv ou pipx. O pacote não é publicado no PyPI.

## Gerar uma nova versão

1. Altere `__version__` em `centaur_cli/__init__.py` e registre a entrega em `CHANGELOG.md`.
2. Atualize exemplos de instalação com a nova versão.
3. Execute os testes e a validação local abaixo.
4. Abra um pull request para `main`. Depois dos testes, faça o merge.

O workflow testa Python 3.10 e 3.13 no Linux e 3.13 no macOS; gera wheel e sdist;
valida o README e todos os recursos; instala o wheel em um ambiente limpo; publica uma
release com tag `cli-v<versão>`, pacotes e SHA256SUMS.
A tag de uma versão publicada não pode apontar para outro commit. Para alterar um pacote
já publicado, gere uma nova versão. Não sobrescreva releases.

Os testes de deploy estático rodam apenas no Linux, por exigirem utilitários GNU e flock.

Pull requests executam testes e build, sem publicar. O push da versão na `main`, incluindo
um merge, inicia a publicação automaticamente. O workflow também aceita `workflow_dispatch`.

## Validação local

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install build==1.3.0 twine==6.2.0 setuptools==80.9.0 wheel==0.45.1
python -m unittest discover -s tests -v
python -m build --no-isolation
python -m twine check --strict dist/*
python scripts/check_dist.py dist
```

Use uma pasta `dist` limpa, com exatamente um wheel e um sdist da versão atual.
`check_dist.py` compara cada módulo e recurso com os arquivos empacotados, verifica os
metadados e testa `centaur --version`, `--help`, `status` e o catálogo de skills instalado
fora da árvore de código. Os testes não chamam modelos pagos.

## Instalar e atualizar

Depois da release:

```bash
curl -fsSL https://raw.githubusercontent.com/Dalistor/Centaur-Driven/main/install.sh | sh
centaur --version
```

Também é possível instalar o wheel diretamente da release pública com pipx ou pip.
Codex e Claude Code continuam sendo instalados e autenticados separadamente.
