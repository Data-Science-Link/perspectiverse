"""Mixed remarks is judged on a spread of the face, not the closest posts."""

from pipeline.live import _claim_sample, _posts_share_a_subject


def test_a_shared_claim_survives_when_the_closest_posts_differ():
    posts = []
    scores = []
    closest = [
        "The briefing mentioned logistics delays at the port.",
        "Weather halted the evening ferry crossing.",
        "Ticket prices jumped for the concert tonight.",
        "A court delayed the hearing until Monday.",
        "Farmers reported a weak harvest this season.",
        "The library closed early for repairs.",
    ]
    for index, text in enumerate(closest):
        posts.append({"text": text})
        scores.append(0.99 - index * 0.01)
    for index in range(34):
        posts.append({"text": f"Ukraine needs air defense after the latest strike {index}."})
        scores.append(0.50 - index * 0.01)
    sample = _claim_sample(posts, scores, limit=40)
    assert len(sample) > 6
    assert _posts_share_a_subject(sample)
    assert not _posts_share_a_subject(posts[:6])


def test_a_grab_bag_does_not_share_a_subject():
    posts = [
        {"text": "Medicare premiums rose again this year for seniors."},
        {"text": "The Lakers won in overtime on a late three."},
        {"text": "Oil prices fell after the reserve release."},
        {"text": "A new vaccine trial reported fewer hospitalizations."},
        {"text": "The opera season opens downtown on Friday night."},
    ]
    assert not _posts_share_a_subject(posts)
