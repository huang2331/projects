from app.analysis import count_words


def test_word_count_handles_contractions_and_hyphens():
    assert count_words("We're teaching evidence-based lessons, today.") == 5
