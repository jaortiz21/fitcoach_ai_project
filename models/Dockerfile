FROM ollama/ollama:0.1-slim

WORKDIR /app

# Copy the model initialization script
COPY ../scripts/init-models.sh /app/init-models.sh

# Make the script executable
RUN chmod +x /app/init-models.sh

# Copy the Modelfile
COPY Modelfile /models/Modelfile

# Set the entrypoint to the initialization script
ENTRYPOINT ["/app/init-models.sh"]
