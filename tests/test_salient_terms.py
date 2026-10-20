from pipeline.cluster_math import salient_terms


def test_salient_terms_fills_at_least_four_for_faces():
    texts = [f"diesel export ban policy wording variant {index}" for index in range(12)]
    terms = salient_terms(texts, limit=8)
    assert len(terms) >= 4
