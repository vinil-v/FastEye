#!/bin/bash
curl -fsSL https://ollama.com/install.sh | sh
ollama --version
systemct status ollama
ollama pull llama3:8b
ollama list
apt install python3.10-venv
python3 -m venv LogWise
