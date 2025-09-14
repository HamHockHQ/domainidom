from domainidom.utils.phonetics import phonetic_similarity, vowel_consonant_balance


def test_phonetic_similarity_basic():
    assert phonetic_similarity("Smith", "Smyth") >= 0.7


def test_vowel_consonant_balance():
    assert 0.0 <= vowel_consonant_balance("domain") <= 1.0
