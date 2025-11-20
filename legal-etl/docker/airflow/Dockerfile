FROM apache/airflow:2.9.2-python3.11

USER root
RUN mkdir -p /opt/legal-etl
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
USER airflow

ENV AIRFLOW_HOME=/opt/airflow
