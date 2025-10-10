# GIMC Classifier: Malware Family Classification Using NLP Techniques

## Overview

The GIMC Classifier is an advanced machine learning system that applies Natural Language Processing (NLP) techniques to classify malware families based on dynamic analysis reports. This system represents a novel approach to malware classification by treating dynamic analysis data as natural language text and applying state-of-the-art NLP models for family identification.

### Research Context

This classifier is part of the GIMC (Genetically Improved Malicious Code) project, which explores the intersection of cybersecurity and machine learning. The research demonstrates that dynamic analysis reports, when processed as text, contain rich behavioral patterns that can be effectively leveraged for malware family classification using transformer-based and traditional neural network architectures.

### Target Malware Families

The classifier framework demonstrates its capabilities using representative malware families selected for the research implementation. The NLP-based classification approach is designed to be extensible and can be adapted to classify any malware families for which sufficient dynamic analysis training data is available. The methodology generalizes to broader malware classification tasks beyond these specific examples.

The current implementation is trained to identify four categories:
- **AgentTesla** - Information stealer malware family
- **RedLineStealer** - Credential and data theft malware
- **RaccoonStealer** - Multi-purpose data exfiltration malware
- **Benign** - Non-malicious samples for binary classification scenarios

The choice of these particular families demonstrates the system's capability across different malware types (information stealers, credential harvesters, and data exfiltration tools).

## Architecture Overview

The system employs multiple complementary neural network architectures, each designed to capture different aspects of malware behavior patterns in dynamic analysis reports:

### 1. Multi-Layer Perceptron (MLP) - `mlp4mal.ipynb`
- **Architecture**: Embedding layer + 3 fully connected layers with ReLU activation
- **Strengths**: Fast training, good baseline performance, interpretable
- **Use Case**: Rapid classification and baseline comparison
- **Implementation**: `models/mlp_nlp.py`

### 2. Convolutional Neural Network (CNN) - `cnn4mal.ipynb`
- **Architecture**: 1D convolutions with multiple filter sizes (3, 4, 5) for n-gram extraction
- **Strengths**: Captures local patterns and n-gram features effectively
- **Use Case**: Detecting specific behavioral signatures in reports
- **Implementation**: `models/cnn_nlp.py`

### 3. Long Short-Term Memory (LSTM) - `lstm4mal.ipynb`
- **Architecture**: Bidirectional LSTM with attention mechanism
- **Strengths**: Handles sequential dependencies and variable-length sequences
- **Use Case**: Learning temporal patterns in malware execution traces
- **Implementation**: `models/lstm.py`

### 4. Transformer/BERT - `bert4mal.ipynb`
- **Architecture**: Multi-head self-attention with positional encoding
- **Strengths**: State-of-the-art performance, captures long-range dependencies
- **Use Case**: Complex behavioral pattern recognition and classification
- **Implementation**: `models/transformer_classifier.py`

## Data Pipeline

### 1. Data Source and Preprocessing - `data-preprocessing.ipynb`
- **Input**: Dynamic analysis reports from GIMC sandbox system
- **Database**: PostgreSQL with malware analysis reports and metadata
- **Processing**: Text extraction, normalization, and tokenization
- **Output**: Structured datasets for model training

### 2. Tokenization - `tokenizer-training.ipynb`
- **Custom Tokenizer**: Specialized for malware analysis terminology
- **Vocabulary**: 20,000 tokens optimized for dynamic analysis reports
- **Features**: Handles API calls, file paths, registry keys, and network artifacts

### 3. Feature Engineering - `utils/mal_data.py`
- **Text Processing**: Cleaning, normalization, and sequence preparation
- **Data Loading**: Direct integration with PostgreSQL database
- **Batch Processing**: Efficient handling of large datasets

## Model Training and Evaluation

### Training Configuration
```python
VOCABULARY_SIZE = 20000      # Custom tokenizer vocabulary
EMBEDDING_DIM = 128          # Word embedding dimensions  
BATCH_SIZE = 32              # Training batch size
LEARNING_RATE = 0.0001       # Adam optimizer learning rate
DROPOUT = 0.25               # Regularization rate
MAX_LENGTH = 40960           # Maximum sequence length
NUM_CLASSES = 4              # Malware families + benign
```

### Training Process - `utils/train.py`
- **Framework**: PyTorch with CUDA acceleration
- **Optimization**: Adam optimizer with learning rate scheduling
- **Regularization**: Dropout, weight decay, early stopping
- **Checkpointing**: Model state saving and loading
- **Evaluation**: Comprehensive metrics and validation

### Performance Evaluation - `test-metrics.ipynb`
- **Metrics**: Accuracy, Precision, Recall, F1-score per class
- **Visualization**: Confusion matrices, ROC curves, training curves
- **Comparison**: Cross-model performance analysis
- **Testing**: Held-out test set evaluation

## Key Features

### Advanced NLP Techniques
- **Custom Tokenization**: Domain-specific vocabulary for malware analysis
- **Sequence Processing**: Variable-length input handling
- **Attention Mechanisms**: Focus on relevant behavioral patterns
- **Transfer Learning**: Pre-trained embeddings where applicable

### Database Integration
- **Direct Loading**: PostgreSQL integration via `utils/mal_data.py`
- **Metadata Support**: Sample tags, analysis timestamps, provenance
- **Scalable Processing**: Efficient batch loading and caching

### Model Management
- **Checkpointing**: Automatic model saving and resumption
- **Hyperparameter Tuning**: Configurable architecture parameters
- **Performance Tracking**: Training metrics and validation curves
- **Model Comparison**: Side-by-side architecture evaluation

