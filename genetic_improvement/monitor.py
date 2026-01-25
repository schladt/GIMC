"""
ES Monitor for GI Evaluation Server
- Monitors completed sandbox analyses and performs ML classification
- Manages build VM timeouts and resets
"""

import asyncio
import argparse
import logging
import json
import os
import sys
import time
import re
import torch
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from transformers import AutoTokenizer

from classifier.models.cnn_nlp import CNN_NLP
from classifier.utils.mal_data import get_mal_data
from models import Candidate, Analysis, Sample, Tag
from .config import Config

# set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

###################################
# Configuration
###################################

# Global variables for model and tokenizer
MODEL = None
TOKENIZER = None
MAX_SEQUENCE_LENGTH = 20480 * 2
DEVICE = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
SIGNATURES = None  # Class labels list

# ES Database session
ES_SESSION = None

# Sandbox Database session (for Analysis table)
SANDBOX_SESSION = None

###################################
# Initialization
###################################

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='ES Monitor for classification and VM management')
    parser.add_argument('--classifier', required=True, help='Path to classifier checkpoint file')
    parser.add_argument('--tokenizer', required=True, help='Path to tokenizer directory')
    parser.add_argument('--signatures', required=True, help='Comma-separated list of class labels (e.g., "wmi,com,cmd,benign")')
    parser.add_argument('--vocab-size', type=int, default=20000, help='Vocabulary size')
    parser.add_argument('--embed-dim', type=int, default=128, help='Embedding dimension')
    parser.add_argument('--num-classes', type=int, default=4, help='Number of classes')
    parser.add_argument('--dropout', type=float, default=0.5, help='Dropout rate')
    parser.add_argument('--poll-interval', type=int, default=10, help='Poll interval in seconds')
    
    return parser.parse_args()

def load_model_and_tokenizer(classifier_path, tokenizer_path, vocab_size, embed_dim, num_classes, dropout):
    """Load and initialize the classifier model and tokenizer"""
    global MODEL, TOKENIZER, DEVICE
    
    logging.info(f"Loading tokenizer from {tokenizer_path}")
    TOKENIZER = AutoTokenizer.from_pretrained(tokenizer_path)
    TOKENIZER.pad_token = "[PAD]"
    TOKENIZER.cls_token = "[CLS]"
    TOKENIZER.sep_token = "[SEP]"
    
    logging.info(f"Loading classifier from {classifier_path}")
    MODEL = CNN_NLP(
        pretrained_embedding=None,
        freeze_embedding=False,
        vocab_size=vocab_size,
        embed_dim=embed_dim,
        filter_sizes=[3, 4, 5],
        num_filters=[10, 10, 10],
        num_classes=num_classes,
        dropout=dropout
    )
    
    # Load checkpoint
    checkpoint = torch.load(classifier_path, map_location=DEVICE)
    MODEL.load_state_dict(checkpoint['model_states'][-1])
    MODEL.to(DEVICE)
    MODEL.eval()
    
    logging.info(f"Model loaded successfully on {DEVICE}")

def init_databases():
    """Initialize database connections"""
    global ES_SESSION, SANDBOX_SESSION
    
    # Load settings
    settings_file = os.path.join(os.path.dirname(__file__), '..', 'settings.json')
    with open(settings_file) as f:
        settings = json.load(f)
    
    # ES Database (for Candidate table)
    es_engine = create_engine(settings['sqlalchemy_database_uri'], echo=False)
    ESSession = sessionmaker(bind=es_engine)
    ES_SESSION = ESSession()
    
    # Sandbox Database (for Analysis table) - same database, different tables
    sandbox_engine = create_engine(settings['sqlalchemy_database_uri'], echo=False)
    SandboxSession = sessionmaker(bind=sandbox_engine)
    SANDBOX_SESSION = SandboxSession()
    
    logging.info("Database connections initialized")

###################################
# Report Preprocessing
###################################

def mal_tokenizer(line):
    """
    Tokenize a line of text
    """
    line = line.lower()
    line = line.replace(',', ' ')
    line = line.replace('\\', ' ')
    line = line.replace('\\\\', ' ')
    return line.split()

def preprocess_report(report_text):
    """
    Preprocess a single report for classification.
    Extracts dynamic report data and tokenizes it.
    
    Args:
        report_text: Raw JSON report text
    
    Returns:
        Preprocessed text string ready for tokenization
    """
    try:
        # Parse JSON report
        report = json.loads(report_text)
        
        # Extract dynamic report section
        dynamic_report_tokenized = []
        
        if 'dynamic' in report:
            for item in report['dynamic']:
                line = f"{item['Operation']}, {item['Path']}, {item['Result']}"
                dynamic_report_tokenized.extend(mal_tokenizer(line))
        
        # Join words into text
        text = " ".join(dynamic_report_tokenized)
        
        return text
    
    except Exception as e:
        logging.error(f"Error preprocessing report: {e}")
        return ""

###################################
# Classification
###################################

