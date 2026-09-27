---
version: alpha
colors:
  background: "#edf2f7"
  surface: "#ffffff"
  ink: "#172c45"
  muted: "#52677e"
  line: "#cbd7e4"
  primary: "#275bc6"
  rail: "#152d49"
  success: "#216647"
  warning: "#86531b"
  danger: "#a42c42"
typography:
  display:
    fontFamily: '"Trebuchet MS", "Segoe UI", sans-serif'
  body:
    fontFamily: '"Segoe UI", system-ui, sans-serif'
  code:
    fontFamily: '"Cascadia Code", "SFMono-Regular", Consolas, monospace'
rounded:
  panel: "10px"
  control: "6px"
spacing:
  base: "16px"
  desktopContent: "32px"
components:
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
---

## Overview

Volante é um instrumento de inspeção para quem dirige desenvolvimento feito por IA. O usuário parte de uma capacidade e encontra regra, código e prova. Registro de produto/ferramenta, em português brasileiro, offline e responsivo. O mapa de capacidades e a trilha de três estados são a assinatura: a realização do molde aparece ao lado de sua evidência, sem porcentagem fictícia de conclusão.

## Colors

Paleta de instrumento técnico: navegação azul naval, superfície azul-gelo e ação cobalto. Verde significa prova positiva, âmbar pendência/desatualização e vermelho falha. Texto acompanha toda cor semântica. Evitar neon, gradiente decorativo e grandes números sem ação correspondente.

## Typography

Trebuchet em títulos compactos, Segoe/system em leitura, Cascadia/Consolas para caminhos, hashes e código. Usar fontes locais; nenhuma dependência de rede nem troca tardia de fontes. Corpo de 15px, títulos de 22–38px, metadados de 12px. Português com acentos em toda a interface.

## Layout

Navegação lateral persistente, busca/filtro global, leitura principal e contexto lateral. Abaixo de 1100px o contexto vai para baixo; abaixo de 760px a navegação se torna horizontal com quebra. Scroll natural do documento, código/documentos com overflow próprio. Conteúdo longo deve quebrar sem esconder decisões ou caminhos. Listas extensas usam Mostrar mais, 18 itens por lote.

## Elevation & Depth

Superfícies planas com bordas suaves, sem sombras decorativas. Hierarquia vem do agrupamento por módulo e da trilha comportamento/código/prova. Painéis contextuais não são modais.

## Shapes

Painéis 10px, controles 6px. Conexões entre módulo e capacidade aparecem por alinhamento e linha lateral, não por grafo de forças. Badges compactos e rotulados.

## Components

Tokens CSS em `centaur-driven-graphify/scripts/volante-template.html` são a implementação canônica dos valores acima: background→--bg, surface→--surface, ink→--ink, muted→--muted, line→--line, primary→--brand, rail→--rail e estados→tokens homônimos. Fontes→--display/--sans/--mono; panel→--radius; base→--space. Alterar documento e tokens juntos. Cores derivadas claras nos badges não redefinem intenção.

Funções `chip`, `trace`, `source`, `evidence`, `empty` e `title` são as primitivas compartilhadas. Cada ação tem hover, focus-visible e semântica nativa. Scrollbar global visível com estados hover/active e fallback forced-colors. Filtros usam select nativo, aceitando popup do sistema. Details nativo abre código, evidências e histórico; links navegam pelo hash.

## Do's and Don'ts

- Mostrar data/revisão do snapshot e limitações das provas.
- Nunca confundir implementado, verificado e publicado.
- Evitar botões que simulem executar agente, salvar contrato ou publicar.
- Usar dados reais; demonstrações devem dizer que são fictícias.
- Exibir código como texto escapado. Não executar Markdown/HTML importado.
- Notas são locais, exportação é explícita e não concede novas permissões.
