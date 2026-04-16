import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.services import questionnaire_runtime_service as qr


def test_pin_hash_and_verify_roundtrip():
    pin = "123456"
    hashed = qr.hash_pin(pin)
    assert hashed != pin
    assert qr.verify_pin(pin, hashed) is True
    assert qr.verify_pin("000000", hashed) is False


def test_review_tag_canonicalization():
    assert qr.canonical_review_tag("sin revisar") == "sin_revisar"
    assert qr.canonical_review_tag("en revision") == "en_revision"
    assert qr.canonical_review_tag("cerrado") == "cerrado"


def test_domain_policy_includes_five_domains_and_elimination_caveat():
    assert qr.DOMAIN_ORDER == ["adhd", "conduct", "elimination", "anxiety", "depression"]
    assert qr.DOMAIN_MODEL_POLICY["elimination"]["model_status"] == "experimental_line_more_useful_not_product_ready"
