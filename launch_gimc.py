#!/usr/bin/env python3
"""
GIMC System Launcher
Starts all GIMC services with colored output
"""
import subprocess
import sys
import threading
import signal
import time
import json
import os

# Load settings
project_root = os.path.dirname(os.path.abspath(__file__))
settings_file = os.path.join(project_root, 'settings.json')
with open(settings_file) as f:
    settings = json.load(f)

launcher_config = settings.get('launcher', {})

# ANSI color codes
COLORS = {
    'eval_server': '\033[92m',    # Green
    'es_monitor': '\033[94m',     # Blue
    'sandbox_server': '\033[93m', # Yellow
    'sandbox_monitor': '\033[95m', # Magenta
    'reset': '\033[0m'
}

# Service configurations - build from settings.json
SERVICES = {
    'eval_server': {
        'cmd': ['python', '-m', 'genetic_improvement.evaluation_server',
                launcher_config['eval_server']['interface'],
                launcher_config['eval_server']['port']],
        'color': COLORS['eval_server'],
        'label': '[EVAL-SERVER]'
    },
    'es_monitor': {
        'cmd': ['python', '-m', 'genetic_improvement.monitor',
                '--classifier', launcher_config['es_monitor']['classifier'],
                '--tokenizer', launcher_config['es_monitor']['tokenizer'],
                '--signatures', launcher_config['es_monitor']['signatures']],
        'color': COLORS['es_monitor'],
        'label': '[ES-MONITOR]'
    },
    'sandbox_server': {
        'cmd': ['python', '-m', 'sandbox.sandbox_server',
                launcher_config['sandbox_server']['interface'],
                launcher_config['sandbox_server']['port']],
        'color': COLORS['sandbox_server'],
        'label': '[SANDBOX-SERVER]'
    },
    'sandbox_monitor': {
        'cmd': ['python', '-m', 'sandbox.monitor'],
        'color': COLORS['sandbox_monitor'],
        'label': '[SANDBOX-MONITOR]'
    }
}

processes = {}
running = True

def stream_output(process, name, color, label):
    """Stream process output with color prefix"""
    reset = COLORS['reset']
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                decoded_line = line.rstrip()
                print(f"{color}{label}{reset} {decoded_line}", flush=True)
    except Exception as e:
        print(f"{color}{label}{reset} Error reading output: {e}", flush=True)

def start_service(name, config):
    """Start a service process"""
    print(f"{config['color']}{config['label']}{COLORS['reset']} Starting...")
    try:
        process = subprocess.Popen(
            config['cmd'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        processes[name] = process
        
        # Start thread to read output
        thread = threading.Thread(
            target=stream_output,
            args=(process, name, config['color'], config['label']),
            daemon=True
        )
        thread.start()
        
        return process
    except Exception as e:
        print(f"{config['color']}{config['label']}{COLORS['reset']} Failed to start: {e}", flush=True)
        return None

def shutdown_handler(signum, frame):
    """Handle shutdown signals"""
    global running
    running = False
    print(f"\n{COLORS['reset']}Shutting down all services...")
    
    for name, process in processes.items():
        if process and process.poll() is None:
            config = SERVICES[name]
            print(f"{config['color']}{config['label']}{COLORS['reset']} Terminating...")
            process.terminate()
    
    # Wait for processes to terminate
    time.sleep(2)
    
    # Force kill if still running
    for name, process in processes.items():
        if process and process.poll() is None:
            config = SERVICES[name]
            print(f"{config['color']}{config['label']}{COLORS['reset']} Force killing...")
            process.kill()
    
    print(f"{COLORS['reset']}All services stopped.")
    sys.exit(0)

def main():
    """Main launcher"""
    print(f"{COLORS['reset']}╔═══════════════════════════════════════╗")
    print("║     GIMC System Launcher v1.0        ║")
    print("╚═══════════════════════════════════════╝")
    print()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    # Start all services
    for name, config in SERVICES.items():
        start_service(name, config)
        time.sleep(0.5)  # Small delay between starts
    
    print(f"\n{COLORS['reset']}All services started. Press Ctrl+C to stop all.\n")
    
    # Monitor processes
    try:
        while running:
            time.sleep(1)
            # Check if any process died
            for name, process in list(processes.items()):
                if process.poll() is not None:
                    config = SERVICES[name]
                    print(f"{config['color']}{config['label']}{COLORS['reset']} Process exited with code {process.returncode}")
                    # Optionally restart here
                    
    except KeyboardInterrupt:
        shutdown_handler(None, None)

if __name__ == '__main__':
    main()