def classify_report(report_text, target_class):
    """
    Classify a preprocessed report and return F3 score.
    
    Args:
        report_text: Preprocessed report text
        target_class: Integer index of target class
    
    Returns:
        F3 score (probability of target class)
    """
    try:
        # Tokenize
        inputs = TOKENIZER(
            report_text,
            padding='max_length',
            truncation=True,
            max_length=MAX_SEQUENCE_LENGTH,
            return_tensors='pt'
        ).to(DEVICE)
        
        input_ids = inputs['input_ids']
        
        # Run inference
        with torch.no_grad():
            logits = MODEL(input_ids)
            # Apply softmax to get probabilities
            probs = torch.nn.functional.softmax(logits, dim=-1)
            
            # Get probability for target class
            F3 = probs[0][target_class].item()
        
        return F3
    
    except Exception as e:
        logging.error(f"Error classifying report: {e}")
        return 0.0

###################################
# Analysis Processing
###################################

def process_completed_analysis(candidate):
    """
    Process a candidate with completed analysis.
    
    Args:
        candidate: Candidate object with status=2 and completed analysis
    """
    try:
        logging.info(f"Processing candidate {candidate.hash} with analysis {candidate.analysis_id}")
        
        # Get analysis from sandbox database
        analysis = SANDBOX_SESSION.query(Analysis).filter_by(id=candidate.analysis_id).first()
        
        if not analysis:
            logging.error(f"Analysis {candidate.analysis_id} not found")
            candidate.status = 4
            candidate.F3 = 0
            candidate.error_message = "Analysis not found"
            ES_SESSION.commit()
            return
        
        # Check if analysis had an error (status=3)
        if analysis.status == 3:
            logging.warning(f"Analysis {candidate.analysis_id} failed with error")
            candidate.F3 = 0.0
            candidate.status = 3  # complete
            candidate.error_message = f"Analysis error: {analysis.error_message or 'Unknown error'}"
            ES_SESSION.commit()
            return
        
        # Check if analysis is complete (status=2)
        if analysis.status != 2:
            # Not complete yet (status=0 pending or status=1 running)
            logging.info(f"Analysis {candidate.analysis_id} not complete yet (status={analysis.status})")
            return
        
        # Get classification to determine target class
        classification = candidate.classification
        if not classification:
            logging.error(f"No classification found for candidate {candidate.hash}")
            candidate.status = 4
            candidate.F3 = 0
            candidate.error_message = "No classification found"
            ES_SESSION.commit()
            return
        
        # Map classification to index using global SIGNATURES list
        try:
            target_class = SIGNATURES.index(classification)
        except ValueError:
            logging.error(f"Unknown classification: {classification}. Expected one of {SIGNATURES}")
            candidate.status = 4
            candidate.F3 = 0
            candidate.error_message = f"Unknown classification: {classification}"
            ES_SESSION.commit()
            return
        
        # Read report file
        if not os.path.exists(analysis.report):
            logging.error(f"Report file not found: {analysis.report}")
            candidate.status = 4
            candidate.F3 = 0
            candidate.error_message = "Report file not found"
            ES_SESSION.commit()
            return
        
        with open(analysis.report, 'r') as f:
            report_json = f.read()
        
        # Preprocess report
        preprocessed_text = preprocess_report(report_json)
        
        if not preprocessed_text:
            logging.error(f"Failed to preprocess report for candidate {candidate.hash}")
            candidate.status = 4
            candidate.F3 = 0
            candidate.error_message = "Failed to preprocess report"
            ES_SESSION.commit()
            return
        
        # Classify report
        F3 = classify_report(preprocessed_text, target_class)
        
        logging.info(f"Candidate {candidate.hash} classified with F3={F3:.4f} for class {classification}")
        
        # Update candidate
        candidate.F3 = F3
        candidate.status = 3  # complete
        ES_SESSION.commit()
        
    except Exception as e:
        logging.error(f"Error processing completed analysis: {e}")
        candidate.status = 4
        candidate.F3 = 0
        candidate.error_message = f"Classification error: {str(e)}"
        ES_SESSION.commit()

###################################
# VM Management
###################################

async def check_build_vm_timeouts(config):
    """
    Check for build VM timeouts and reset stuck VMs.
    Similar to sandbox monitor but for build VMs.
    """
    try:
        # Get all candidates currently building (status=1)
        candidates = ES_SESSION.query(Candidate).filter(Candidate.status == 1).all()
        
        for candidate in candidates:
            ES_SESSION.commit()  # refresh date_updated
            ES_SESSION.refresh(candidate)
            
            if candidate.status != 1:
                continue
            
            # Check timeout
            current_time = ES_SESSION.query(sqlalchemy.func.current_timestamp()).scalar()
            current_time = current_time.replace(tzinfo=None)
            last_updated = candidate.date_updated.replace(tzinfo=None)
            time_diff = (current_time - last_updated).total_seconds()
            
            logging.info(f"Candidate {candidate.hash}: time difference = {time_diff}s")
            
            if time_diff > config.VM_TIMEOUT:
                logging.warning(f"Candidate {candidate.hash} on VM {candidate.build_vm} timed out")
                
                # Set status to error
                candidate.status = 4
                candidate.error_message = "Build VM timeout"
                ES_SESSION.add(candidate)
                ES_SESSION.commit()
                
                # Reset VM
                if candidate.build_vm:
                    await reset_build_vm(candidate.build_vm, config)
    
    except Exception as e:
        logging.error(f"Error checking build VM timeouts: {e}")

