"""In-memory cosine-similarity matcher against the registered-people library.

Fine up to a few thousand people (per the plan); replace with FAISS or a
vector index only if Phase 3/6 measurements show this is a bottleneck.
"""
from functools import lru_cache

import numpy as np

from app.repos.people_repo import PeopleRepo

EMBEDDING_DIM = 192  # SpeechBrain ECAPA-TDNN output size


class Matcher:
    def __init__(self, people_repo: PeopleRepo):
        self.people_repo = people_repo
        self._ids: list[str] = []
        self._matrix = np.zeros((0, EMBEDDING_DIM), dtype=np.float32)
        self.refresh()

    def refresh(self) -> None:
        people = self.people_repo.list_active()
        ids = []
        vectors = []
        for doc in people:
            ids.append(doc["_id"])
            vectors.append(self.people_repo.get_vector(doc))
        self._ids = ids
        self._matrix = np.stack(vectors) if vectors else np.zeros((0, EMBEDDING_DIM), dtype=np.float32)

    def rank(self, query_vec: np.ndarray) -> list[tuple[str, float]]:
        """Returns [(person_id, cosine_similarity), ...] sorted best-first."""
        if self._matrix.shape[0] == 0:
            return []
        sims = self._matrix @ query_vec  # vectors are unit-norm -> dot product == cosine sim
        order = np.argsort(-sims)
        return [(self._ids[i], float(sims[i])) for i in order]


@lru_cache(maxsize=1)
def get_matcher() -> Matcher:
    return Matcher(PeopleRepo())
