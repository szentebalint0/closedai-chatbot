import json

from sql_tools import get_hot_products


def main() -> None:
    print(json.dumps(get_hot_products(), indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
