import torch
import torch.nn as nn
import torch.optim as optim

class LSTMClassifier(nn.Module):
    def __init__(self, vocab_size, embed_dim, hidden_dim, num_layers, num_class, dropout=0.2, bidirectional=False):
        super(LSTMClassifier, self).__init__()
        
        # Embedding layer
        self.embedding = nn.Embedding(num_embeddings=vocab_size,
                                      embedding_dim=embed_dim,
                                      padding_idx=0)
        
        # Unidirectional LSTM layer
        self.lstm = nn.LSTM(input_size=embed_dim,
                            hidden_size=hidden_dim,
                            num_layers=num_layers,
                            batch_first=True,
                            dropout=dropout,
                            bidirectional=bidirectional)  # No bidirectionality

        # Single fully connected classification layer
        self.fc = nn.Linear(hidden_dim, num_class)

    def forward(self, text):
        # Embedding lookup
        embedded = self.embedding(text)

        # LSTM forward pass
        lstm_out, _ = self.lstm(embedded)  # Output shape: (batch_size, seq_len, hidden_dim)

        # Extract the output of the last time step
        lstm_out = lstm_out[:, -1, :]  # Shape: (batch_size, hidden_dim)

        # Fully connected layer for classification
        logits = self.fc(lstm_out)  # Output shape: (batch_size, num_class)

        return logits
