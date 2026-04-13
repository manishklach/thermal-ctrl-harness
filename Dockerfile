FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY thermal_ctrl/ ./thermal_ctrl/
COPY configs/ ./configs/
CMD ["python", "-m", "thermal_ctrl", "dry-run", "--config", "configs/config.yaml"]
