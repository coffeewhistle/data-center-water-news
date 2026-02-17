import unittest

from batching_utils import dedupe_companies, dedupe_people, company_key, person_key


class BatchingUtilsTests(unittest.TestCase):
    def test_company_dedupe_uses_case_insensitive_name(self):
        companies = [
            {"name": "Acme Corp", "sector": "Cloud"},
            {"name": "  acme corp  ", "sector": "Infra"},
            {"name": "Beta LLC", "sector": "Power"},
        ]
        deduped = dedupe_companies(companies)
        self.assertEqual(len(deduped), 2)
        self.assertIn(company_key("Acme Corp"), deduped)
        self.assertIn(company_key("Beta LLC"), deduped)

    def test_people_dedupe_uses_name_and_company(self):
        people = [
            {"full_name": "Jane Doe", "primary_company": "Acme"},
            {"full_name": "jane doe", "primary_company": "acme"},
            {"full_name": "Jane Doe", "primary_company": "Beta"},
        ]
        deduped = dedupe_people(people)
        self.assertEqual(len(deduped), 2)
        self.assertIn(person_key("Jane Doe", "Acme"), deduped)
        self.assertIn(person_key("Jane Doe", "Beta"), deduped)


if __name__ == "__main__":
    unittest.main()