## Project Structure

```
classifier/
├── README.md                   # This documentation
├── data-preprocessing.ipynb    # Data loading and preprocessing pipeline
├── tokenizer-training.ipynb    # Custom tokenizer training
├── mlp4mal.ipynb              # MLP model training and evaluation
├── mlp4mal-test.ipynb         # MLP model testing
├── cnn4mal.ipynb              # CNN model training and evaluation  
├── lstm4mal.ipynb             # LSTM model training and evaluation
├── bert4mal.ipynb             # Transformer model training and evaluation
├── test-metrics.ipynb         # Comprehensive model comparison
├── models/                    # Neural network implementations
│   ├── mlp_nlp.py            # Multi-Layer Perceptron
│   ├── cnn_nlp.py            # Convolutional Neural Network
│   ├── lstm.py               # LSTM with attention
│   └── transformer_classifier.py # Transformer/BERT model
└── utils/                     # Supporting utilities
    ├── mal_data.py           # Data loading and preprocessing
    ├── train.py              # Training and evaluation functions
    ├── batch.py              # Batch processing utilities
    └── plot.py               # Visualization utilities
```

## Getting Started

### Prerequisites

1. **Environment Setup**:
```bash
pip install torch torchvision
pip install transformers tokenizers
pip install numpy pandas matplotlib seaborn
pip install tqdm scikit-learn
pip install psycopg2-binary sqlalchemy
```

2. **Configuration** - Create `../settings.json`:
```json
{
    "data_path": "/path/to/data/storage/",
    "sqlalchemy_database_uri": "postgresql://user:pass@host:port/db"
}
```

3. **Database Setup**:
   - PostgreSQL with malware analysis reports
   - Tables: `sample`, `analysis`, `tag`, `sample_tag`
   - Report data stored as JSON or text fields

### Quick Start

1. **Data Preparation**:
```bash
jupyter notebook data-preprocessing.ipynb
```

2. **Train a Model** (e.g., MLP):
```bash
jupyter notebook mlp4mal.ipynb
```

3. **Evaluate Performance**:
```bash
jupyter notebook test-metrics.ipynb
```

### Training Custom Models

Each model can be trained independently with configurable hyperparameters:

```python
# Example MLP configuration
VOCABULARY_SIZE = 20000
EMBEDDING_DIM = 128
HIDDEN_SIZES = [512, 256, 128]
DROPOUT = 0.25
LEARNING_RATE = 0.0001
BATCH_SIZE = 32
NUM_EPOCHS = 15
```

## Performance Characteristics

### Model Comparison
- **Speed**: MLP > CNN > LSTM > Transformer
- **Memory**: MLP < CNN < LSTM < Transformer  
- **Accuracy**: Generally Transformer > LSTM > CNN > MLP
- **Interpretability**: MLP > CNN > LSTM > Transformer

### Scalability
- **Training Time**: Varies by model complexity and dataset size
- **GPU Requirements**: Transformer models benefit most from GPU acceleration
- **Data Size**: System scales to millions of samples with proper batching

## Integration with GIMC System

### Sandbox Integration
- **Input Source**: Dynamic analysis reports from GIMC sandbox
- **Real-time Classification**: Models can classify new samples as they're analyzed
- **Feedback Loop**: Classification results inform genetic improvement process

### Genetic Improvement Integration
- **Fitness Evaluation**: Classifier scores guide genetic algorithm optimization
- **Variant Analysis**: Compare classification before/after genetic modifications
- **Evolution Metrics**: Track classification changes across generations

## Research Applications

### Malware Analysis
- **Family Identification**: Automated malware family labeling
- **Behavioral Clustering**: Group samples by behavioral similarity
- **Variant Detection**: Identify new variants of known families

### Security Research
- **Pattern Discovery**: Identify novel behavioral patterns
- **Evasion Analysis**: Study how malware evades detection
- **Attribution**: Support malware attribution and campaign tracking

## Troubleshooting

### Common Issues

1. **CUDA Out of Memory**:
   - Reduce `BATCH_SIZE` 
   - Use gradient accumulation
   - Enable mixed precision training

2. **Database Connection Errors**:
   - Verify `settings.json` configuration
   - Check PostgreSQL connectivity
   - Ensure required tables exist

3. **Tokenization Issues**:
   - Retrain tokenizer with current dataset
   - Adjust vocabulary size for your data
   - Handle out-of-vocabulary tokens

### Performance Optimization

- **Hardware**: Use GPU acceleration when available
- **Data Loading**: Implement efficient data pipelines
- **Model Selection**: Choose appropriate architecture for your use case
- **Hyperparameter Tuning**: Use grid search or automated optimization

## Contributing

When extending the classifier system:

1. **Follow Naming Conventions**: Use consistent model and file naming
2. **Add Documentation**: Include detailed docstrings and comments  
3. **Update Metrics**: Add new models to `test-metrics.ipynb`
4. **Test Thoroughly**: Validate on held-out test sets
5. **Share Results**: Document performance comparisons

## Related Research

This classifier supports research in:
- **Malware Classification**: NLP approaches to malware analysis
- **Behavioral Analysis**: Dynamic analysis report processing
- **Genetic Improvement**: Automated malware variant generation
- **Cybersecurity AI**: Machine learning for threat detection

## Citation

If you use this classifier in your research, please cite the GIMC project and related publications on NLP-based malware classification techniques.
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
