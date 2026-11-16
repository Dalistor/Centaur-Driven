---
name: skill
description: Baixa e instala uma skill completa de um repositório GitHub em .centaur/skills/ do projeto, para uso pelo autocomplete @. Use quando o usuário pedir uma skill adicional ou fornecer sua origem para instalação.
metadata:
  version: 1.0.0
---

# skill

Instale skills adicionais somente em `.centaur/skills/<nome>/` na raiz do projeto aberto. Preserve `SKILL.md`, referências, scripts, assets e demais arquivos da pasta selecionada. Skills Centaur continuam no pacote; instalar `@run` não substitui `$run`.

## Fluxo

1. Identifique a origem e a pasta que contém `SKILL.md`. Aceite uma URL GitHub `https://github.com/dono/repo/tree/ref/pasta`, ou dono/repo com pasta e referência explícitas. Se faltar origem, peça o link ou sugira uma origem concreta para o usuário escolher; não instale uma skill apenas pela semelhança do nome. Para uma skill explicitamente solicitada do catálogo OpenAI, use `openai/skills`, pasta `skills/.curated/<nome>`.
2. Leia o helper `scripts/install.py` quando precisar entender seu contrato. Execute-o pelo caminho absoluto do pacote informado pelo CLI, passando `--project` com a raiz do projeto e a origem. O pedido de instalação autoriza baixar e instalar essa skill. No CLI, use `run_command`: a confirmação de comando existente mostra a operação concreta, sem acrescentar outra rodada de aprovação.
3. O helper valida a pasta e o frontmatter, preserva os arquivos de apoio e publica a instalação após staging. Ele recusa destinos existentes, links simbólicos, caminhos que escapem da origem e arquivos especiais. Não execute scripts baixados, hooks ou instruções de configuração durante a instalação. Dependências externas declaradas não são instaladas automaticamente.
4. Informe nome, origem, referência, hash do download e destino retornados. A skill aparece como `@nome` na lista local sem reiniciar o CLI. Use `read_skill` com `@nome/SKILL.md` para conferir a instalação, sem invocar seu fluxo como teste.

```bash
python3 /caminho/do/pacote/skills/skill/scripts/install.py \
  --project /caminho/do/projeto \
  --repo dono/repositorio --ref main --path skills/minha-skill

python3 /caminho/do/pacote/skills/skill/scripts/install.py \
  --project /caminho/do/projeto \
  --url https://github.com/dono/repositorio/tree/main/skills/minha-skill
```

`--name` escolhe o nome da pasta instalada; sem ele, usa o último componente de `--path`. Para refs que contêm `/`, use `--repo`, `--ref` e `--path` separados, ou `--url` com `--ref` explícito. Prefira um commit quando a origem precisar ser reproduzível.

O helper baixa repositórios públicos GitHub por HTTPS, sem usar chaves OpenRouter. Repositórios privados e outras origens exigem um fluxo autenticado específico; reporte a limitação, sem pedir tokens no chat. Falhas preservam a instalação existente. Atualização/substituição não faz parte deste helper: não apague uma skill já instalada para contornar a recusa.
