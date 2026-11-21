import math

from inteligentny_asystent_urzednika import llm


def test_atrapa_generuje_i_osadza():
    a = llm.Atrapa()
    assert a.generuj("pytanie").startswith("[ATRAPA LLM]")
    w1, w2, w3 = a.osadz(["koszt remontu ulicy", "koszty remontu ulic", "diety radnych"])
    iloczyn = lambda x, y: sum(p * q for p, q in zip(x, y))
    assert math.isclose(iloczyn(w1, w1), 1.0)
    assert iloczyn(w1, w2) > iloczyn(w1, w3)


def test_domyslny_backend_to_atrapa():
    assert isinstance(llm.model_tekstowy(), llm.Atrapa)
    assert len(llm.osadz(["test"])[0]) == llm.WYMIAR_ATRAPY
