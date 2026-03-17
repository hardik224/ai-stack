from app.services.processor import run_worker_loop


def main() -> None:
    run_worker_loop()


if __name__ == "__main__":
    main()
