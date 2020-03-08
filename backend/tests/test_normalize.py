import pytest

from jobs import normalize, skills


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("Northwind Analytics GmbH", "northwind analytics"),
        ("Northwind Analytics", "northwind analytics"),
        ("Granite Cloud Inc.", "granite cloud"),
        ("Bluefin Labs B.V.", "bluefin labs"),
        ("Maple & Moss Ltd", "maple and moss"),
        ("Café Ünïcode SA", "cafe unicode"),
        ("Limited", "limited"),  # a suffix alone is still a name
    ],
)
def test_company_key(raw, key):
    assert normalize.company_key(raw) == key


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("Sr. Full-Stack Developer (m/f/d)", "senior full stack developer"),
        ("Senior Full-Stack Developer", "senior full stack developer"),
        ("Jr. Data Engineer (m/w/d)", "junior data engineer"),
        ("Backend Engineer (all genders)", "back end engineer"),
        ("Senior Backend Eng", "senior back end engineer"),
        (".NET Developer", "net developer"),
        ("C# Developer", "c sharp developer"),
    ],
)
def test_title_key(raw, key):
    assert normalize.title_key(raw) == key


def test_fingerprint_matches_the_same_job_across_boards():
    a = normalize.fingerprint("Kestrel Media Ltd", "Senior Full-Stack Developer", "onsite", "Manchester", "GB")
    b = normalize.fingerprint("Kestrel Media", "Sr. Full-Stack Developer", "hybrid", "Manchester", None)
    assert a == b


def test_fingerprint_separates_different_places_and_remote():
    berlin = normalize.fingerprint("Acme", "Data Engineer", "onsite", "Berlin", "DE")
    munich = normalize.fingerprint("Acme", "Data Engineer", "onsite", "Munich", "DE")
    remote_us = normalize.fingerprint("Acme", "Data Engineer", "remote", None, None)
    remote_with_city = normalize.fingerprint("Acme", "Data Engineer", "remote", "Berlin", "DE")
    assert len({berlin, munich, remote_us}) == 3
    assert remote_us == remote_with_city  # remote jobs don't depend on where the company sits


@pytest.mark.parametrize(
    ("title", "kind", "level"),
    [
        ("Senior Python Developer", None, "senior"),
        ("Sr. Data Engineer (m/f/d)", None, "senior"),
        ("Junior Data Analyst", "internship", "intern"),
        ("Jr. iOS Engineer", None, "junior"),
        ("Lead DevOps Engineer", None, "lead"),
        ("Staff Backend Engineer", None, "staff"),
        ("Engineering Manager", None, "manager"),
        ("Python Developer", None, "mid"),
    ],
)
def test_seniority(title, kind, level):
    assert normalize.seniority(title, kind) == level


def test_annual_usd(settings):
    settings.FX_TO_USD = {"USD": 1.0, "EUR": 1.1}
    assert normalize.annual_usd(100_000, "USD", "year") == 100_000
    assert normalize.annual_usd(5_000, "EUR", "month") == 66_000
    assert normalize.annual_usd(50, "usd", "hour") == 104_000
    assert normalize.annual_usd(50, "JPY", "hour") is None
    assert normalize.annual_usd(None, "USD", "year") is None
    assert normalize.annual_usd(10, "USD", None) is None


def test_skills_map_board_tags_to_one_spelling():
    assert skills.extract_tags(["vue", "VueJS", "postgres", "k8s", "Node"], "", "") == [
        "Vue.js", "PostgreSQL", "Kubernetes", "Node.js",
    ]


def test_skills_keep_unknown_board_tags():
    assert skills.extract_tags(["Elixir"], "", "") == ["Elixir"]


def test_skills_from_title_and_description():
    tags = skills.extract_tags([], "Senior Go Engineer", "You will use Docker, CI/CD and C# with .NET Core.")
    assert tags == ["Go", "C#", ".NET", "Docker", "CI/CD"]


def test_ambiguous_words_are_not_taken_from_prose():
    tags = skills.extract_tags([], "Backend Engineer", "Let's go! We spring into action and value security.")
    assert tags == []

def trace_request(data=None):
    if data is None:
        return None
    return data