async def reset_build_vm(vm_name, config):
    """
    Reset a build VM to snapshot.
    
    Args:
        vm_name: Name of VM to reset
        config: Config object with VM settings
    """
    try:
        # Import VM management functions based on provider
        from sandbox.monitor import vmware_linux_reset_snapshot, vmware_linux_start_vm
        from sandbox.monitor import virsh_reset_snapshot, virsh_start_vm
        
        vm_provider = config.VM_PROVIDER
        
        if vm_provider == 'vmware':
            reset_snapshot = vmware_linux_reset_snapshot
            start_vm = vmware_linux_start_vm
        elif vm_provider == 'libvirt':
            reset_snapshot = virsh_reset_snapshot
            start_vm = virsh_start_vm
        else:
            logging.error(f"Unknown VM provider: {vm_provider}")
            return
        
        # Get snapshot name
        snapshot = None
        for vm in config.VMS:
            if vm['name'] == vm_name:
                snapshot = vm['snapshot']
                break
        
        if not snapshot:
            logging.error(f"Snapshot not found for VM {vm_name}")
            return
        
        # Reset VM
        logging.info(f"Resetting VM {vm_name} to snapshot {snapshot}")
        await reset_snapshot(vm_name, snapshot)
        
        logging.info(f"VM {vm_name} reset successfully")
    
    except Exception as e:
        logging.error(f"Error resetting build VM {vm_name}: {e}")

###################################
# Main Loop
###################################

async def main_loop(config, poll_interval):
    """
    Main monitoring loop.
    
    Args:
        config: Config object
        poll_interval: Seconds between polls
    """
    logging.info("ES Monitor starting main loop")
    
    while True:
        try:
            # Clear session cache to get fresh data
            ES_SESSION.expire_all()
            SANDBOX_SESSION.expire_all()
            
            # Check for build VM timeouts
            await check_build_vm_timeouts(config)
            
            # Check for completed analyses to classify
            candidates_analyzing = ES_SESSION.query(Candidate).filter(Candidate.status == 2).all()
            
            for candidate in candidates_analyzing:
                process_completed_analysis(candidate)

            if not candidates_analyzing:
                logging.debug("No candidates with completed analyses to process")

            # Sleep before next poll
            await asyncio.sleep(poll_interval)
        
        except KeyboardInterrupt:
            logging.info("ES Monitor stopped by user")
            break
        
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            await asyncio.sleep(poll_interval)

###################################
# VM Initialization
###################################

async def initialize_vms(config):
    """
    Initialize build VMs by resetting to snapshots and starting them.
    
    Args:
        config: Config object with VM settings
    """
    # Import VM management functions based on provider
    from sandbox.monitor import vmware_linux_reset_snapshot, vmware_linux_start_vm
    from sandbox.monitor import virsh_reset_snapshot, virsh_start_vm
    
    vm_provider = config.VM_PROVIDER
    
    if vm_provider == 'vmware':
        reset_snapshot = vmware_linux_reset_snapshot
        start_vm = vmware_linux_start_vm
    elif vm_provider == 'libvirt':
        reset_snapshot = virsh_reset_snapshot
        start_vm = virsh_start_vm
    else:
        logging.error(f"Unknown VM provider: {vm_provider}")
        return
    
    # Get VMs from config
    vms = config.VMS
    
    logging.info(f"Initializing {len(vms)} build VMs...")
    
    # Reset all VMs to snapshot
    logging.info("Resetting VMs to snapshots...")
    list_of_tasks = [reset_snapshot(vm['name'], vm['snapshot']) for vm in vms]
    await asyncio.gather(*list_of_tasks)
    
    # Start all VMs
    logging.info("Starting VMs...")
    list_of_tasks = [start_vm(vm['name']) for vm in vms]
    await asyncio.gather(*list_of_tasks)
    
    logging.info("All build VMs initialized and ready")

###################################
# Entry Point
###################################

async def main():
    """Main entry point"""
    global SIGNATURES
    
    # Parse arguments
    args = parse_args()
    
    # Parse signatures list
    SIGNATURES = [s.strip() for s in args.signatures.split(',')]
    logging.info(f"Class signatures: {SIGNATURES}")
    
    # Load model and tokenizer
    load_model_and_tokenizer(
        args.classifier,
        args.tokenizer,
        args.vocab_size,
        args.embed_dim,
        args.num_classes,
        args.dropout
    )
    
    # Initialize databases
    init_databases()
    
    # Load config
    config = Config()
    
    # Initialize build VMs
    await initialize_vms(config)
    
    # Start main loop
    await main_loop(config, args.poll_interval)

if __name__ == '__main__':
    asyncio.run(main())
