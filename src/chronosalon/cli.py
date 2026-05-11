from __future__ import annotations

import argparse
import json
from pathlib import Path

from chronosalon.app import ChronoSalonApp
from chronosalon.services.config_loader import ModelConfigLoader


def main() -> None:
    parser = argparse.ArgumentParser(prog="chronosalon", description="ChronoSalon MVP command line tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build-room", help="Build a room draft from a topic.")
    build_parser.add_argument("topic")

    chat_parser = subparsers.add_parser("demo-chat", help="Run a deterministic local chat demo.")
    chat_parser.add_argument("topic")
    chat_parser.add_argument("message")

    config_parser = subparsers.add_parser("check-config", help="Load model configuration template.")
    config_parser.add_argument("--path", default="src/config/model_config.yaml")

    serve_parser = subparsers.add_parser("serve", help="Start the ChronoSalon API and frontend server.")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()
    app = ChronoSalonApp()

    if args.command == "build-room":
        print(json.dumps(app.build_room(args.topic), ensure_ascii=False, indent=2))
        return

    if args.command == "demo-chat":
        room = app.build_room(args.topic)
        payload = app.chat(room, args.message)
        print(json.dumps({"room": room, **payload}, ensure_ascii=False, indent=2))
        return

    if args.command == "check-config":
        configs = ModelConfigLoader().load(Path(args.path))
        print(json.dumps({name: config.__dict__ for name, config in configs.items()}, ensure_ascii=False, indent=2))
        return

    if args.command == "serve":
        import uvicorn

        uvicorn.run("chronosalon.api:app", host=args.host, port=args.port, reload=False)
        return


if __name__ == "__main__":
    main()
