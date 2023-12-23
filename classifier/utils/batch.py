"""
Batch helper functions adapted from https://medium.com/@bitdribble/migrate-torchtext-to-the-new-0-9-0-api-1ff1472b5d71
"""

from torch.nn.utils.rnn import pad_sequence
from torch.utils.data import Sampler
import torch

import random


def collate_batch(batch, text_transform, label_transform, padding_value=1, device="cpu"):
    """Collates batch of data. This function is passed to the DataLoader as the collate_fn argument.
    It will likely need to be inside a wrapper to pass additional arguments to the collate_fn.
    
    Args:
    - batch (iterable): batch of data 
    - text_transform (callable): text transform function
    - label_transform (callable): label transform function  
    - padding_value (int): padding value for text
    - device (str): device to send tensors to

    Returns
    - collated batch
    """
    text_list, label_list = [], []
    for (_text, _label) in batch:
        processed_text = torch.tensor(text_transform(_text))
        text_list.append(processed_text)
        label_list.append(label_transform(_label))
    return pad_sequence(text_list, padding_value=padding_value).to(device), torch.tensor(label_list).to(device)

class BatchSamplerSimilarLength(Sampler):
    """Batch sampler that pools indices with similar lengths together.
    This is especially useful for RNNs.
    """
    def __init__(self, dataset, batch_size, indices=None, shuffle=True):
        """Initializes the batch sampler.

        Args:
        - dataset (torch.utils.data.Dataset): dataset to sample from
        - batch_size (int): batch size
        - indices (list): indices to sample from
        - shuffle (bool): whether to shuffle indices
        """
        
        self.batch_size = batch_size
        self.shuffle = shuffle
        # get the indices and length
        self.indices = [(i, len(s[1])) for i, s in enumerate(dataset)]
        # if indices are passed, then use only the ones passed (for ddp)
        if indices is not None:
            self.indices = torch.tensor(self.indices)[indices].tolist()

    def __iter__(self):
        if self.shuffle:
            random.shuffle(self.indices)

        pooled_indices = []
        # create pool of indices with similar lengths
        for i in range(0, len(self.indices), self.batch_size * 100):
            pooled_indices.extend(sorted(self.indices[i:i + self.batch_size * 100], key=lambda x: x[1]))
        self.pooled_indices = [x[0] for x in pooled_indices]

        # yield indices for current batch
        batches = [self.pooled_indices[i:i + self.batch_size] for i in
               range(0, len(self.pooled_indices), self.batch_size)]

        if self.shuffle:
            random.shuffle(batches)
        for batch in batches:
            yield batch

    def __len__(self):
        return len(self.pooled_indices) // self.batch_size

