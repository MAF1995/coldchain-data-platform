FROM apache/airflow:3.3.1-python3.12

COPY --chown=airflow:root infra/airflow/requirements.txt /tmp/requirements-pharma.txt
RUN pip install --no-cache-dir -r /tmp/requirements-pharma.txt
