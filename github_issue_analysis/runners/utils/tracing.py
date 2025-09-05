# src/utils/tracing.py
from __future__ import annotations

import logging
import os
from pathlib import Path


def setup_tracing(experiment_name: str = "experiment") -> None:
    """
    Configure tracing for one of: file | mlflow | phoenix.
    Also keeps standard Python logging to 'data/results/{experiment_name}/system.log'.
    """
    backend = os.getenv("TRACING_BACKEND", "file").lower()

    # Always ensure log directory + basic logging to file remains
    log_dir = Path(f"data/results/{experiment_name}")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "system.log"
    if not any(
        isinstance(h, logging.FileHandler)
        and getattr(h, "baseFilename", "") == str(log_file)
        for h in logging.getLogger().handlers
    ):
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )
        root = logging.getLogger()
        root.addHandler(fh)
        root.setLevel(logging.DEBUG)

    if backend == "mlflow":
        _setup_tracing_mlflow(experiment_name)
    elif backend == "phoenix":
        _setup_tracing_phoenix(experiment_name)
    else:
        _setup_tracing_filefallback(log_dir)


def _setup_tracing_mlflow(experiment_name: str) -> None:
    """
    Configure MLflow with PydanticAI autologging for full tracing.

    Creates a master parent run that all agent runs will nest under,
    preventing accidental grandchild nesting while preserving all traces.

    Requires MLFLOW_TRACKING_URI to be set if you run a server,
    otherwise MLflow will default to a local ./mlruns directory.
    """
    from datetime import datetime

    import mlflow

    tracking_uri = os.getenv(
        "MLFLOW_TRACKING_URI"
    )  # e.g., http://127.0.0.1:5000 or file:./mlruns
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)

    mlflow.set_experiment(experiment_name)

    # Enable PydanticAI autologging for full tracing
    import mlflow.pydantic_ai as ml_pa

    ml_pa.autolog(log_traces=True, silent=True)

    # Create and ACTIVATE a master parent run for the entire experiment
    # Keep it active so autologging sends traces here
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    master_run_name = f"{experiment_name}_master_{timestamp}"

    # Use mlflow.start_run to create AND activate the master run
    master_run = mlflow.start_run(run_name=master_run_name)

    # Set tags on the master run
    mlflow.set_tag("run.type", "master")
    mlflow.set_tag("experiment.name", experiment_name)
    mlflow.set_tag("timestamp", timestamp)

    # Store the master run ID globally so agents can create child runs
    os.environ["MLFLOW_MASTER_RUN_ID"] = master_run.info.run_id

    # Important: Don't end this run - keep it active for autologging
    print(f"📊 Created and activated MLflow master run: {master_run_name}")
    print(f"🔗 Master run ID: {master_run.info.run_id}")
    print("📝 Master run will remain active to collect all traces")


def _setup_tracing_phoenix(experiment_name: str) -> None:
    """
    Set up Phoenix tracing with simplified, best-practice approach.

    Uses automatic instrumentation and proper OpenInference conventions
    to ensure optimal Phoenix integration and data quality.
    """
    try:
        from utils.phoenix_integration import setup_phoenix_tracing

        # Set up Phoenix with simplified integration
        phoenix = setup_phoenix_tracing(experiment_name)

        if phoenix:
            # Store Phoenix integration globally for use in experiments
            os.environ["PHOENIX_INTEGRATION_INITIALIZED"] = "true"
            # Store the experiment name for later use
            os.environ["PHOENIX_EXPERIMENT_NAME"] = experiment_name

            print(f"🔭 Phoenix tracing enabled for project: {experiment_name}")
            print("📊 Features: automatic instrumentation, datasets, evaluations")
        else:
            print("❌ Phoenix setup failed - falling back to file tracing")
            # Fall back to file tracing if Phoenix setup fails
            _setup_tracing_filefallback(Path("data/results/03_mcp_agents"))

    except ImportError as e:
        print(f"⚠️ Phoenix integration not available: {e}")
        print("📁 Falling back to file tracing")
        _setup_tracing_filefallback(Path("data/results/03_mcp_agents"))


def _setup_tracing_filefallback(log_dir: Path) -> None:
    """
    Your current behavior: write spans to a local telemetry file.
    Useful as a no-external-dependency fallback.
    """
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    telemetry_file = log_dir / "telemetry.txt"
    fh = open(telemetry_file, "w")
    exporter = ConsoleSpanExporter(out=fh)

    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    logging.getLogger(__name__).info("Telemetry (OTel spans) -> %s", telemetry_file)
