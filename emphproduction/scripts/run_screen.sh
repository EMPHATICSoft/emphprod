#!/bin/bash

# Script to run prodmc_r2408.py in a screen session (assumes already in sl7 container)
# Usage: ./run_screen.sh [screen_name] [python_script_args...]
# Usage: ./run_screen.sh --help (to show Python script options)

# Show help if requested
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    echo "Production runner script - runs prodmc_r2408.py in screen session"
    echo ""
    echo "Usage: $0 [screen_name] [python_script_args...]"
    echo "       $0 --help"
    echo ""
    echo "If screen_name is not provided, uses 'emphatic_prod'"
    echo ""
    echo "Python script options:"
    python3 ./prodmc_r2408.py --help
    exit 0
fi

# Check if first argument looks like a screen name (doesn't start with -)
if [[ "$1" != -* ]] && [[ $# -gt 1 ]]; then
    SCREEN_NAME="$1"
    shift
else
    SCREEN_NAME="emphatic_prod"
fi

CURRENT_DIR=$(pwd)
SETUP_SCRIPT="/exp/emph/app/users/gsdavies/prod6/emphaticsoft/setup/setup_emphatic.sh"
BUILD_DIR="/exp/emph/app/users/gsdavies/prod6/build"

# Create timestamped log file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$CURRENT_DIR/production_${TIMESTAMP}.log"

echo "Starting production job in screen session: $SCREEN_NAME"
echo "Current directory: $CURRENT_DIR" 
echo "Python script args: $@"
echo "Log file: $LOG_FILE"

# Create a temporary script to run inside the container
cat > container_script.sh << SCRIPT_EOF
#!/bin/bash
echo "Setting up EMPHATICSoft environment in container..." | tee -a $LOG_FILE
source $SETUP_SCRIPT
cd $BUILD_DIR
source ../emphaticsoft/ups/setup_for_development -p
echo "Environment setup complete, changing to work directory..." | tee -a $LOG_FILE
cd $CURRENT_DIR
echo "Starting Python script at \$(date)..." | tee -a $LOG_FILE
python3 -u ./prodmc_r2408.py $@ 2>&1 | tee -a $LOG_FILE
echo "Python script completed at \$(date)" | tee -a $LOG_FILE
echo "Log saved to: $LOG_FILE" | tee -a $LOG_FILE
echo "Press any key to exit screen session..."
read -n 1
SCRIPT_EOF

chmod +x container_script.sh

# Create screen session and run the job using sl7-emph properly
screen -dmS "$SCREEN_NAME" bash -c "
    cd '$CURRENT_DIR'
    echo 'Setting up EMPHATICSoft environment...'
    source '$SETUP_SCRIPT'
    echo 'Entering SL7 container environment...'
    sl7-emph -- bash ./container_script.sh
    rm -f ./container_script.sh
"

echo "Screen session '$SCREEN_NAME' started"
echo "Log file: $LOG_FILE"
echo "To attach: screen -r $SCREEN_NAME"
echo "To detach: Ctrl+A, then D"
echo "To list sessions: screen -ls"
echo "To kill session: screen -S $SCREEN_NAME -X quit"
echo "To monitor progress: tail -f $LOG_FILE"