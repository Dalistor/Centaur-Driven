import copy
import tempfile
import unittest
from pathlib import Path
from support import fixture, write, load_project


class SpecificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.contract, _, _ = fixture(self.root)
        self.specification = {
            'actors': ['Paciente'], 'exclusions': ['Cobrança'],
            'use_cases': [{'id': 'UC-01', 'title': 'Consultar horários', 'actor': 'Paciente',
                           'main_flow': ['Consultar agenda'], 'rules': ['RES-01']}],
            'data_model': {'entities': [{'name': 'Paciente'}, {'name': 'Reserva'}],
                           'relationships': [{'from': 'Paciente', 'to': 'Reserva', 'cardinality': '1:N'}]}}

    def save(self, spec):
        self.contract['specification'] = spec
        write(self.root, '.centaur/contracts/reservas/v001.json', self.contract)
        return load_project(self.root)

    def test_conceptual_change_invalidates_existing_evidence(self):
        before = load_project(self.root)
        original = next(c for c in before['contracts'] if c['id'] == 'reservas')
        self.assertEqual(original['rules'][0]['verification'], 'aprovada')
        after = self.save(self.specification)
        contract = next(c for c in after['contracts'] if c['id'] == 'reservas')
        self.assertEqual(contract['specification'], self.specification)
        self.assertEqual(contract['rules'][0]['verification'], 'desatualizada')

    def test_invalid_references_do_not_produce_executable_contract(self):
        for mutate in (
            lambda s: s['use_cases'][0].update(actor='Desconhecido'),
            lambda s: s['use_cases'][0].update(rules=['RF-INEXISTENTE']),
            lambda s: s['data_model']['relationships'][0].update(to='Inexistente'),
            lambda s: s['data_model']['relationships'][0].update(cardinality='qualquer'),
        ):
            spec = copy.deepcopy(self.specification)
            mutate(spec)
            data = self.save(spec)
            self.assertTrue(data['warnings'])
            self.assertFalse(any(c['id'] == 'reservas' for c in data['contracts']))

    def test_requirement_kind_is_checked(self):
        self.contract['rules'][0]['kind'] = 'non_functional'
        self.assertTrue(any(c['id'] == 'reservas' for c in self.save(self.specification)['contracts']))
        self.contract['rules'][0]['kind'] = 'unknown'
        self.assertFalse(any(c['id'] == 'reservas' for c in self.save(self.specification)['contracts']))
