#!/bin/bash

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to set up Python virtual environment
setup_venv() {
    local venv_path="$1"
    if [ ! -d "$venv_path" ]; then
        echo "Creating Python virtual environment at $venv_path..."
        python3 -m venv "$venv_path"
        source "$venv_path/bin/activate"
        echo "Installing Python dependencies..."
        pip install -r "$(dirname "$venv_path")/requirements.txt"
        deactivate
        echo "Virtual environment setup complete."
    else
        echo "Python virtual environment already exists at $venv_path."
    fi
}

# Check for required package managers
if ! command_exists pnpm; then
    echo "pnpm is not installed. Installing globally..."
    npm install -g pnpm
fi

# Set up Python virtual environment for twitter-scraper
setup_venv "/home/trendpup/TrendPup/twitter-scraper/venv"

echo "Starting services..."

# Create a new tmux session named "trendpup"
if command_exists tmux; then
    # Kill existing session if it exists
    tmux kill-session -t trendpup 2>/dev/null

    # Create new session
    tmux new-session -d -s trendpup

    # Start backend in first window
    # Explicitly set SERVER_PORT to 3001 to avoid conflicts
    # Make sure WebSocket server can start on 8080
    tmux send-keys -t trendpup:0 'cd agent && pnpm install && HOST=0.0.0.0 SERVER_PORT=3001 pnpm start --character="./characters/professor.character.json"' C-m
    
    # Wait a bit for the backend to start
    sleep 5

    # Create new window for frontend
    tmux new-window -t trendpup:1
    # Start Next.js app using standard command
    tmux send-keys -t trendpup:1 'cd frontend && pnpm install && pnpm build && pnpm start' C-m
    
    # Create new window for twitter-scraper with venv activated
    tmux new-window -t trendpup:2
    # Activate virtual environment and start main.py in scheduler mode
    tmux send-keys -t trendpup:2 'cd twitter-scraper && source venv/bin/activate && python3 main.py' C-m
    tmux rename-window -t trendpup:2 'scraper'

    # Set the initial window to backend (0)
    tmux select-window -t trendpup:0
    
    # Function to gracefully shutdown all processes when tmux session ends
    cleanup_on_exit() {
        echo "Shutting down all services..."
        tmux send-keys -t trendpup:2 C-c
        tmux send-keys -t trendpup:1 C-c
        tmux send-keys -t trendpup:0 C-c
        sleep 2
        tmux kill-session -t trendpup
    }
    
    # Attach to the session
    trap cleanup_on_exit EXIT
    tmux attach-session -t trendpup

else
    # If tmux is not available, use background processes
    echo "Starting services..."
    
    # Start backend with explicit port settings
    (cd agent && pnpm install && HOST=0.0.0.0 SERVER_PORT=3001 pnpm start --character="./characters/professor.character.json") &
    
    # Wait a bit for backend to start
    sleep 5
    
    # Start frontend with standard Next.js command
    (cd frontend && pnpm install && pnpm build && pnpm start) &
    
    # Start twitter scraper in background with venv activated
    (cd twitter-scraper && source venv/bin/activate && python3 main.py --schedule) &
    
    # Function to gracefully shutdown all processes on exit
    cleanup_on_exit() {
        echo "Shutting down all services..."
        pkill -f "python3 main.py"
        pkill -f "pnpm start"
        pkill -f "SERVER_PORT=3001 pnpm start"
    }
    
    # Set up trap for graceful shutdown
    trap cleanup_on_exit EXIT
    
    # Wait for all processes
    wait
fi 