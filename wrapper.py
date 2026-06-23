import sys
import os
import yaml
import subprocess
from datetime import datetime

def write_to_event_log(code, message):
    print(f"[EVENT - {code}] {message}")

def write_to_error_log(code, message):
    print(f"[ERROR - {code}] {message}", file=sys.stderr)

def main():
    # 1. Accept initial args
    raw_date = sys.argv[1] # e.g., CYLC_TASK_CYCLE_POINT
    task_name = sys.argv[2]
    config_path = sys.argv[3]
    
    # Parse date (assuming YYYYMMDDHH format from Cylc)
    # date = raw_date[:10].replace("T", "") # Adjust based on actual string format
    date = raw_date 
    
    # 2. Access config file
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
        
    python_libs = config['environment']['python']['load_these_libraries']
    python_path = config['environment']['python']['path']
    
    task_config = config['tasks'][task_name.replace(" ", "_")]
    script_path = task_config['script_path']
    script_name = task_config['script_name']
    arguments = task_config['args_to_pass']
    
    write_to_event_log("INIT", f"configs loaded for {task_name} on {date}")

    # 3. Handle Python Libraries (e.g., via pip or system loading)
    try:
        # Example of installing missing libraries (if actually installing at runtime)
        # In an HPC environment, this might be loading modules instead
        for lib in python_libs:
            subprocess.check_call([python_path, "-m", "pip", "install", lib])
        write_to_event_log("ENV", "libraries installed/loaded")
    except subprocess.CalledProcessError as e:
        write_to_error_log("ENV", f"libraries failed install: {e}")
        sys.exit(1)

    # 4. Construct and Execute Command
    # E.g.: /path/to/python /path/to/script/script.py arg1 arg2
    command = [python_path, os.path.join(script_path, script_name)] + arguments
    
    try:
        write_to_event_log("EXEC", f"Running command: {' '.join(command)}")
        # Run the command and wait for it to complete
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        write_to_event_log("SUCCESS", f"{task_name} on {date} successfully executed.")
        
    except subprocess.CalledProcessError as e:
        # Retrieve the log location exported by Cylc in Section 1
        error_log_location = os.environ.get('ERROR_LOG_LOCATION', 'UNKNOWN_DIR')
        
        write_to_error_log("FAIL", f"{task_name} on {date} FAILED to execute.")
        write_to_error_log("FAIL", f"Error output: {e.stderr}")
        write_to_error_log("FAIL", f"Check full logs for {task_name} on {date} at: {error_log_location}")
        sys.exit(1)

if __name__ == "__main__":
    main()
