from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from db import get_training_data


def rank(articles):
    if not articles:
        return []

    data = get_training_data()
    positives = sum(1 for d in data if d["selected"] == 1)

    if len(data) < 10 or positives == 0:
        return [(a, None) for a in articles]

    texts = [f"{d['title']} {d['abstract']}" for d in data]
    labels = [d["selected"] for d in data]

    vec = TfidfVectorizer(max_features=5000, stop_words="english", sublinear_tf=True)
    X = vec.fit_transform(texts)

    clf = LogisticRegression(max_iter=1000, C=1.0, class_weight="balanced")
    clf.fit(X, labels)

    article_texts = [f"{a['title']} {a['abstract']}" for a in articles]
    probs = clf.predict_proba(vec.transform(article_texts))[:, 1].tolist()

    return sorted(zip(articles, probs), key=lambda x: x[1], reverse=True)
