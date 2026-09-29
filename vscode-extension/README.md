# Centaur Volante para VS Code

Abra um projeto com `.centaur/workspace.json`. A árvore **Centaur · Funcionalidades** no Explorer apresenta funcionalidades, regras, fontes (incluindo testes), evidências e passos dos casos de uso. RF/RNF, atores, exclusões, fluxos alternativos e modelo de dados aparecem a partir da especificação do contrato. Clique em uma fonte para abrir o arquivo na linha registrada. Contratos também são acessíveis diretamente. Avisos de leitura e evidências desatualizadas aparecem no contexto.

O contexto é relido quando contratos ou fontes vinculadas mudam no disco, sem gerar HTML ou indexar Graphify. Edições ainda não salvas não renovam evidências. Use **Centaur: Atualizar contexto** para recarregar manualmente. Python 3.10+ é necessário; configure `centaurVolante.python` se preciso. Pastas precisam ser confiáveis para executar o leitor Python.

**Centaur: Abrir testes**, **Inspecionar execução (depurador)** e **Revisar alterações** abrem as ferramentas nativas Testing, Run and Debug e Source Control. Testes exigem um adaptador instalado; valores e erros de execução usam as configurações e instrumentação existentes do projeto. A extensão não inventa traces nem marca uma evidência como aprovada ao abrir essas ferramentas.

## Autocomplete opcional

Execute **Centaur: Habilitar autocomplete IA nesta sessão** e escolha um modelo fornecido por uma integração do VS Code. O provedor precisa estar instalado, autenticado e autorizar o acesso; disponibilidade e cobrança dependem dele. A seleção envia trechos limitados do arquivo ativo (até 5.000 caracteres anteriores e 1.500 posteriores) e até 6.000 caracteres das regras relacionadas e sua base conceitual (sem conteúdo de evidências). Não há varredura de outros arquivos para montar o prompt.

Sugestões aparecem como texto inline, aceito pelas teclas padrão do editor. Há debounce, cancelamento, limite de resposta e descarte quando o documento muda. Arquivos ocultos e nomes comuns de credenciais são excluídos; isso não substitui a revisão de segredos colocados em código comum. **Centaur: Desabilitar autocomplete IA** interrompe a assistência. Reiniciar a janela também desabilita: não há envio automático antes de selecionar um modelo nesta sessão.

## Fluxos e agentes

**Centaur: Abrir fluxos e agentes** abre o painel secundário para edição de casos de uso e delegação delimitada. O painel gera `.centaur/volante.html` somente ao ser aberto ou salvo.

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

Perfis apenas indicam executáveis locais já instalados e autenticados pelo usuário. `{prompt}`, `{workspace}`, `{contract}` e `{rule}` são argumentos individuais, sem interpolação de shell. Na página **Agentes**, selecione de uma a quatro regras elegíveis e clique em **Iniciar agentes selecionados**. Cada execução cria uma branch e um worktree próprios em `.centaur/worktrees/`, visíveis no painel e no canal de saída **Centaur Volante**. O projeto não pode ter alterações rastreadas pendentes: os worktrees partem do último commit. Fechar a aba preserva agentes ativos; reabra para acompanhá-los. **Interromper** envia SIGINT; worktrees e branches são preservados para revisão. A integração de código, a publicação e a limpeza de worktrees continuam ações explícitas.

O painel secundário usa o HTML do gerador com CSP restritiva e não carrega recursos externos. O HTML avulso pode ser aberto no navegador para inspecionar ou baixar um fluxo em JSON; geração por IA e execução de processos exigem a extensão em uma pasta confiável do VS Code.

## Verificação e pacote

`npm test` executa testes de contratos, navegação segura, autocomplete e host simulado. `npm run package` gera `.centaur/build/centaur-volante.vsix` na raiz do repositório. Instale pelo comando “Extensions: Install from VSIX”.
