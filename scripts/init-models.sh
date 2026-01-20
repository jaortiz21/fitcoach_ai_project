#!/bin/sh
set -e

ollama serve
sleep 3

echo "Waiting for Ollama to be ready..."
until wget -qO- http://ollama:11434/api/version >/dev/null 2>&1; do
  sleep 2
done

echo "Pulling base model..."
ollama pull llama3

echo "Pulling embedding model..."
ollama pull nomic-embed-text

if ! ollama list | grep -q fitcoach; then
  echo "Creating fitcoach model..."
  ollama create fitcoach -f /models/Modelfile
else
  echo "fitcoach model already exists"
fi

echo "Model initialization complete."

wait
