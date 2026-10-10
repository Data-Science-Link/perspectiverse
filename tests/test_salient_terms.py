from pipeline.cluster_math import salient_terms


def test_salient_terms_pads_up_to_four_when_threshold_is_strict():
    texts = [f"israel gaza conflict report variant {index}" for index in range(20)]
    terms = salient_terms(texts, limit=6)
    assert len(terms) >= 4
    assert len(terms) <= 6
    assert all(isinstance(term, str) and term for term in terms)


def test_salient_terms_keeps_single_post_bucket():
    terms = salient_terms(["only one post about diesel prices"], limit=6)
    assert terms == ["diesel"]
