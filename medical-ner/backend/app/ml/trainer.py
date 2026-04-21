import math
import json
import numpy as np
import torch
import torch.nn as nn
from collections import Counter
from pathlib import Path
from typing import Dict, List

from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    DataCollatorForTokenClassification,
)
from datasets import Dataset
from seqeval.metrics import f1_score, precision_score, recall_score


class _WeightedNERTrainer(Trainer):
    """HuggingFace Trainer subclass that applies per-class loss weighting."""

    def __init__(self, *args, class_weights: torch.Tensor = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits  # (batch, seq_len, num_labels)

        weight = self.class_weights.to(logits.device) if self.class_weights is not None else None
        loss_fct = nn.CrossEntropyLoss(weight=weight, ignore_index=-100)
        loss = loss_fct(logits.view(-1, model.config.num_labels), labels.view(-1))

        return (loss, outputs) if return_outputs else loss


class PhoBERTNERTrainer:
    """Fine-tune PhoBERT for Vietnamese medical NER."""

    LABELS = [
        "O",
        "B-DISEASE", "I-DISEASE",
        "B-DRUG", "I-DRUG",
        "B-SYMPTOM", "I-SYMPTOM",
        "B-TREATMENT", "I-TREATMENT",
        "B-BODY_PART", "I-BODY_PART",
        "B-TEST", "I-TEST",
        "B-VALUE", "I-VALUE",
        "B-DATE", "I-DATE",
    ]

    def __init__(self, model_name: str = "vinai/phobert-base"):
        self.model_name = model_name
        self.num_labels = len(self.LABELS)
        self.label2id = {label: i for i, label in enumerate(self.LABELS)}
        self.id2label = {i: label for i, label in enumerate(self.LABELS)}

        self.tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
        self.model = AutoModelForTokenClassification.from_pretrained(
            model_name,
            num_labels=self.num_labels,
            id2label=self.id2label,
            label2id=self.label2id,
        )

        self._freeze_layers(num_freeze=8)

    def _freeze_layers(self, num_freeze: int):
        for param in self.model.roberta.embeddings.parameters():
            param.requires_grad = False
        for i in range(num_freeze):
            for param in self.model.roberta.encoder.layer[i].parameters():
                param.requires_grad = False
        print(f"Frozen {num_freeze}/12 transformer layers")

    def load_dataset(self, data_path: Path) -> Dataset:
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Dataset.from_dict({
            "tokens": [item["tokens"] for item in data],
            "tags": [item["tags"] for item in data],
            "source": [item.get("source", "") for item in data],
        })

    def _get_word_ids_slow(self, words: list, input_ids: list) -> list:
        """Manual word_ids for slow tokenizers (PhoBERT SentencePiece)."""
        word_ids = [None]  # CLS
        for word_idx, word in enumerate(words):
            subwords = self.tokenizer.tokenize(word) or [self.tokenizer.unk_token]
            word_ids.extend([word_idx] * len(subwords))
        word_ids.append(None)  # SEP

        if len(word_ids) >= len(input_ids):
            word_ids = word_ids[: len(input_ids)]
        else:
            word_ids.extend([None] * (len(input_ids) - len(word_ids)))
        return word_ids

    def tokenize_and_align_labels(self, examples):
        """Tokenize and align BIO labels — only the first subword of each word
        keeps the word label; continuation subwords are masked with -100."""
        tokenized_inputs = self.tokenizer(
            examples["tokens"],
            truncation=True,
            is_split_into_words=True,
            max_length=256,
            padding="max_length",
        )

        labels = []
        for i, label in enumerate(examples["tags"]):
            input_ids = tokenized_inputs["input_ids"][i]
            word_ids = self._get_word_ids_slow(examples["tokens"][i], input_ids)

            label_ids = []
            previous_word_idx = None
            for word_idx in word_ids:
                if word_idx is None:
                    label_ids.append(-100)
                elif word_idx != previous_word_idx:
                    # First subword: use the word's BIO label
                    label_ids.append(self.label2id[label[word_idx]])
                else:
                    # Continuation subword: mask from loss
                    label_ids.append(-100)
                previous_word_idx = word_idx

            labels.append(label_ids)

        tokenized_inputs["labels"] = labels
        return tokenized_inputs

    @staticmethod
    def compute_class_weights(
        tokenized_dataset: Dataset,
        num_labels: int,
        label2id: Dict[str, int],
    ) -> torch.Tensor:
        """Compute per-class weights using sqrt inverse frequency.

        "O" and padding (-100) are kept at weight 1.0 so the dominant O class
        does not suppress entity signal.  Entity labels are boosted by
        sqrt(max_entity_count / class_count), capped at 10.0.
        """
        counts: Counter = Counter()
        for label_seq in tokenized_dataset["labels"]:
            for lbl in label_seq:
                if lbl != -100:
                    counts[lbl] += 1

        b_label_ids = [idx for name, idx in label2id.items() if name.startswith("B-")]
        max_b_count = max((counts.get(idx, 1) for idx in b_label_ids), default=1)

        weights = torch.ones(num_labels)
        for name, idx in label2id.items():
            if name == "O":
                weights[idx] = 1.0
            elif name.startswith(("B-", "I-")):
                count = max(counts.get(idx, 1), 1)
                weights[idx] = min(math.sqrt(max_b_count / count), 10.0)

        print("Class weights:")
        for name, idx in sorted(label2id.items(), key=lambda x: x[1]):
            print(f"  {name:<15} w={weights[idx]:.2f}  (n={counts.get(idx, 0)})")

        return weights

    def compute_metrics(self, p):
        predictions, labels = p
        predictions = np.argmax(predictions, axis=2)

        true_predictions = [
            [self.LABELS[pred] for (pred, lbl) in zip(prediction, label) if lbl != -100]
            for prediction, label in zip(predictions, labels)
        ]
        true_labels = [
            [self.LABELS[lbl] for (pred, lbl) in zip(prediction, label) if lbl != -100]
            for prediction, label in zip(predictions, labels)
        ]

        return {
            "precision": precision_score(true_labels, true_predictions),
            "recall": recall_score(true_labels, true_predictions),
            "f1": f1_score(true_labels, true_predictions),
        }

    def train(
        self,
        train_dataset: Dataset,
        val_dataset: Dataset,
        output_dir: Path,
        num_epochs: int = 5,
        learning_rate: float = 2e-5,
        batch_size: int = 16,
    ) -> Trainer:
        tokenized_train = train_dataset.map(self.tokenize_and_align_labels, batched=True)
        tokenized_val = val_dataset.map(self.tokenize_and_align_labels, batched=True)

        class_weights = self.compute_class_weights(
            tokenized_dataset=tokenized_train,
            num_labels=self.num_labels,
            label2id=self.label2id,
        )

        data_collator = DataCollatorForTokenClassification(tokenizer=self.tokenizer)

        training_args = TrainingArguments(
            output_dir=str(output_dir),
            num_train_epochs=num_epochs,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            learning_rate=learning_rate,
            weight_decay=0.01,
            warmup_steps=100,
            eval_strategy="epoch",
            save_strategy="epoch",
            load_best_model_at_end=True,
            metric_for_best_model="f1",
            logging_dir=str(output_dir / "logs"),
            logging_steps=50,
            save_total_limit=3,
            fp16=torch.cuda.is_available(),
        )

        trainer = _WeightedNERTrainer(
            model=self.model,
            args=training_args,
            train_dataset=tokenized_train,
            eval_dataset=tokenized_val,
            data_collator=data_collator,
            tokenizer=self.tokenizer,
            compute_metrics=self.compute_metrics,
            class_weights=class_weights,
        )

        print("Starting training...")
        trainer.train()

        trainer.save_model(str(output_dir / "final_model"))
        self.tokenizer.save_pretrained(str(output_dir / "final_model"))

        print(f"Model saved to {output_dir / 'final_model'}")
        return trainer
