from datetime import datetime
import threading
import pydivert
from core.config import BLOCK_QUIC
from core.desync import AdaptiveStrategyManager
from core.dpi_parser import is_quic_initial, match_target_sni


def start_windows_engine(
    stop_event: threading.Event | None = None,
    log_callback=None,
    strategy_callback=None,
    manager_holder: dict | None = None,
):
    if stop_event is None:
        stop_event = threading.Event()

    def emit_log(msg: str):
        now = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{now}] {msg}"
        if log_callback:
            log_callback(formatted)
        else:
            print(formatted)

    manager = AdaptiveStrategyManager()
    if manager_holder is not None:
        manager_holder["manager"] = manager

    last_strategy = manager.current_strategy["name"]
    if strategy_callback:
        strategy_callback(last_strategy)

    if BLOCK_QUIC:
        flt = (
            "(outbound and ((tcp.DstPort == 443 and tcp.PayloadLength > 0) or"
            " (udp.DstPort == 443 and udp.PayloadLength >= 1200))) or (inbound"
            " and tcp.SrcPort == 443 and tcp.PayloadLength > 0)"
        )
    else:
        flt = (
            "(outbound and tcp.DstPort == 443 and tcp.PayloadLength > 0) or"
            " (inbound and tcp.SrcPort == 443 and tcp.PayloadLength > 0)"
        )

    emit_log(f"Движок запущен. Стратегия: {last_strategy}")

    try:
        with pydivert.WinDivert(flt) as w:
            while not stop_event.is_set():
                packet = w.recv()
                if stop_event.is_set():
                    w.send(packet)
                    break

                # Отслеживаем смену стратегии (автоматическую или из UI)
                curr_strat = manager.current_strategy["name"]
                if curr_strat != last_strategy:
                    last_strategy = curr_strat
                    emit_log(f"[*] Активная стратегия -> {curr_strat}")
                    if strategy_callback:
                        strategy_callback(curr_strat)

                # Входящий ответ от сервера -> фиксируем успех соединения
                if packet.is_inbound and packet.tcp:
                    conn_key = (
                        packet.dst_addr,
                        packet.tcp.dst_port,
                        packet.src_addr,
                        packet.tcp.src_port,
                    )
                    manager.register_incoming_success(conn_key)
                    w.send(packet)
                    continue

                # Блокировка QUIC Initial
                if packet.udp:
                    if is_quic_initial(packet.payload):
                        continue
                    w.send(packet)
                    continue

                # Десинхронизация TLS ClientHello
                if packet.tcp:
                    sni_match = match_target_sni(packet.payload)
                    if sni_match:
                        hostname, sni_start, sni_len = sni_match
                        conn_key = (
                            packet.src_addr,
                            packet.tcp.src_port,
                            packet.dst_addr,
                            packet.tcp.dst_port,
                        )
                        manager.register_outgoing(conn_key)
                        emit_log(f"[+] {hostname}")

                        orig_seq = packet.tcp.seq_num
                        orig_ttl = (
                            packet.ipv4.ttl
                            if packet.ipv4
                            else (
                                packet.ipv6.hop_limit if packet.ipv6 else 128
                            )
                        )

                        actions = manager.build_sequence(
                            packet.payload, sni_start, sni_len
                        )

                        for action in actions:
                            packet.payload = action.payload
                            packet.tcp.seq_num = orig_seq + action.seq_offset

                            target_ttl = (
                                action.ttl
                                if action.ttl is not None
                                else orig_ttl
                            )
                            if packet.ipv4:
                                packet.ipv4.ttl = target_ttl
                            elif packet.ipv6:
                                packet.ipv6.hop_limit = target_ttl

                            packet.recalculate_checksums()
                            if action.bad_checksum:
                                packet.tcp.cksum = (
                                    packet.tcp.cksum ^ 0xFFFF
                                ) & 0xFFFF

                            w.send(packet, recalculate_checksum=False)
                        continue

                w.send(packet)

    except PermissionError:
        emit_log("[!] ОШИБКА: Запусти программу от имени Администратора!")
    except Exception as e:
        if not stop_event.is_set():
            emit_log(f"[!] Ошибка движка: {e}")
    finally:
        if manager_holder is not None:
            manager_holder.pop("manager", None)
        emit_log("Движок остановлен.")
