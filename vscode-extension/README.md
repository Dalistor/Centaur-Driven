# Centaur Volante para VS Code

Abra a raiz Git do projeto que contém `.centaur/workspace.json` e execute **Centaur: Abrir Volante** na paleta de comandos. A extensão gera o snapshot no projeto e mostra o painel em uma aba do editor. Reabrir ou usar o comando atualiza o snapshot. É necessário Python 3.10+; altere `centaurVolante.python` se o executável tiver outro nome.

## Instalação local e atualização

Baixe `centaur-volante.vsix` nos arquivos anexados à [release do projeto](https://github.com/Dalistor/Centaur-Driven/releases). Instale pelo terminal na pasta onde salvou o arquivo:

```bash
code --install-extension ./centaur-volante.vsix
```

Para atualizar, baixe o VSIX da release mais recente e execute o mesmo comando com `--force`:

```bash
code --install-extension ./centaur-volante.vsix --force
```

Também é possível instalar pelo comando **Extensions: Install from VSIX...** na paleta do VS Code. Se o comando `code` não estiver disponível no terminal, instale o comando de shell do VS Code ou use a paleta. Recarregue a janela após instalar ou atualizar.

Para gerar o VSIX a partir do código fonte, execute na raiz do repositório:

```bash
cd vscode-extension
npm ci
npm test
npm run package
code --install-extension ./centaur-volante.vsix
```

Isso requer Node.js 22. O workflow `release-vsix.yml` executa esses mesmos testes e gera o VSIX quando uma tag `v<versão>` correspondente a `vscode-extension/package.json` é enviada. Depois dos testes e do empacotamento, ele cria a release e anexa `centaur-volante.vsix`.

Em **Casos de uso**, selecione um contrato, edite passos e conexões e clique em **Salvar JSON no projeto**. Os arquivos ficam em `.centaur/use-cases/<contrato>.json`. **Gerar fluxo com IA** usa um modelo de linguagem disponível no VS Code escolhido na hora; a proposta é revisada na tela antes de ser salva. A extensão não marca contrato como aprovado ou evidência como verificada.

Para iniciar agentes, adicione perfis em `centaurVolante.agentProfiles` no `settings.json`:

```json
{
  "centaurVolante.agentProfiles": [
    {"id":"codex","label":"Codex CLI","command":"codex","args":["exec","{prompt}"]},
    {"id":"outro","label":"Outro CLI","command":"meu-agente","args":["--task","{prompt}"]}
  ]
}
```

Perfis apenas indicam executáveis locais já instalados e autenticados pelo usuário. `{prompt}`, `{workspace}`, `{contract}` e `{rule}` são argumentos individuais, sem interpolação de shell. Na página **Agentes**, selecione de uma a quatro regras elegíveis e clique em **Iniciar agentes selecionados**. Cada execução cria uma branch e um worktree próprios, visíveis no painel e no canal de saída **Centaur Volante**. O projeto não pode ter alterações rastreadas pendentes: os worktrees partem do último commit. **Interromper** envia SIGINT; worktrees e branches são preservados para revisão. A integração de código, a publicação e a limpeza de worktrees continuam ações explícitas.

A aba usa o HTML do gerador com CSP restritiva e não carrega recursos externos. O HTML avulso pode ser aberto no navegador para inspecionar ou baixar um fluxo em JSON; geração por IA e execução de processos exigem a extensão em uma pasta confiável do VS Code.
