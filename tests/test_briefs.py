from pipeline.briefs import apply_level_summaries, assemble_email, at_most_four, sentences


def _topic():
    return {
        "name": "Diesel Export Ban",
        "total_volume_percent": 5.7,
        "category": "Business",
        "perspectives": [
            {
                "id": "1A",
                "title": "No Diesel Ban",
                "summary": "The US will not ban diesel exports",
                "volume_percent": 60.0,
                "arguments": [
                    "A ban would strand refinery jobs",
                    "Exports keep the Gulf Coast plants running",
                ],
                "representative_posts": [
                    {"author": "ada", "text": "A diesel export ban would idle the Gulf Coast.", "likes": 4},
                ],
            },
            {
                "id": "1B",
                "title": "Oil Release",
                "summary": "G7 nations release oil reserves",
                "volume_percent": 40.0,
                "arguments": [
                    "Releasing reserves cools the price faster than a ban",
                ],
                "representative_posts": [
                    {"author": "bea", "text": "The G7 release is the tool they actually used.", "likes": 2},
                ],
            },
        ],
    }


def test_level_summaries_stay_within_four_sentences_and_name_the_split():
    topic = apply_level_summaries(_topic())
    assert 1 <= len(sentences(topic["brief"])) <= 4
    assert "\n\n" in topic["detail"]
    assert "Oil Release" in topic["detail"]
    face = topic["perspectives"][0]
    assert len(sentences(face["brief"])) <= 4
    assert "Gulf Coast" in face["detail"]
    assert at_most_four(face["brief"]) == face["brief"]


def test_email_lists_planets_with_arguments_and_the_disagreement():
    digest = assemble_email([_topic()])
    planet = digest["planets"][0]
    assert digest["subject"].startswith("This week:")
    assert planet["name"] == "Diesel Export Ban"
    assert any("No Diesel Ban" in item for item in planet["arguments"])
    assert "Oil Release" in planet["disagreement"]
    assert "No Diesel Ban" in planet["disagreement"]
