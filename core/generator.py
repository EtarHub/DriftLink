import random


def get_base_pool() -> list[dict]:
    """Возвращает полный базовый пул проверенных стратегий."""
    return [
        {
            "name": "Cascade TTL(3,4,5) + BadSum",
            "type": "cascade_fake_disorder",
            "ttl_list": "3,4,5",
            "use_bad_checksum": True,
        },
        {
            "name": "Cascade TTL(2,3,4) + BadSum",
            "type": "cascade_fake_disorder",
            "ttl_list": "2,3,4",
            "use_bad_checksum": True,
        },
        {
            "name": "Cascade TTL(4,5,6) + BadSum",
            "type": "cascade_fake_disorder",
            "ttl_list": "4,5,6",
            "use_bad_checksum": True,
        },
        {
            "name": "Cascade TTL(5,6,7) + BadSum",
            "type": "cascade_fake_disorder",
            "ttl_list": "5,6,7",
            "use_bad_checksum": True,
        },
        {
            "name": "Clean MultiSplit (без фейков)",
            "type": "multisplit",
        },
        {
            "name": "Clean TTL(2,3,4) (без BadSum)",
            "type": "cascade_fake_disorder",
            "ttl_list": "2,3,4",
            "use_bad_checksum": False,
        },
        {
            "name": "Clean TTL(3,4,5) (без BadSum)",
            "type": "cascade_fake_disorder",
            "ttl_list": "3,4,5",
            "use_bad_checksum": False,
        },
        {
            "name": "Single TTL(3) + BadSum",
            "type": "cascade_fake_disorder",
            "ttl_list": "3",
            "use_bad_checksum": True,
        },
        {
            "name": "Single TTL(4) + BadSum",
            "type": "cascade_fake_disorder",
            "ttl_list": "4",
            "use_bad_checksum": True,
        },
    ]


def generate_random_strategy(existing_names: set[str] | None = None) -> dict:
    """Генерирует новую уникальную стратегию для сложных провайдеров."""
    if existing_names is None:
        existing_names = set()

    for _ in range(30):
        mode = random.choice(["cascade", "single", "wide"])
        badsum = random.choice([True, False])
        tag = "BadSum" if badsum else "Clean"

        if mode == "single":
            t = random.randint(2, 8)
            ttl_str = str(t)
        elif mode == "wide":
            t = random.randint(2, 5)
            ttl_str = f"{t},{t+2},{t+4}"
        else:
            t = random.randint(2, 7)
            ttl_str = f"{t},{t+1},{t+2}"

        name = f"Gen_TTL({ttl_str})_{tag}"
        if name not in existing_names:
            return {
                "name": name,
                "type": "cascade_fake_disorder",
                "ttl_list": ttl_str,
                "use_bad_checksum": badsum,
            }

    return {
        "name": f"Gen_MultiSplit_{random.randint(100, 999)}",
        "type": "multisplit",
    }


def build_test_suite(extra_random: int = 8) -> list[dict]:
    """Формирует полный набор стратегий для автоматического теста (базовые + сгенерированные)."""
    suite = get_base_pool()
    seen = {s["name"] for s in suite}
    for _ in range(extra_random):
        cand = generate_random_strategy(seen)
        seen.add(cand["name"])
        suite.append(cand)
    return suite
