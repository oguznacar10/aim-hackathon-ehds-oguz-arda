# Hosted demo of the Health Data Access Body app. Standard library only, no pip install.
# No key in the image: the hosting platform sets the three variables named in the README run section.
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
