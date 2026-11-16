# Observação e recuperação

Saber que o sistema quebrou antes do usuário avisar, e conseguir voltar a um estado bom. Dimensione ao risco: comece pelo que detecta indisponibilidade e pelo que protege dados; o resto é refinamento.

## Logs

- Saída padrão do processo, coletada pelo supervisor (journald, driver do contêiner, plataforma); a aplicação não gerencia arquivos de log por conta própria. Onde houver arquivo, há rotação e limite de disco.
- Estruturados (JSON ou chave=valor) com instante, nível, mensagem e um identificador de requisição que atravessa os serviços.
- Registram o que permite reconstruir um problema: erro com contexto, decisão de autorização negada, operação administrativa, início e fim de tarefas longas.
- **Não** registram senhas, tokens, corpo de requisição com dados pessoais nem segredos de configuração. Retenção definida e compatível com as obrigações do projeto.

## Métricas e alertas

Para um serviço que atende requisições, quatro sinais bastam para começar: **latência**, **tráfego**, **erros** e **saturação** (CPU, memória, disco, conexões). Para filas e tarefas agendadas: tamanho/idade da fila e "rodou com sucesso por último em".

- O mínimo viável é uma **verificação externa de disponibilidade** batendo no health check, de fora da própria máquina, com aviso a uma pessoa. Uma máquina não consegue avisar que ela mesma caiu.
- Alerta existe para exigir ação. Cada um tem dono, canal e o que fazer (link para o runbook). Alerta que ninguém age vira ruído e é removido ou ajustado.
- Alerte por **sintoma que o usuário sente** (erro alto, lento, fora do ar) e por **esgotamento previsível** (disco enchendo, certificado vencendo, backup sem rodar); causas internas ficam em painel.
- Quando houver compromisso de disponibilidade, escreva-o como objetivo mensurável (por exemplo, proporção de requisições bem-sucedidas no mês) e alerte pela queima desse orçamento, não por picos isolados.

Se o projeto não tem ferramenta de monitoramento, não escolha uma por ele: apresente a lacuna, o mínimo necessário e as opções compatíveis com onde o sistema roda.

## Backup e restauração

- Liste **o que não pode ser recriado**: banco, uploads, configuração do servidor, segredos (estes pelo cofre, não por cópia solta).
- Defina com o usuário quanto de dado pode ser perdido (RPO) e em quanto tempo precisa voltar (RTO); a frequência do backup e o tipo de restauração saem daí, não de um padrão.
- Automático, com **cópia fora da máquina e da conta de origem**, cifrada, com retenção definida. A credencial que grava o backup não deve poder apagar os anteriores.
- **Backup só existe depois de restaurado.** Entregue o procedimento de restauração e uma rotina de ensaio periódico em ambiente separado; sem ensaio, registre como "backup não verificado".
- Falha ou ausência do backup gera alerta, como qualquer outro sintoma.

## Mudanças no banco

- Migrações versionadas, aplicadas pelo pipeline ou por comando documentado, nunca à mão sem registro.
- **Expandir, migrar, contrair**: primeiro a mudança compatível com a versão anterior do código, depois o código, por último a remoção. Isso é o que permite deploy sem interrupção e rollback do código.
- Rollback de código **não** desfaz dados. Operação destrutiva (remover coluna, apagar registros) exige backup recente conferido e é passo manual explícito, nunca automático.

## Rollback e incidentes

- O caminho de volta do deploy está escrito e foi ensaiado ao menos uma vez: qual comando, quanto leva e o que ele não cobre.
- Diante de um incidente, primeiro **restabeleça** (reverter para a última versão boa costuma ser mais rápido que corrigir adiante); investigue a causa depois, com os registros preservados.
- Depois, um registro curto e sem culpados: o que aconteceu, como foi detectado, o que restabeleceu e o que muda para não repetir ou para detectar antes.

## Runbook

Em `.centaur/ops/README.md`, curto e com comandos exatos. Quem nunca operou o sistema deve conseguir segui-lo:

- Onde roda, como acessar e quem tem acesso.
- Como publicar, verificar a versão em execução e reverter.
- Como ver logs e o estado do serviço; quais alertas existem e o que fazer em cada um.
- Como restaurar o backup, com a data do último ensaio.
- Rotinas e seus donos: atualizar dependências e sistema, renovar certificados, rotacionar credenciais, limpar releases antigas.
- Pendências conhecidas e contatos.

Acompanhar se a operação melhora cabe em quatro números, quando o time quiser medi-los: frequência de deploy, tempo da mudança até produção, proporção de deploys que causam falha e tempo para restabelecer. Eles são diagnóstico, não meta a ser perseguida por si.

## Entregar

Scripts de backup e restauração, configuração de rotação/coleta de logs e definições de verificação/alerta como propostas versionadas para o operador aplicar, mais o runbook. Diga o que ficou apenas escrito e o que foi de fato ensaiado; restauração e alerta não testados são pendências, não entregas.
