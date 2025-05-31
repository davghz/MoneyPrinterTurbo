import argparse
import sys
import os
import signal # For more robust exit handling if needed, though try/finally covers Ctrl+C
from loguru import logger

# Assuming 'app' is in PYTHONPATH or main.py is in the root project directory
try:
    from app.orchestrator.stream_orchestrator import StreamOrchestrator
except ImportError:
    # Adjust path if main.py is not in the root or 'app' is not directly importable
    # This is a common adjustment needed depending on how the script is run.
    # For example, if main.py is in root, and app is a dir:
    # sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
    from app.orchestrator.stream_orchestrator import StreamOrchestrator


# Global flag to indicate if shutdown is in progress
shutdown_in_progress = False
orchestrator_instance: StreamOrchestrator = None

def setup_logging():
    """Configures Loguru logger."""
    logger.remove()  # Remove default handler
    # Log level can be configured from stream_config.json by the orchestrator itself if it reads it.
    # For now, set a default for main.py.
    logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
    logger.info("Logging setup complete.")

def signal_handler(signum, frame):
    """Handles signals like SIGINT (Ctrl+C) and SIGTERM for graceful shutdown."""
    global shutdown_in_progress
    global orchestrator_instance

    if shutdown_in_progress:
        logger.warning("Shutdown already in progress. Please wait or force quit if necessary.")
        return

    shutdown_in_progress = True
    signal_name = signal.Signals(signum).name
    logger.info(f"{signal_name} received. Initiating graceful shutdown...")

    if orchestrator_instance is not None:
        orchestrator_instance.stop()

    logger.info("Application cleanup finished. Exiting.")
    # sys.exit(0) # Normal exit after cleanup. Orchestrator.stop() should allow run_loop to finish.

def main():
    """
    Main function to initialize and run the StreamOrchestrator.
    """
    global orchestrator_instance # Allow signal handler to access it

    setup_logging()

    parser = argparse.ArgumentParser(description="HarmoniStream AI Stream Orchestrator")

    # Determine default config path relative to main.py's location (assumed to be project root)
    # If main.py is in project root, stream_config.example.json is also in root.
    project_root = os.path.dirname(os.path.abspath(__file__))
    default_config_path = os.path.join(project_root, "stream_config.example.json")

    # If stream_config.json exists, use it as default, otherwise use example.
    actual_config_path = os.path.join(project_root, "stream_config.json")
    if os.path.exists(actual_config_path):
        default_config_path = actual_config_path
        logger.info(f"Found 'stream_config.json', using it as default: {default_config_path}")
    else:
        logger.info(f"No 'stream_config.json' found, using example as default: {default_config_path}")


    parser.add_argument(
        "--config",
        type=str,
        default=default_config_path,
        help="Path to the stream configuration JSON file (e.g., stream_config.json or stream_config.example.json)."
    )
    args = parser.parse_args()

    logger.info(f"Using stream configuration file: {args.config}")

    if not os.path.exists(args.config):
        logger.error(f"Configuration file not found: {args.config}. Please ensure the path is correct.")
        sys.exit(1)

    orchestrator_instance = StreamOrchestrator(config_file_path=args.config)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)  # Handle Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler) # Handle `kill` command

    if orchestrator_instance.config and orchestrator_instance.ffmpeg_manager: # Check if init was successful
        try:
            logger.info("Starting StreamOrchestrator run_loop...")
            orchestrator_instance.run_loop()  # This blocks until orchestrator's loop exits
        except Exception as e:
            # KeyboardInterrupt is caught by signal_handler now
            logger.exception(f"Unhandled exception during StreamOrchestrator run_loop: {e}")
        finally:
            # This finally block will run after run_loop exits, either normally or via exception
            # (but not if process is killed with SIGKILL).
            # Graceful shutdown is primarily handled by signal_handler setting shutdown_event.
            logger.info("StreamOrchestrator run_loop has exited.")
            # Ensure stop is called if not already via signal handler (e.g., if run_loop exits due to other reasons)
            if not shutdown_in_progress: # Check if signal_handler already ran
                logger.info("Run_loop exited without explicit signal. Ensuring orchestrator stop sequence.")
                orchestrator_instance.stop()
    else:
        logger.error("StreamOrchestrator did not initialize properly (config or ffmpeg_manager missing). Cannot start run_loop.")

    logger.info("Application main function finished.")

if __name__ == "__main__":
    main()
