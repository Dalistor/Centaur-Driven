---
version: alpha
colors:
  background: "#f6f7f9"
  surface: "#ffffff"
  ink: "#202a35"
  muted: "#5d6b79"
  line: "#dce2e7"
  primary: "#246555"
  rail: "#eef1f3"
  success: "#246555"
  warning: "#8a5315"
  danger: "#a53646"
typography:
  display:
    fontFamily: '"Avenir Next", "Segoe UI", sans-serif'
  body:
    fontFamily: '"Segoe UI", system-ui, sans-serif'
  code:
    fontFamily: '"Cascadia Code", "SFMono-Regular", Consolas, monospace'
rounded:
  panel: "12px"
  control: "7px"
spacing:
  base: "16px"
  desktopContent: "36px"
components:
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
---

## Overview

Volante é um instrumento de inspeção para quem dirige desenvolvimento feito por IA. O usuário parte de uma capacidade e encontra regra, código e prova. Registro de produto/ferramenta, em português brasileiro, offline e responsivo. O mapa de capacidades e a trilha de três estados são a assinatura: a realização do molde aparece ao lado de sua evidência, sem porcentagem fictícia de conclusão.

## Colors

Paleta de instrumento de leitura: navegação cinza-neblina, superfície branca e ação verde-petróleo. A cor fica concentrada em evidências e decisões; a área de decisão usa âmbar claro, sem competir com o mapa. Verde significa prova positiva, âmbar pendência/desatualização e vermelho falha. Tema claro explícito: meta e CSS usam color-scheme: only light; body declara fundo, texto e fonte, sem herdar o tema do hospedeiro. Alto contraste do sistema continua respeitado. Texto acompanha toda cor semântica. Evitar neon, gradiente decorativo e grandes números sem ação correspondente.

## Typography

Avenir Next/Segoe em títulos compactos, Segoe/system em leitura, Cascadia/Consolas para caminhos, hashes e código. Usar fontes locais; nenhuma dependência de rede nem troca tardia de fontes. Corpo de 14px, títulos de 18–34px e metadados de 10–12px. Títulos com peso 650 e tracking compacto; monoespaçada restrita a IDs e fontes. Português com acentos em toda a interface.

## Layout

Navegação lateral persistente, busca/filtro global, leitura principal e contexto lateral. Abaixo de 1000px o contexto vai para baixo; abaixo de 700px a navegação se torna horizontal com quebra. Na visão geral, a assinatura é um mapa pontilhado com capacidades agrupadas por módulo e segmentos que representam regras reais. Módulos sem contratos no recorte não ocupam cartões vazios. O resumo tem links para contratos, código e evidências; decisões abertas recebem destaque lateral. O fundo pontilhado delimita o mapa, sem sugerir dependências inexistentes. Scroll natural do documento, código/documentos com overflow próprio. Conteúdo longo deve quebrar sem esconder decisões ou caminhos. Listas extensas usam Mostrar mais, 18 itens por lote. Contratos mostram uma linha por capacidade com intenção e progresso; Código começa por arquivos e só expande trechos do arquivo selecionado. Casos de uso apresentam grafo com passos e conexões editáveis em painel lateral, mantendo o canvas com rolagem própria em telas estreitas.

## Elevation & Depth

Superfícies planas com bordas suaves. Somente os nós de capacidade têm sombra de 2px, distinguindo os elementos clicáveis do plano do mapa. Hierarquia vem do agrupamento por módulo e da trilha comportamento/código/prova. Painéis contextuais não são modais.

## Shapes

Painéis 12px, controles 7px. Ícones SVG de traço 1.6px compartilham geometria de 24×24, sem glifos dependentes da fonte. Conexões entre módulo e capacidade aparecem por alinhamento e linha lateral, não por grafo de forças. Badges compactos e rotulados.

## Components

Modelo B: os tokens CSS são canônicos; este documento espelha os valores aceitos. Tokens CSS em `centaur-driven-graphify/scripts/volante-template.html` são a implementação canônica dos valores acima: background→--bg, surface→--surface, ink→--ink, muted→--muted, line→--line, primary→--brand, rail→--rail e estados→tokens homônimos. Fontes→--display/--sans/--mono; panel→--radius; control→--control-radius; base→--space; desktopContent→padding de .content/.topbar. Tokens derivados --soft, --brand-soft, --warn-soft e --bad-soft pertencem ao mesmo :root e alimentam todos os estados, sem redefinições por tela. Alterar documento e tokens juntos. Cores derivadas claras nos badges não redefinem intenção.

Funções `icon`, `chip`, `trace`, `source`, `evidence`, `empty`, `graph` e `title` são as primitivas compartilhadas. Cada ação tem hover, focus-visible e semântica nativa. Scrollbar global visível com estados hover/active e fallback forced-colors. Filtros usam select nativo, aceitando popup do sistema. Details nativo abre código, evidências e histórico; links navegam pelo hash.

## Do's and Don'ts

- Mostrar data/revisão do snapshot e limitações das provas.
- Nunca confundir implementado, verificado e publicado.
- Ações de salvar fluxo ou iniciar agente só aparecem habilitadas quando seu hospedeiro realmente oferece essa capacidade. Nenhuma delas aprova contrato ou integra código.
- Usar dados reais; demonstrações devem dizer que são fictícias.
- Exibir código como texto escapado. Não executar Markdown/HTML importado.
- Notas são locais, exportação é explícita e não concede novas permissões.

## Revisão visual

Redesenho solicitado em 2026-09-27 após avaliação do usuário. Sai a navegação naval e o agrupamento de caixas equivalentes; entram navegação neutra, mapa com nós de capacidade e decisões em destaque. Preservados estados, limites do snapshot, filtros, notas locais e fontes escapadas. Não há novos estados de negócio.

A extensão hospeda o mesmo template no VS Code com política de recursos restrita. A versão avulsa baixa JSON; a versão hospedada salva em arquivo de projeto após validação de versão, e mostra execuções de agentes configurados. O fluxo em nós usa as mesmas cores e tipografia do mapa de capacidades; arestas exprimem apenas conexões registradas no JSON.
