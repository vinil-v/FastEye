#!/bin/bash
#check the root user
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3:8b
sudo apt update
sudo apt install python3.10-venv
python3 -m venv LogWise
cd LogWise
mkdir -p .streamlit
touch .streamlit/secrets.toml
echo "[ollama]" >> .streamlit/secrets.toml
echo 'url = "http://localhost:11434"' >> .streamlit/secrets.toml
echo 'model = "llama3:8b"' >> .streamlit/secrets.toml
source bin/activate
pip install streamlit requests
touch run.sh
echo "#!/bin/bash" >> run.sh
echo "streamlit run logwise.py" >> run.sh
chmod +x run.sh
echo "Setup complete. Run './run.sh' to start LogWise."

