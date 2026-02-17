def company_key(name):
    if name is None:
        return None
    key = str(name).strip().lower()
    return key or None


def person_key(full_name, primary_company=None):
    if full_name is None:
        return None
    name_key = str(full_name).strip().lower()
    if not name_key:
        return None
    company_key_part = (primary_company or "").strip().lower()
    return f"{name_key}|{company_key_part}"


def dedupe_companies(companies):
    deduped = {}
    for company in companies:
        if not isinstance(company, dict):
            continue
        key = company_key(company.get("name"))
        if key and key not in deduped:
            deduped[key] = company
    return deduped


def dedupe_people(people):
    deduped = {}
    for person in people:
        if not isinstance(person, dict):
            continue
        key = person_key(person.get("full_name"), person.get("primary_company"))
        if key and key not in deduped:
            deduped[key] = person
    return deduped
