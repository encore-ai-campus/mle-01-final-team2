"""순수 파이썬 BM25(문자 bigram). 형태소 분석기·임베딩 모델 없이 한국어 청크를 검색한다.

한계: 의미 검색(임베딩)이 아니다. 어휘가 겹치지 않는 질문은 찾지 못한다. 임베딩은 모델 선택 후 이 인터페이스 뒤에 붙인다.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

TOKEN = re.compile(r"[가-힣A-Za-z0-9]+")


def tokenize(text: str) -> list[str]:
    out = []
    for w in TOKEN.findall(text.lower()):
        if len(w) == 1:
            out.append(w)
        else:
            out += [w[i:i + 2] for i in range(len(w) - 1)]
            if w.isascii():
                out.append(w)
    return out


class BM25:
    def __init__(self, docs: list[dict], k1: float = 1.5, b: float = 0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.index: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.len = []
        for i, d in enumerate(docs):
            tf = Counter(tokenize(d["text"]))
            self.len.append(sum(tf.values()))
            for t, c in tf.items():
                self.index[t].append((i, c))
        self.avg = (sum(self.len) / len(self.len)) if self.len else 0
        self.n = len(docs)

    def search(self, query: str, allowed_notices: set[str] | None = None, top: int = 20) -> list[tuple[float, dict]]:
        scores: dict[int, float] = defaultdict(float)
        for t in set(tokenize(query)):
            post = self.index.get(t)
            if not post:
                continue
            idf = math.log(1 + (self.n - len(post) + 0.5) / (len(post) + 0.5))
            for i, tf in post:
                if allowed_notices is not None and self.docs[i]["notice_id"] not in allowed_notices:
                    continue
                denom = tf + self.k1 * (1 - self.b + self.b * self.len[i] / (self.avg or 1))
                scores[i] += idf * tf * (self.k1 + 1) / denom
        best = sorted(scores.items(), key=lambda x: -x[1])[:top]
        return [(s, self.docs[i]) for i, s in best]
