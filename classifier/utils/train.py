"""
Utility functions for training and evaluating neural networks.
"""

import time
import torch
import os

def compute_accuracy(model, data_loader, device):
    """Compute the accuracy over the mini-batch
    
    Args:
    - model: PyTorch neural network object
    - data_loader: PyTorch data loader object
    - device: device type
    
    Returns:
    - accuracy (float)
    """

    with torch.no_grad():

        correct_pred, num_examples = 0, 0

        for i, (features, targets) in enumerate(data_loader):

            features = features.to(device)
            targets = targets.to(device)

            logits = model(features)
            _, predicted_labels = torch.max(logits, 1)

            num_examples += targets.size(0)
            correct_pred += (predicted_labels == targets).sum().to("cpu")

    return float(correct_pred)/num_examples * 100


def train_model(model, num_epochs, train_loader,
                valid_loader, test_loader, optimizer,
                device, 
                loss_fn=torch.nn.CrossEntropyLoss(),
                logging_interval=50,
                scheduler=None,
                scheduler_on='valid_acc',
                checkpoint_prefix=None,
                resume_on_epoch=None,
                batch_size=None):

    """Train a neural network and return the train/test accuracies.

    Args:
    - model: PyTorch neural network object
    - num_epochs: total number of training epochs
    - train_loader: PyTorch DataLoader object for training data
    - valid_loader: PyTorch DataLoader object for validation data
    - test_loader: PyTorch DataLoader object for test data
    - optimizer: PyTorch optimizer object (defines the update rule)
    - device: device type
    - loss_fn: loss function for training
    - logging_interval: (int) frequency of minibatch logging
    - scheduler: PyTorch scheduler object
    - scheduler_on: (str) 'valid_acc' or 'minibatch_loss'
    """

    start_time = time.time()
    
    
    if checkpoint_prefix is not None:
        checkpoint_path = f'{checkpoint_prefix}_checkpoint.pth'
    else:
        checkpoint_path = None
    
    if os.path.exists(checkpoint_path):
        checkpoint = torch.load(checkpoint_path)
        if resume_on_epoch is not None:
            epoch = resume_on_epoch
        else:
            epoch = checkpoint['epoch']
        model.load_state_dict(checkpoint['model_states'][epoch])
        optimizer.load_state_dict(checkpoint['optimizer_states'][epoch])
        model_states = checkpoint['model_states'][:epoch+1]
        optimizer_states = checkpoint['optimizer_states'][:epoch]
        train_acc_list = checkpoint['train_acc_list'][:epoch]
        valid_acc_list = checkpoint['valid_acc_list'][:epoch]
        minibatch_loss_list = checkpoint['minibatch_loss_list'][:(epoch * batch_size)]
        print(f'Loaded checkpoint from {checkpoint_path}. Resume on epoch {epoch}')
    else:
        epoch = 0
        minibatch_loss_list = []
        train_acc_list = []
        valid_acc_list = []
        model_states = []
        optimizer_states = []
        print(f'No checkpoint found at {checkpoint_path}. Start training from scratch.')
    
    while epoch < num_epochs:

        model.train()
        for batch_idx, (features, targets) in enumerate(train_loader):

            features = features.to(device)
            targets = targets.to(device)

            # Zero previously calculated gradients
            model.zero_grad()

            # ## FORWARD AND BACK PROP
            logits = model(features)
            loss = loss_fn(logits, targets)

            loss.backward()

            # ## UPDATE MODEL PARAMETERS
            optimizer.step()

            # ## LOGGING
            minibatch_loss_list.append(loss.item())
            if not batch_idx % logging_interval:
                elapsed = (time.time() - start_time)/60
                print(f'Epoch: {epoch+1:03d}/{num_epochs:03d} '
                      f'| Batch {batch_idx:04d}/{len(train_loader):04d} '
                      f'| Loss: {loss:.4f} '
                      f'| Elapsed: {elapsed:.2f} min',  end="\r", flush=True)

        model.eval()
        with torch.no_grad():  # save memory during inference
            train_acc = compute_accuracy(model, train_loader, device=device)
            valid_acc = compute_accuracy(model, valid_loader, device=device)
            elapsed = (time.time() - start_time)/60
            print(f'Epoch: {epoch+1:03d}/{num_epochs:03d} '
                  f'| Train: {train_acc :.2f}% '
                  f'| Validation: {valid_acc :.2f}% '
                  f'| Elapsed: {elapsed:.2f} min')
            train_acc_list.append(train_acc)
            valid_acc_list.append(valid_acc)


        
        if scheduler is not None:

            if scheduler_on == 'valid_acc':
                scheduler.step(valid_acc_list[-1])
            elif scheduler_on == 'minibatch_loss':
                scheduler.step(minibatch_loss_list[-1])
            else:
                raise ValueError(f'Invalid `scheduler_on` choice.')
        
        # save model checkpoint
        if checkpoint_prefix is not None:
            # checkpoint_path = f'{checkpoint_prefix}_epoch_{epoch+1}.pth'
            checkpoint_path = f'{checkpoint_prefix}_checkpoint.pth'
            model_states.append(model.state_dict())
            optimizer_states.append(optimizer.state_dict())
            torch.save({'model_states': model_states, 
                        'optimizer_states': optimizer_states, 
                        'epoch': epoch, 
                        'train_acc_list': train_acc_list,
                        'valid_acc_list': valid_acc_list,
                        'minibatch_loss_list': minibatch_loss_list
                    }, checkpoint_path)
        epoch += 1
        
    elapsed = (time.time() - start_time)/60
    print(f'Total Training Time: {elapsed:.2f} min')
    if test_loader is not None:
        test_acc = compute_accuracy(model, test_loader, device=device)
        print(f'Test accuracy {test_acc :.2f}%')

    return minibatch_loss_list, train_acc_list, valid_acc_list
