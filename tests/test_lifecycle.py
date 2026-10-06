import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from support import SCRIPTS, fixture, write
from lifecycle import load_project, project_path, validate_use_case


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.contract, self.state, self.evidence = fixture(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def rule(self, key='reservas/RES-01'):
        return next(r for c in load_project(self.root)['contracts'] for r in c['rules'] if r['key'] == key)

    def test_use_case_is_projected_separately_and_rejects_broken_links(self):
        project = load_project(self.root)
        self.assertEqual(project['use_cases'][0]['contract'], 'reservas')
        self.assertEqual(len(project['use_cases'][0]['nodes']), 6)
        case = copy.deepcopy(project['use_cases'][0])
        case['edges'].append({'from': 'missing', 'to': 'fim', 'label': ''})
        with self.assertRaisesRegex(ValueError, 'inexistente'):
            validate_use_case(case, next(c for c in project['contracts'] if c['id'] == 'reservas'))
        write(self.root, '.centaur/use-cases/reservas.json', case)
        broken = load_project(self.root)
        self.assertFalse(broken['use_cases'])
        self.assertTrue(any('inexistente' in w for w in broken['warnings']))

    def cli(self, script, *args):
        return subprocess.run([sys.executable, str(SCRIPTS/script), str(self.root), *args], capture_output=True, text=True)

    def test_independent_dimensions_and_ready_gate(self):
        r=self.rule()
        self.assertEqual((r['implementation'], r['verification'], r['delivery']['stage']), ('implementada', 'aprovada', 'integrated'))
        self.assertEqual(self.cli('validate-lifecycle.py', '--ready', r['key']).returncode, 0)
        self.assertEqual(self.cli('validate-lifecycle.py', '--ready', 'reservas/RES-02').returncode, 1)
        self.assertEqual(self.rule('reservas/RES-02')['next'], 'Implementar comportamento')

    def test_source_change_invalidates_evidence_and_dependent_rule(self):
        with (self.root/'src/agenda.py').open('a') as f:f.write('\n# changed\n')
        self.assertEqual(self.rule()['verification'], 'desatualizada')
        self.assertEqual(self.rule()['delivery']['stage'], 'integrated')
        self.assertEqual(self.rule('reservas/RES-02')['next'], 'Aguardar dependências integradas')
        self.assertEqual(self.cli('validate-lifecycle.py','--ready','reservas/RES-01').returncode,1)

    def test_contract_version_and_inline_change_invalidate(self):
        c=copy.deepcopy(self.contract);c['rules'][0]['acceptance'].append('Novo critério')
        write(self.root,'.centaur/contracts/reservas/v001.json',c)
        self.assertEqual(self.rule()['verification'],'desatualizada')
        c['version']=2;write(self.root,'.centaur/contracts/reservas/v002.json',c)
        self.assertEqual(self.rule()['implementation'],'ausente')
        self.assertTrue(load_project(self.root)['warnings'])

    def test_draft_never_replaces_approved_or_grants_execution(self):
        c=copy.deepcopy(self.contract);c.update(version=2,status='draft')
        write(self.root,'.centaur/contracts/reservas/v002.json',c)
        self.assertEqual(self.rule()['version'],1)
        self.assertEqual(self.rule('lembretes/LEM-01')['next'],'Resolver contrato ou decisão humana')

    def test_inheritance_and_dependency_cycles(self):
        c=copy.deepcopy(self.contract);c['extends']=['reservas@1'];write(self.root,'.centaur/contracts/reservas/v001.json',c)
        self.assertIn('Herança circular',str(load_project(self.root)['warnings']))
        c['extends']=[];c['rules'][0]['depends_on']=['reservas/RES-02'];write(self.root,'.centaur/contracts/reservas/v001.json',c)
        self.assertIn('Dependência circular',str(load_project(self.root)['warnings']))
        self.assertFalse(self.rule()['eligible'])

    def test_blocked_dependency_propagates_transitively(self):
        from lifecycle import object_digest
        # Give each rule a separate source, so only the first rule's evidence ages.
        rules = []
        self.contract['rules'] = []
        self.state['rules'] = {}
        for n in range(3):
            rid = f'R{n}'
            rule = {'id': rid, 'description': f'Behavior {n}', 'acceptance': ['Observable result'], 'depends_on': [f'reservas/R{n-1}'] if n else []}
            self.contract['rules'].append(rule)
            write(self.root, f'src/r{n}.py', f'VALUE = {n}\n')
            self.state['rules'][rid] = {'implementation': 'implementada', 'sources': [{'path': f'src/r{n}.py'}], 'evidence': [], 'delivery': {'stage': 'integrated', 'revision': 'fixture', 'reference': 'fixture', 'at': '2026-09-27T03:00:00Z'}}
        write(self.root, '.centaur/contracts/reservas/v001.json', self.contract)
        write(self.root, '.centaur/state/reservas.json', self.state)
        from lifecycle import digest
        fingerprint = next(c for c in load_project(self.root)['contracts'] if c['id']=='reservas')['hash']
        for n in range(3):
            e = {**self.evidence, 'id': f'ev-r{n}', 'rule': f'R{n}', 'contract_hash': fingerprint, 'files': {f'src/r{n}.py': digest(self.root/f'src/r{n}.py')}}
            write(self.root, f'.centaur/evidence/ev-r{n}.json', e)
            self.state['rules'][f'R{n}']['evidence'] = [e['id']]
        write(self.root, '.centaur/state/reservas.json', self.state)
        write(self.root, 'src/r0.py', 'VALUE = 100\n')
        self.assertEqual(self.rule('reservas/R2')['verification'], 'aprovada')
        self.assertEqual(self.rule('reservas/R2')['waiting'], ['reservas/R1'])
        self.assertEqual(self.cli('validate-lifecycle.py','--ready','reservas/R2').returncode,1)

    def test_missing_evidence_cannot_be_approved(self):
        (self.root/'.centaur/evidence/ev-demo.json').unlink()
        self.assertEqual(self.rule()['verification'],'não verificada')
        self.assertEqual(self.cli('validate-lifecycle.py','--ready','reservas/RES-01').returncode,1)

    def test_declared_implementation_without_source_is_partial(self):
        self.state['rules']['RES-01']['sources']=[]
        write(self.root,'.centaur/state/reservas.json',self.state)
        self.assertEqual(self.rule()['implementation'],'parcial')
        self.assertEqual(self.cli('validate-lifecycle.py','--ready','reservas/RES-01').returncode,1)

    def test_failed_check_and_delivery_reference(self):
        self.evidence['result']='failed';write(self.root,'.centaur/evidence/ev-demo.json',self.evidence)
        self.assertEqual(self.rule()['verification'],'falhou')
        self.state['rules']['RES-01']['delivery']={'stage':'published'}
        write(self.root,'.centaur/state/reservas.json',self.state)
        self.assertEqual(self.rule()['delivery']['stage'],'local')
        self.assertTrue(self.rule()['issues'])

    def test_path_escape_and_reserved_sources(self):
        for path in ('../outside.py','/etc/passwd','.env','keys/secret.json'):
            self.state['rules']['RES-01']['sources']=[{'path':path}]
            write(self.root,'.centaur/state/reservas.json',self.state)
            self.assertEqual(self.cli('validate-lifecycle.py','--ready','reservas/RES-01').returncode,1)
        outside=self.root.parent/'external-lifecycle-test.py';outside.write_text('PRIVATE')
        try:
            (self.root/'src/link.py').symlink_to(outside)
            self.state['rules']['RES-01']['sources']=[{'path':'src/link.py'}]
            write(self.root,'.centaur/state/reservas.json',self.state)
            self.assertEqual(self.cli('validate-lifecycle.py').returncode,1)
        finally:outside.unlink()

    def test_capture_runs_actual_command_and_keeps_state_unchanged(self):
        old=(self.root/'.centaur/state/reservas.json').read_bytes()
        result=self.cli('record-evidence.py','reservas/RES-01','--summary','Teste real','--',sys.executable,'-c','assert 1 == 1')
        self.assertEqual(result.returncode,0,result.stderr)
        records=list((self.root/'.centaur/evidence').glob('ev-*.json'))
        self.assertEqual(len(records),2)
        self.assertEqual((self.root/'.centaur/state/reservas.json').read_bytes(),old)
        result=self.cli('record-evidence.py','reservas/RES-01','--summary','Falha real','--',sys.executable,'-c','raise SystemExit(3)')
        self.assertEqual(result.returncode,1,result.stderr)
        self.assertTrue(any(json.loads(x.read_text()).get('exit_code')==3 for x in (self.root/'.centaur/evidence').glob('*.json')))

    def test_executor_captures_without_writing_shared_state(self):
        (self.root/'.centaur/state/reservas.json').unlink()
        result=self.cli('record-evidence.py','reservas/RES-01','--summary','Bootstrap real','--file','src/agenda.py','--',sys.executable,'-c','print("executed")')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('executed',result.stdout)
        self.assertFalse((self.root/'.centaur/state/reservas.json').exists())
        self.assertEqual(len(list((self.root/'.centaur/evidence').glob('*.json'))),2)

    def test_capture_rejects_source_mutation_even_with_exit_zero(self):
        result=self.cli('record-evidence.py','reservas/RES-01','--summary','Mutação durante check','--',sys.executable,'-c',"from pathlib import Path; Path('src/agenda.py').write_text('changed')")
        self.assertEqual(result.returncode,1,result.stderr)
        record=next(json.loads(x.read_text()) for x in (self.root/'.centaur/evidence').glob('*.json') if x.name!='ev-demo.json')
        self.assertFalse(record['sources_stable'])


if __name__=='__main__':unittest.main()

class SpecCompletionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        fixture(self.root)
        self.path = '.centaur/specs/0002/README.md'
        self.body = ('# Entrega verificada\n\n**Status:** Em revisão\n'
                     '**Contrato:** reservas@1\n**Regras:** RES-01\n'
                     '**Specs filhas:** —\n**Dependências:** —\n\n'
                     '## Checklist de conclusão\n- [x] Disponibilidade\n')
        write(self.root, self.path, self.body)

    def gate(self, identifier='master/0002'):
        return subprocess.run([sys.executable, str(SCRIPTS / 'validate-lifecycle.py'),
                               str(self.root), '--complete', identifier], capture_output=True, text=True)

    def test_valid_integrated_delivery_is_complete_without_publication(self):
        result = self.gate()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual((self.root / self.path).read_text(), self.body)

    def test_checked_task_and_concluida_claim_do_not_replace_rule_evidence(self):
        write(self.root, self.path, self.body.replace('Em revisão', 'Concluída').replace('RES-01', 'RES-02'))
        result = self.gate()
        self.assertEqual(result.returncode, 1)
        self.assertIn('evidência corrente e integração', result.stdout)

    def test_missing_or_stale_contract_and_missing_rules_block(self):
        for body in (self.body.replace('reservas@1', 'reservas@2'),
                     self.body.replace('RES-01', 'DESCONHECIDA'),
                     self.body.replace('**Regras:** RES-01', ''),
                     self.body.replace('[x]', '[ ]')):
            write(self.root, self.path, body)
            self.assertEqual(self.gate().returncode, 1)

    def test_stale_evidence_blocks_completion(self):
        with (self.root / 'src/agenda.py').open('a') as stream: stream.write('\n# changed\n')
        self.assertEqual(self.gate().returncode, 1)

    def test_local_delivery_is_not_completion(self):
        path = self.root / '.centaur/state/reservas.json'
        state = json.loads(path.read_text())
        state['rules']['RES-01']['delivery'] = {'stage': 'local'}
        write(self.root, str(path.relative_to(self.root)), state)
        self.assertEqual(self.gate().returncode, 1)

    def test_children_declared_in_parent_or_only_child_link_block(self):
        write(self.root, self.path, self.body.replace('**Specs filhas:** —', '**Specs filhas:** master/0003'))
        self.assertIn('spec ausente', self.gate().stdout)
        write(self.root, self.path, self.body)
        write(self.root, '.centaur/specs/0003/README.md', self.body.replace(
            '**Specs filhas:** —', '**Spec mestre:** master/0002').replace('[x]', '[ ]'))
        self.assertIn('tasks pendentes', self.gate().stdout)

    def test_missing_dependencies_and_cycles_block(self):
        write(self.root, self.path, self.body.replace('**Dependências:** —', '**Dependências:** master/0009'))
        self.assertIn('spec ausente', self.gate().stdout)
        write(self.root, self.path, self.body.replace('**Dependências:** —', '**Dependências:** master/0003'))
        write(self.root, '.centaur/specs/0003/README.md', self.body.replace(
            '**Dependências:** —', '**Dependências:** master/0002'))
        self.assertIn('ciclo entre specs', self.gate().stdout)

    def test_missing_or_ambiguous_master_and_unqualified_dependencies_block(self):
        for field in ('**Spec mestre:** master/0099',
                      '**Spec mestre:** master/0001, master/0099',
                      '**Dependências:** 0001', '**Spec mestre:** master/0002'):
            write(self.root, self.path, self.body.replace('**Dependências:** —', field))
            self.assertEqual(self.gate().returncode, 1, field)
