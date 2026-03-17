# Extends official Airflow 2.9 image to bake in cs2_analytics package and Slack provider.
# Using Dockerfile instead of _PIP_ADDITIONAL_REQUIREMENTS to avoid re-pip on every container start.
FROM apache/airflow:2.9-python3.12

USER root
# Copy package metadata and source for pip install
COPY pyproject.toml /opt/cs2-analytics/pyproject.toml
COPY src /opt/cs2-analytics/src

# Install local package (cs2_analytics) and Slack provider
# Pin apache-airflow-providers-slack==8.7.1 — version from constraints-2.9.3/constraints-3.12.txt
# (9.x requires Airflow >= 2.11 and will conflict)
RUN pip install --no-cache-dir /opt/cs2-analytics \
    "apache-airflow-providers-slack==8.7.1"

USER airflow
# Add src to PYTHONPATH so `from cs2_analytics.ingestion.faceit import FACEITClient` works
# in all containers (scheduler + worker + webserver share this anchor)
ENV PYTHONPATH="/opt/cs2-analytics/src:${PYTHONPATH}"
