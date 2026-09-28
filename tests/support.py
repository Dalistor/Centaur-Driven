import hashlib
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'centaur-driven-graphify/scripts'
sys.path.insert(0, str(SCRIPTS))
from volante import load_project


def write(root, relative, content):
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(content, ensure_ascii=False, indent=2) if not isinstance(content, str) else content, encoding='utf-8')


def fixture(root):
    write(root, '.centaur/workspace.json', {'name': 'Clínica Horizonte · demonstração fictícia', 'version': 1, 'lifecycle': 1, 'scopes': {'master': {'code': '.', 'specs': '.centaur/specs', 'owner': 'Diego'}, 'agenda': {'code': 'src', 'specs': '.centaur/modules/agenda/specs', 'owner': 'Produto'}, 'notificacoes': {'code': 'src', 'specs': '.centaur/modules/notificacoes/specs', 'owner': 'Integrações'}}})
    c = {'schema': 1, 'id': 'reservas', 'version': 1, 'title': 'Reservar e cancelar consultas', 'scope': 'agenda', 'status': 'approved', 'intent': 'Pacientes encontram horários e reservam com segurança; profissionais mantêm o controle da agenda.', 'approval': {'by': 'Exemplo fictício', 'at': '2026-09-27T03:00:00Z', 'reference': 'Aprovação ilustrativa, somente para demonstrar o visor.'}, 'extends': [], 'boundaries': ['Preservar autenticação e política de cobrança.', 'A agenda deve impedir sobreposição de reservas.'], 'autonomy': ['Organizar funções e testes dentro do módulo de agenda.'], 'decisions': [], 'rules': [{'id': 'RES-01', 'description': 'Consultar horários disponíveis', 'acceptance': ['Exibir somente horários livres do profissional selecionado.'], 'depends_on': []}, {'id': 'RES-02', 'description': 'Impedir duas reservas no mesmo horário', 'acceptance': ['Duas solicitações concorrentes produzem apenas uma reserva.', 'A segunda pessoa recebe uma mensagem de indisponibilidade.'], 'depends_on': ['reservas/RES-01']}, {'id': 'RES-03', 'description': 'Cancelar somente a própria reserva', 'acceptance': ['Outro paciente não pode cancelar a reserva.'], 'depends_on': []}]}
    write(root, '.centaur/contracts/reservas/v001.json', c)
    write(root, '.centaur/use-cases/reservas.json', {'schema': 1, 'contract': 'reservas', 'version': 1, 'title': 'Reserva de uma consulta', 'summary': 'Exemplo fictício editável; o fluxo organiza a jornada sem aprovar o contrato.', 'nodes': [
        {'id': 'inicio', 'kind': 'start', 'label': 'Paciente inicia reserva', 'detail': ''},
        {'id': 'consulta', 'kind': 'action', 'label': 'Consulta horários livres', 'detail': 'Filtra o profissional selecionado.'},
        {'id': 'livre', 'kind': 'decision', 'label': 'Horário ainda disponível?', 'detail': 'Confirmar no ato da reserva.'},
        {'id': 'confirmar', 'kind': 'action', 'label': 'Confirmar reserva', 'detail': 'Impedir duplicidade concorrente.'},
        {'id': 'indisponivel', 'kind': 'end', 'label': 'Informar indisponibilidade', 'detail': ''},
        {'id': 'fim', 'kind': 'end', 'label': 'Enviar confirmação', 'detail': ''}
    ], 'edges': [{'from': 'inicio', 'to': 'consulta', 'label': ''}, {'from': 'consulta', 'to': 'livre', 'label': ''}, {'from': 'livre', 'to': 'confirmar', 'label': 'Sim'}, {'from': 'livre', 'to': 'indisponivel', 'label': 'Não'}, {'from': 'confirmar', 'to': 'fim', 'label': ''}]})
    write(root, 'src/agenda.py', 'def horarios_disponiveis(horarios):\n    """Exemplo didático: exclui horários ocupados."""\n    return [h for h in horarios if not h["ocupado"]]\n\ndef reservar(horario):\n    raise NotImplementedError("Adicionar proteção concorrente")\n')
    state = {'schema': 1, 'contract': 'reservas@1', 'rules': {'RES-01': {'implementation': 'implementada', 'sources': [{'path': 'src/agenda.py', 'start': 1, 'end': 3, 'role': 'Disponibilidade de horários'}], 'evidence': [], 'delivery': {'stage': 'integrated', 'revision': 'demo-001', 'at': '2026-09-27T03:00:00Z', 'reference': 'Integração fictícia da demonstração'}}, 'RES-02': {'implementation': 'parcial', 'sources': [{'path': 'src/agenda.py', 'start': 5, 'end': 6, 'role': 'Reserva em construção'}], 'evidence': []}}}
    write(root, '.centaur/state/reservas.json', state)
    data = load_project(root)
    e = {'schema': 1, 'id': 'ev-demo', 'contract': 'reservas@1', 'rule': 'RES-01', 'contract_hash': data['contracts'][0]['hash'], 'method': 'test', 'result': 'passed', 'at': '2026-09-27T03:05:00Z', 'summary': 'Demonstração: seleção de horários livres.', 'reference': 'Evidência fictícia, não representa execução real.', 'files': {'src/agenda.py': hashlib.sha256((root/'src/agenda.py').read_bytes()).hexdigest()}, 'command': ['python3', '-m', 'unittest', 'test_agenda'], 'revision': 'demo-001'}
    write(root, '.centaur/evidence/ev-demo.json', e)
    state['rules']['RES-01']['evidence'] = ['ev-demo']
    write(root, '.centaur/state/reservas.json', state)
    c2 = {**c, 'id': 'lembretes', 'title': 'Lembrar o paciente da consulta', 'scope': 'notificacoes', 'status': 'draft', 'intent': 'Enviar um lembrete antes da consulta, respeitando a preferência do paciente.', 'decisions': ['Com quantas horas de antecedência enviar o lembrete?'], 'rules': [{'id': 'LEM-01', 'description': 'Enviar lembrete no canal autorizado', 'acceptance': ['Enviar somente a pacientes que aceitaram o canal.'], 'depends_on': ['reservas/RES-02']}]}
    write(root, '.centaur/contracts/lembretes/v001.json', c2)
    write(root, '.centaur/specs/0001/README.md', '# [0001] Reserva com proteção de concorrência\n\n**Status:** Em andamento\n**Contrato:** reservas@1\n\n## Checklist de conclusão\n- [x] Task 01 — Consultar disponibilidade\n- [ ] Task 02 — Proteger reserva concorrente\n')
    write(root, 'docs/system/Fluxos/Agendamento.md', '# Jornada de agendamento\n\nPaciente consulta horários → escolhe profissional → reserva → recebe confirmação.\n\nEste documento é fictício e descreve a intenção da demonstração.\n')
    return c, state, e


if __name__ == '__main__':
    fixture(Path(sys.argv[1]).resolve())
