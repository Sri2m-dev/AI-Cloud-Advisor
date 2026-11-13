import copy,json,pathlib,unittest
from validate import validate_contract
BASE=json.loads(pathlib.Path(__file__).with_name('compose.yaml').read_text())
class IsolationTests(unittest.TestCase):
    def test_valid(self): self.assertTrue(validate_contract(BASE))
    def reject(self,change):
        c=copy.deepcopy(BASE); change(c)
        with self.assertRaises(AssertionError): validate_contract(c)
    def test_published_port(self): self.reject(lambda c:c['services']['postgres'].update(ports=['5432:5432']))
    def test_external_network(self): self.reject(lambda c:c['networks']['private'].update(internal=False))
    def test_wrong_volume(self): self.reject(lambda c:c['volumes']['postgres_data'].update(name='ai-cloud-advisor-p3-clean_evidence_data'))
    def test_remote_database(self): self.reject(lambda c:c['services']['qualification']['environment'].update(PGHOST='remote'))
    def test_tls_bypass(self): self.reject(lambda c:c['services']['qualification']['environment'].update(PGSSLMODE='disable'))
    def test_ignored_sql_errors(self): self.reject(lambda c:c['services']['qualification'].update(command=['psql']))
    def test_image_pull(self): self.reject(lambda c:c['services']['postgres'].update(pull_policy='always'))
if __name__=='__main__': unittest.main()
