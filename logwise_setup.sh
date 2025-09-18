#!/bin/bash
# LogWise Setup Script
# This script sets up the LogWise environment with Ollama and required dependencies.
# Supported on Ubuntu/Debian systems.
# Update and install prerequisites
# Ollama installation and model download
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3:8b
# Python environment setup
sudo apt update
sudo apt install python3.10-venv
python3 -m venv LogWise
cd LogWise
# Create Streamlit secrets.toml
mkdir -p .streamlit
touch .streamlit/secrets.toml
echo "[ollama]" >> .streamlit/secrets.toml
echo 'url = "http://localhost:11434"' >> .streamlit/secrets.toml
echo 'model = "llama3:8b"' >> .streamlit/secrets.toml
# Install Python dependencies
source bin/activate
pip install streamlit requests
wget https://raw.githubusercontent.com/vinil-v/LogWise/refs/heads/main/logwise.py

#build run script
touch run.sh
echo "#!/bin/bash" >> run.sh
echo "streamlit run logwise.py" >> run.sh
chmod +x run.sh
echo "Setup complete. Run './run.sh' to start LogWise."