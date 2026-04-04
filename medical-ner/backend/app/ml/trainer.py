import torch
import numpy as np
import json
from pathlib import Path
from typing import Dict, List

from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    DataCollatorForTokenClassification
)
from datasets import Dataset
from seqeval.metrics import f1_score, precision_score, recall_score


class PhoBERTNERTrainer:
    """Fine-tune PhoBERT for Vietnamese medical NER"""

    LABELS = [
        'O',
        'B-DISEASE', 'I-DISEASE',
        'B-DRUG', 'I-DRUG',
        'B-SYMPTOM', 'I-SYMPTOM',
        'B-TREATMENT', 'I-TREATMENT',
        'B-BODY_PART', 'I-BODY_PART',
        'B-TEST', 'I-TEST'
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
            label2id=self.label2id
        )

        self._freeze_layers(num_freeze=8)

    def _freeze_layers(self, num_freeze: int):
        """Freeze bottom N transformer layers for transfer learning"""
        for param in self.model.roberta.embeddings.parameters():
            param.requires_grad = False

        for i in range(num_freeze):
            for param in self.model.roberta.encoder.layer[i].parameters():
                param.requires_grad = False

        print(f"Frozen {num_freeze}/12 transformer layers")

    def load_dataset(self, data_path: Path) -> Dataset:
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return Dataset.from_dict({
            "tokens": [item["tokens"] for item in data],
            "tags": [item["tags"] for item in data]
        })

    def _get_word_ids_slow(self, words: list, input_ids: list) -> list:
        """Manual word_ids for slow tokenizers (e.g. PhoBERT sentencepiece)"""
        word_ids = [None]  # CLS token

        for word_idx, word in enumerate(words):
            subwords = self.tokenizer.tokenize(word)
            if not subwords:
                subwords = [self.tokenizer.unk_token]
            word_ids.extend([word_idx] * len(subwords))

        word_ids.append(None)  # SEP token

        # Align length with input_ids (truncate or pad with None)
        if len(word_ids) >= len(input_ids):
            word_ids = word_ids[:len(input_ids)]
        else:
            word_ids.extend([None] * (len(input_ids) - len(word_ids)))

        return word_ids

    def tokenize_and_align_labels(self, examples):
        """Tokenize and align BIO labels with subword tokens"""
        tokenized_inputs = self.tokenizer(
            examples["tokens"],
            truncation=True,
            is_split_into_words=True,
            max_length=256,
            padding="max_length"
        )

        labels = []
        for i, label in enumerate(examples["tags"]):
            input_ids = tokenized_inputs["input_ids"][i]
            words = examples["tokens"][i]
            word_ids = self._get_word_ids_slow(words, input_ids)

            label_ids = []
            previous_word_idx = None
            for word_idx in word_ids:
                if word_idx is None:
                    label_ids.append(-100)
                elif word_idx != previous_word_idx:
                    label_ids.append(self.label2id[label[word_idx]])
                else:
                    label_ids.append(self.label2id[label[word_idx]])
                previous_word_idx = word_idx

            labels.append(label_ids)

        tokenized_inputs["labels"] = labels
        return tokenized_inputs

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
        batch_size: int = 16
    ) -> Trainer:
        tokenized_train = train_dataset.map(self.tokenize_and_align_labels, batched=True)
        tokenized_val = val_dataset.map(self.tokenize_and_align_labels, batched=True)

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

        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=tokenized_train,
            eval_dataset=tokenized_val,
            data_collator=data_collator,
            tokenizer=self.tokenizer,
            compute_metrics=self.compute_metrics,
        )

        print("Starting training...")
        trainer.train()

        trainer.save_model(str(output_dir / "final_model"))
        self.tokenizer.save_pretrained(str(output_dir / "final_model"))

        print(f"Model saved to {output_dir / 'final_model'}")
        return trainer
