import torch
from torch import nn
import math

VOCABULARY_SIZE = 20_000
MAX_LENGTH = 20480 * 2
EMBEDDING_DIM = 128
DROPOUT = 0.1
NUM_CLASSES = 2

class PositionalEncoding(nn.Module):
    """
    https://pytorch.org/tutorials/beginner/transformer_tutorial.html
    """

    def __init__(self, d_model, max_length=MAX_LENGTH, dropout=DROPOUT):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)

        pe = torch.zeros(max_length, d_model)
        position = torch.arange(0, max_length, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float()
            * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)
        self.register_buffer("pe", pe)

    def forward(self, x):
        x = x + self.pe[:, : x.size(1), :]
        return self.dropout(x)

class TransformerClassifier(nn.Module):
    """
    Text classifier based on a pytorch TransformerEncoder.
    """

    def __init__(
        self,
        vocab_size=VOCABULARY_SIZE,
        d_model=EMBEDDING_DIM,
        max_length=MAX_LENGTH,
        nhead=8,
        dim_feedforward=2048,
        num_layers=6,
        dropout=0.1,
        activation="relu",
        classifier_dropout=DROPOUT,
        num_classes=NUM_CLASSES
    ):

        super().__init__()

        embeddings = nn.Embedding(vocab_size, d_model)
        assert d_model % nhead == 0, "nheads must divide evenly into d_model"

        self.emb = embeddings

        self.pos_encoder = PositionalEncoding(
            d_model=d_model,
            dropout=dropout,
            max_length=max_length,
        )

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
        )
        self.transformer_encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=num_layers,
        )
        self.classifier = nn.Linear(d_model, num_classes)
        self.d_model = d_model

    def forward(self, x):
        x = self.emb(x) * math.sqrt(self.d_model)
        x = self.pos_encoder(x)
        x = self.transformer_encoder(x)
        x = x.mean(dim=1)
        x = self.classifier(x)

        return x