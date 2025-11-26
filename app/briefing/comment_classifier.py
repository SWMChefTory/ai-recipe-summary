import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


class CommentClassifier:
    def __init__(self, model_id, threshold=0.5):
        self.model = AutoModelForSequenceClassification.from_pretrained(model_id)
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model.eval()
        self.threshold = threshold

    def predict(self, comments):
        results = []
        for text in comments:
            inputs = self.tokenizer(text, return_tensors="pt", truncation=True, padding=True)
            with torch.no_grad():
                logits = self.model(**inputs).logits
                probs = torch.softmax(logits, dim=1)
                label = torch.argmax(probs, dim=1).item()
                if label == 1:
                    results.append(text)
        return results
