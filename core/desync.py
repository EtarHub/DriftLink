from dataclasses import dataclass
import time
from core.config import AUTO_SWITCH_TIMEOUT, FAKE_SNI, STRATEGIES


@dataclass
class PacketAction:
    payload: bytes
    seq_offset: int
    ttl: int | None = None
    bad_checksum: bool = False


class AdaptiveStrategyManager:
    """Управляет выбором стратегии: поддерживает ручной выбор (Избранное/Тест)

    и автоматическое переключение при смене сети/Wi-Fi.
    """

    def __init__(self):
        self.current_idx = 0
        self.forced_strategy: dict | None = None
        self.pending_connections: dict[tuple, float] = {}
        self.last_switch_time = 0.0

    @property
    def current_strategy(self) -> dict:
        if self.forced_strategy is not None:
            return self.forced_strategy
        return STRATEGIES[self.current_idx % len(STRATEGIES)]

    def set_strategy(self, strategy: dict | None):
        """Устанавливает конкретную стратегию (из Избранного/Генератора)

        или None для возврата в автоматический режим.
        """
        self.forced_strategy = strategy
        self.pending_connections.clear()

    def register_outgoing(self, conn_key: tuple):
        """Запоминаем время отправки ClientHello для отслеживания успеха."""
        # Если пользователь жестко выбрал стратегию вручную, не переключаем её сами
        if self.forced_strategy is not None:
            return

        now = time.monotonic()
        failed = 0
        for k, ts in list(self.pending_connections.items()):
            if now - ts > AUTO_SWITCH_TIMEOUT:
                failed += 1
                del self.pending_connections[k]

        # Если 3+ соединения подряд зависли без ответа — переключаем на следующий профиль
        if failed >= 3 and (now - self.last_switch_time > 5.0):
            self.current_idx = (self.current_idx + 1) % len(STRATEGIES)
            self.last_switch_time = now
            print(
                "\n[!] Сеть не отвечает на текущую стратегию. Переключаюсь на:"
                f" {self.current_strategy['name']}\n"
            )

        self.pending_connections[conn_key] = now

    def register_incoming_success(self, conn_key: tuple):
        """Если сервер ответил (пришел ServerHello) — стратегия работает."""
        self.pending_connections.pop(conn_key, None)

    def build_sequence(
        self, payload: bytes, sni_start: int, sni_len: int
    ) -> list[PacketAction]:
        strat = self.current_strategy
        stype = strat.get("type", "cascade_fake_disorder")

        if stype == "multisplit":
            return self._build_multisplit(payload, sni_start, sni_len)

        raw_ttl = strat.get("ttl_list", "3,4,5")
        if isinstance(raw_ttl, str):
            ttl_values = tuple(
                int(x.strip()) for x in raw_ttl.split(",") if x.strip()
            )
        else:
            ttl_values = tuple(raw_ttl)

        return self._build_cascade_fake(
            payload,
            sni_start,
            sni_len,
            ttl_list=ttl_values,
            use_badsum=strat.get("use_bad_checksum", True),
        )

    def _build_cascade_fake(
        self,
        payload: bytes,
        sni_start: int,
        sni_len: int,
        ttl_list: tuple[int, ...],
        use_badsum: bool,
    ) -> list[PacketAction]:
        actions = []
        before = payload[:sni_start]
        domain_part = payload[sni_start : sni_start + sni_len]
        after = payload[sni_start + sni_len :]

        fake_domain = (
            FAKE_SNI.ljust(sni_len, b"\x00")
            if len(FAKE_SNI) <= sni_len
            else FAKE_SNI[:sni_len]
        )

        # 1. Часть пакета до домена
        actions.append(PacketAction(payload=before, seq_offset=0))

        # 2. Каскад фейковых доменов с заданным TTL и опциональной порчей чексуммы
        for test_ttl in ttl_list:
            actions.append(
                PacketAction(
                    payload=fake_domain,
                    seq_offset=sni_start,
                    ttl=test_ttl,
                    bad_checksum=use_badsum,
                )
            )

        # 3. Настоящий домен, разрезанный пополам в обратном порядке (Disorder)
        mid = sni_len // 2
        actions.append(
            PacketAction(
                payload=domain_part[mid:],
                seq_offset=sni_start + mid,
                bad_checksum=False,
            )
        )
        actions.append(
            PacketAction(
                payload=domain_part[:mid],
                seq_offset=sni_start,
                bad_checksum=False,
            )
        )

        # 4. Хвост пакета
        if after:
            actions.append(
                PacketAction(
                    payload=after,
                    seq_offset=sni_start + sni_len,
                    bad_checksum=False,
                )
            )
        return actions

    def _build_multisplit(
        self, payload: bytes, sni_start: int, sni_len: int
    ) -> list[PacketAction]:
        """Чистое разрезание без фейков (для корпоративных сетей и строгих NAT)."""
        cut_points = sorted(
            {1, 2, sni_start + 1, sni_start + (sni_len // 2), len(payload)}
        )
        cut_points = [p for p in cut_points if 0 < p <= len(payload)]

        actions = []
        prev = 0
        for pt in cut_points:
            actions.append(
                PacketAction(
                    payload=payload[prev:pt], seq_offset=prev, bad_checksum=False
                )
            )
            prev = pt

        actions.reverse()
        return actions
