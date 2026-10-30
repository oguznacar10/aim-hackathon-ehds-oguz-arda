# Hosted demo of the Health Data Access Body app. Standard library only, no pip install.
# Keys come from the platform's environment: OPENROUTER_API_KEY, TYPESAFE_API_KEY, GATEKEEPER_SECOND_OPINION=jev.
FROM python:3.12.12-slim
WORKDIR /app
COPY src ./src
COPY scripts/serve.py ./scripts/serve.py
COPY challenge/requests ./challenge/requests
COPY challenge/data ./challenge/data
COPY challenge/README.md ./challenge/README.md
ENV HOST=0.0.0.0 PORT=8000 PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "scripts/serve.py"]
