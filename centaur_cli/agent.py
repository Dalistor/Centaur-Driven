"""Execução de um turno com ferramentas e checkpoints de histórico."""

import json
from pathlib import Path

from .tools import TOOLS
from . import skill_catalog


def project_prompt(root):
    prompt = ('Você é Centaur, um assistente de programação no terminal. Responda em português. '
              'Investigue antes de alterar e valide o trabalho. Use ferramentas para consultar '
              'arquivos; não invente resultados. Alterações e comandos exigem aprovação. '
              f'A pasta aberta é {root}. Skills incluídas no CLI: {", ".join(skill_catalog.names())}. '
              'Use read_skill com path <nome>/SKILL.md e start_line 1 para ler uma skill; '
              'continue a leitura se houver mais linhas. Caminhos relativos entre skills são '
              'resolvidos no catálogo, por exemplo graphify/references/lifecycle.md. '
              'As skills chamam a subskill interna de memória lendo _internal/memory/SKILL.md '
              'e seu contrato via read_skill; ela não é um comando do catálogo. '
              'Comece com busca e leitura direta. Para decisões históricas pertinentes, use memory; '
              'para relações amplas difíceis de localizar, use graphify sob demanda. '
              'Quando motivo e impacto forem necessários, recupere o histórico, investigue as relações '
              'e confirme no código, specs e evidências atuais. Não atualize o grafo após conversas '
              'ou registros de memória; consultar não autoriza indexar nem mudar o backend. '
              'Pedidos como $spec, $run e $check invocam as skills correspondentes. '
              '/status mostra uma árvore local das specs; /status --ai analisa evidências '
              'e recomenda conclusão ou execução, sem alterar registros nem iniciar tasks. '
              'Quando delegate_task estiver disponível, $run delega cada task elegível '
              'a um subagente com contexto próprio. Descreva contrato, fontes, arquivos de posse, '
              'dependências, risco, modo e aceite no campo task. O Auto Router seleciona '
              'modelos apropriados somente no backend OpenRouter; escolha cost_tier conforme complexidade e limite do CLI. '
              'Com Codex/Claude, delegate_task herda backend e modelo da sessão, sem model ou cost_tier. '
              'Verifique o trabalho retornado antes de consolidar a spec. '
              'Leia as skills relevantes antes de executar o fluxo. '
              'A dependência clean-code instalada localmente ou no diretório de skills do usuário '
              'é acessível por read_skill com path clean-code/SKILL.md e suas referências. '
              f'Skills adicionais do projeto em .centaur/skills: {", ".join(skill_catalog.additional_names(root)) or "nenhuma"}. '
              'Menções $nome invocam a skill Centaur: leia nome/SKILL.md via read_skill. '
              'Menções @nome invocam a skill adicional do projeto: leia @nome/SKILL.md '
              'via read_skill; suas referências usam @nome/references/arquivo. '
              'Skills adicionais ficam em .centaur/skills/<nome>/SKILL.md; preserve os namespaces '
              'mesmo quando uma skill adicional tem o mesmo nome de uma skill Centaur. '
              f'Scripts incluídos ficam em {skill_catalog.SKILL_ROOT}; use esse caminho absoluto '
              'para executá-los com run_command, após aprovação. Histórico fica em .centaur/chats.\n')
    instructions = Path(root) / 'AGENTS.md'
    if instructions.is_file():
        prompt += instructions.read_text(encoding='utf-8')[:24000]
    return prompt


def run_turn(chat, client, tools, store, emit, instructions=''):
    messages = chat['messages']
    # Completa chamadas interrompidas sem repetir operações com efeitos colaterais.
    answered = {message.get('tool_call_id') for message in messages if message['role'] == 'tool'}
    recovered = []
    for message in messages:
        recovered.append(message)
        for call in message.get('tool_calls', []):
            if call['id'] not in answered:
                recovered.append({'role': 'tool', 'tool_call_id': call['id'],
                                 'content': 'Execução interrompida; confira o estado antes de tentar novamente.'})
    messages[:] = recovered
    for _ in range(20):
        response = client.complete(chat['model'],
                                   [{'role': 'system', 'content': project_prompt(tools.root) + instructions}] + messages,
                                   getattr(tools, 'definitions', TOOLS))
        selected_model = getattr(response, 'model', None)
        if selected_model:
            chat.setdefault('models_used', []).append(selected_model)
        messages.append(response)
        store.save(chat)
        emit()
        calls = response.get('tool_calls', [])
        if not calls:
            return
        for call in calls:
            try:
                arguments = json.loads(call['function']['arguments'])
                result = tools.execute(call['function']['name'], arguments)
            except (ValueError, KeyError, TypeError) as error:
                result = f'Chamada inválida: {error}'
            messages.append({'role': 'tool', 'tool_call_id': call['id'], 'content': result})
            store.save(chat)
            emit()
    raise RuntimeError('Limite de 20 etapas atingido; envie outra mensagem para continuar.')
