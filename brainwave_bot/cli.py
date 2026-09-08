import argparse
import json
from .orchestrator import default_orchestrator

def main() -> None:
    parser = argparse.ArgumentParser(description="Ask Brainwave business questions")
    parser.add_argument("question")
    parser.add_argument("--markets", nargs="+", default=["EMEA", "APAC", "AMER", "LATAM"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = default_orchestrator().ask(args.question, args.markets)
    print(result.model_dump_json(indent=2) if args.json else result.answer)

if __name__ == "__main__":
    main()
