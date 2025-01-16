from torch import nn

class MLP_NLP(nn.Module):

    def __init__(self, vocab_size, embed_dim, num_class, hidden_size1, hidden_size2, hidden_size3, dropout=0.5):
        super(MLP_NLP, self).__init__()
        self.embedding = nn.Embedding(num_embeddings=vocab_size,
                                embedding_dim=embed_dim,
                                padding_idx=0,
                                max_norm=5.0)
        self.activation = nn.ReLU()
        self.dropout = nn.Dropout(dropout)
        self.fc1 = nn.Linear(embed_dim, hidden_size1)  # dense layer
        self.fc2 = nn.Linear(hidden_size1, hidden_size2)  # dense layer
        self.fc3 = nn.Linear(hidden_size2, hidden_size3)  # dense layer
        self.fc4 = nn.Linear(hidden_size3, num_class)  # dense layer
        self.init_weights()

    def init_weights(self):
        initrange = 0.5
        self.embedding.weight.data.uniform_(-initrange, initrange)
        self.fc1.weight.data.uniform_(-initrange, initrange)
        self.fc1.bias.data.zero_()
        self.fc2.weight.data.uniform_(-initrange, initrange)
        self.fc2.bias.data.zero_()
        self.fc3.weight.data.uniform_(-initrange, initrange)
        self.fc3.bias.data.zero_()
        self.fc4.weight.data.uniform_(-initrange, initrange)
        self.fc4.bias.data.zero_()


    def forward(self, text):
        embedded = self.embedding(text)
        embedded = embedded.mean(dim=1)
        h1 = self.fc1(embedded)
        a1 = self.activation(h1)
        d1 = self.dropout(a1)
        h2 = self.fc2(d1)
        a2 = self.activation(h2)
        d2 = self.dropout(a2)
        h3 = self.fc3(d2)
        a3 = self.activation(h3)
        d3 = self.dropout(a3)
        h4 = self.fc4(d3)
        y = h4
        return y