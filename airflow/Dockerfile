# Extends official Airflow 2.9 image to bake in cs2_analytics package and Slack provider.
# Using Dockerfile instead of _PIP_ADDITIONAL_REQUIREMENTS to avoid re-pip on every container start.
FROM apache/airflow:2.9.3-python3.12

USER root
# Copy package metadata and source for pip install
COPY --chown=airflow:0 pyproject.toml /opt/cs2-analytics/pyproject.toml
COPY --chown=airflow:0 src /opt/cs2-analytics/src
COPY --chown=airflow:0 scripts /opt/cs2-analytics/scripts
# Copy dbt project into the image — BashOperator runs dbt CLI from this path
COPY --chown=airflow:0 dbt_project /opt/cs2-analytics/dbt_project

# Switch to airflow user before pip — the official image blocks root pip
USER airflow

# Install local package (cs2_analytics), Slack/Celery providers, dbt + Snowflake connector
# Pin apache-airflow-providers-slack==8.7.1 — version from constraints-2.9.3/constraints-3.12.txt
# (9.x requires Airflow >= 2.11 and will conflict)
# dbt-core 1.11.7 + dbt-snowflake 1.11.3 must match minor version (Pitfall 5 from RESEARCH.md)
# cryptography>=41.0 required for RSA key-pair auth (Snowflake killed password auth Nov 2025)
RUN pip install --no-cache-dir /opt/cs2-analytics \
    "apache-airflow-providers-slack==8.7.1" \
    "apache-airflow-providers-celery>=3.7,<4.0" \
    "dbt-core==1.11.7" \
    "dbt-snowflake==1.11.3" \
    "snowflake-connector-python>=3.0" \
    "cryptography>=41.0"
# Add the repo root and src to PYTHONPATH so DAG tasks can import both
# `scripts.bootstrap_csapi` and the installed package modules.
ENV PYTHONPATH="/opt/cs2-analytics:/opt/cs2-analytics/src:${PYTHONPATH}"
