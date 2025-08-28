# GIMC Classifier

This directory contains the machine learning classifier components of the GIMC (Genetically Improved Malicious Code) project. The classifiers use Natural Language Processing (NLP) techniques to identify and classify malware families based on dynamic analysis reports.

## Overview

The classifier system employs multiple deep learning architectures to classify malware samples into different families:

- **AgentTesla** - Information stealer malware
- **RedLineStealer** - Credential theft malware  
- **RaccoonStealer** - Data theft malware
- **Benign** - Non-malicious samples

The system processes dynamic analysis reports as text and uses various neural network architectures to learn distinguishing patterns for classification.

## Project Structure

```
classifier/
├── models/                    # Neural network model implementations
│   ├── mlp_nlp.py            # Multi-Layer Perceptron for NLP
│   ├── cnn_nlp.py            # Convolutional Neural Network for NLP
│   ├── lstm.py               # Long Short-Term Memory network
│   └── transformer_classifier.py # BERT/Transformer-based classifier
├── utils/                     # Utility functions and helpers
│   ├── mal_data.py           # Data loading and preprocessing utilities
│   ├── train.py              # Training and evaluation functions
│   ├── batch.py              # Batch processing utilities
│   └── plot.py               # Visualization utilities
├── data-preprocessing.ipynb   # Data preprocessing and preparation
├── mlp4mal.ipynb             # MLP model training notebook
├── mlp4mal-test.ipynb        # MLP model testing and evaluation
├── cnn4mal.ipynb             # CNN model training notebook
├── lstm4mal.ipynb            # LSTM model training notebook
├── bert4mal.ipynb            # BERT/Transformer model training notebook
├── test-metrics.ipynb        # Model evaluation and metrics comparison
└── tokenizer-training.ipynb  # Custom tokenizer training
```

## Models

### 1. Multi-Layer Perceptron (MLP)
- **File**: `models/mlp_nlp.py`, `mlp4mal.ipynb`
- **Architecture**: Embedding layer + 3 fully connected layers with ReLU activation and dropout
- **Use Case**: Baseline model for text classification
- **Features**: Simple architecture, fast training, good interpretability

### 2. Convolutional Neural Network (CNN)
- **File**: `models/cnn_nlp.py`, `cnn4mal.ipynb`
- **Architecture**: 1D convolutions with multiple filter sizes for n-gram feature extraction
- **Use Case**: Capturing local patterns and n-gram features in text
- **Features**: Parallel convolutions, max pooling, effective for short text sequences

### 3. Long Short-Term Memory (LSTM)
- **File**: `models/lstm.py`, `lstm4mal.ipynb`
- **Architecture**: Bidirectional LSTM with attention mechanism
- **Use Case**: Sequential pattern recognition in longer text sequences
- **Features**: Handles variable-length sequences, captures long-term dependencies

### 4. BERT/Transformer
- **File**: `models/transformer_classifier.py`, `bert4mal.ipynb`
- **Architecture**: Transformer-based model with self-attention
- **Use Case**: State-of-the-art performance on text classification tasks
- **Features**: Pre-trained embeddings, attention mechanisms, transfer learning

## Getting Started

### Prerequisites

1. **Python Environment**: Python 3.8+ with required packages
```bash
pip install -r ../requirements.txt
```

2. **Configuration**: Create `../settings.json` with:
```json
{
    "data_path": "/path/to/your/data/",
    "sqlalchemy_database_uri": "your_database_connection_string"
}
```

3. **Database**: PostgreSQL database with malware analysis reports

### Data Preparation

1. **Data Preprocessing**:
   ```bash
   jupyter notebook data-preprocessing.ipynb
   ```
   - Loads malware reports from database
   - Preprocesses text data
   - Creates training/validation/test splits

2. **Tokenizer Training** (optional):
   ```bash
   jupyter notebook tokenizer-training.ipynb
   ```
   - Trains custom tokenizer on malware data
   - Creates vocabulary mappings

### Model Training

Train individual models using their respective notebooks:

```bash
# Multi-Layer Perceptron
jupyter notebook mlp4mal.ipynb

# Convolutional Neural Network
jupyter notebook cnn4mal.ipynb

# LSTM Network
jupyter notebook lstm4mal.ipynb

# BERT/Transformer
jupyter notebook bert4mal.ipynb
```

### Model Evaluation

```bash
# Comprehensive model testing and metrics
jupyter notebook test-metrics.ipynb

# Specific MLP testing
jupyter notebook mlp4mal-test.ipynb
```

## Key Features

### Data Processing
- **Custom Tokenization**: Specialized tokenizer for malware report text
- **Database Integration**: Direct loading from PostgreSQL database
- **Preprocessing Pipeline**: Text cleaning, normalization, and feature extraction

### Model Training
- **PyTorch Implementation**: All models built with PyTorch framework
- **GPU Support**: CUDA acceleration for faster training
- **Checkpointing**: Model state saving and loading
- **Hyperparameter Tuning**: Configurable model parameters

### Evaluation Metrics
- **Classification Accuracy**: Overall model performance
- **Precision/Recall/F1**: Per-class performance metrics
- **Confusion Matrices**: Detailed classification analysis
- **ROC Curves**: Binary classification performance

## Configuration Parameters

### Common Parameters
- `VOCABULARY_SIZE`: 20,000 (default tokenizer vocabulary size)
- `EMBEDDING_DIM`: 128 (word embedding dimensions)
- `BATCH_SIZE`: 32 (training batch size)
- `LEARNING_RATE`: 0.0001 (Adam optimizer learning rate)
- `DROPOUT`: 0.25 (dropout rate for regularization)

### Model-Specific Parameters
Each model has additional hyperparameters configurable in their respective notebooks.

## Data Flow

1. **Raw Reports** → Database storage of malware analysis reports
2. **Data Loading** → `utils/mal_data.py` extracts and preprocesses reports
3. **Tokenization** → Text converted to numerical sequences
4. **Model Training** → Neural networks learn classification patterns
5. **Evaluation** → Models tested on held-out data
6. **Inference** → Trained models classify new malware samples

## Performance Notes

- **Training Time**: Varies by model complexity (MLP < CNN < LSTM < BERT)
- **Memory Usage**: BERT requires most GPU memory, MLP requires least
- **Accuracy**: Generally BERT > LSTM > CNN > MLP (with proper tuning)
- **Inference Speed**: MLP fastest, BERT slowest for real-time classification

## Troubleshooting

### Common Issues

1. **CUDA Out of Memory**: Reduce batch size or use CPU training
2. **Database Connection**: Verify `settings.json` database URI
3. **Missing Data**: Ensure malware reports exist in database
4. **Import Errors**: Check that all required packages are installed

### Performance Optimization

- Use GPU acceleration when available
- Adjust batch size based on available memory
- Consider gradient accumulation for large models
- Use mixed precision training for faster convergence

## Contributing

When adding new models or features:
1. Follow the existing code structure and naming conventions
2. Add comprehensive documentation and comments
3. Include evaluation metrics in `test-metrics.ipynb`
4. Update this README with new model information

## Related Components

This classifier module integrates with other GIMC components:
- **Sandbox**: Provides dynamic analysis reports for training data
- **Genetic Improvement**: Uses classifier scores for fitness evaluation
- **Evaluation Server**: Serves trained models for real-time classification
