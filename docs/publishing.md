# Publicação do Centaur CLI

O pacote público se chama `centaur-cli` e instala o comando `centaur`. Requer Python 3.10+
e Linux/macOS com curses. A versão tem uma única fonte: `centaur_cli.__version__`.

## Configuração inicial no PyPI

A publicação usa Trusted Publishing (OIDC), sem guardar um token no repositório.
Antes da primeira publicação, o proprietário deve cadastrar um **pending publisher** em
[PyPI → Publishing](https://pypi.org/manage/account/publishing/):

| Campo | Valor |
| --- | --- |
| PyPI project name | `centaur-cli` |
| GitHub owner | `Dalistor` |
| GitHub repository | `Centaur-Driven` |
| Workflow filename | `publish-cli.yml` |
| Environment name | `pypi` |

Se o projeto já existir sob sua conta, configure os mesmos campos nos publishers do projeto.
Um pending publisher não reserva o nome. O projeto é criado na primeira publicação aceita.
Não envie credenciais por chat nem adicione tokens ao código.

Depois de cadastrar, abra a execução de
[Publish Centaur CLI](https://github.com/Dalistor/Centaur-Driven/actions/workflows/publish-cli.yml)
e selecione **Re-run failed jobs** se o job `pypi` falhou por ausência do publisher.
Os jobs de build e release continuam úteis mesmo quando a autorização do PyPI falta.
Verifique o sucesso do job e a página [centaur-cli no PyPI](https://pypi.org/project/centaur-cli/)
antes de anunciar `pip install centaur-cli`.

Referências: [criar um projeto via OIDC](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
e [usar um publisher](https://docs.pypi.org/trusted-publishers/using-a-publisher/).

## Gerar uma nova versão

1. Altere `__version__` em `centaur_cli/__init__.py` e registre a entrega em `CHANGELOG.md`.
2. Atualize exemplos de instalação com a nova versão.
3. Execute os testes e a validação local abaixo.
4. Abra um pull request para `main`. Depois dos testes, faça o merge.

O workflow testa Python 3.10 e 3.13 no Linux e 3.13 no macOS; gera wheel e sdist;
valida o README e todos os recursos; instala o wheel em um ambiente limpo; publica uma
release com tag `cli-v<versão>`, pacotes e SHA256SUMS; depois publica os mesmos pacotes no PyPI.
A tag de uma versão publicada não pode apontar para outro commit. Para alterar um pacote
já publicado, gere uma nova versão. Não sobrescreva releases ou arquivos do PyPI.

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

Depois da publicação no PyPI:

```bash
pipx install centaur-cli
pipx upgrade centaur-cli
centaur --version
```

Também é possível instalar o wheel diretamente da release pública com pipx ou pip.
Codex e Claude Code continuam sendo instalados e autenticados separadamente.
