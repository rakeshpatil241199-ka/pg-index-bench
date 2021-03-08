FROM python:3.10-slim

WORKDIR /app
ENV PYTHONPATH=/app/src
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY sql/ ./sql/
COPY src/ ./src/
COPY tests/ ./tests/

RUN python3 -m unittest discover -s /app/tests -p "test_*.py" -v

ENTRYPOINT ["python3", "-m", "pg_index_bench.cli"]
CMD ["--help"]