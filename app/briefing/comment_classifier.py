import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


class CommentClassifier:
    def __init__(self, model_id, threshold=0.5, batch_size=32):
        self.model = AutoModelForSequenceClassification.from_pretrained(model_id)
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model.eval()
        self.threshold = threshold
        self.batch_size = max(1, int(batch_size))

    def _iter_batches(self, comments):
        for start in range(0, len(comments), self.batch_size):
            yield comments[start : start + self.batch_size]

    def predict(self, comments):
        if not comments:
            return []

        results = []
        for batch in self._iter_batches(comments):
            inputs = self.tokenizer(batch, return_tensors="pt", truncation=True, padding=True)
            with torch.no_grad():
                logits = self.model(**inputs).logits
                probs = torch.softmax(logits, dim=1)[:, 1]
                keep_mask = probs >= self.threshold

            for text, keep in zip(batch, keep_mask.tolist()):
                if keep:
                    results.append(text)
        return results
