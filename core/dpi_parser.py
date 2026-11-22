import struct
from core.config import TARGET_DOMAINS

# Известные сигнатуры версий QUIC (байты с 1 по 5)
QUIC_VERSIONS = {
    b"\x00\x00\x00\x01",  # QUIC v1 (RFC 9000)
    b"\x6b\x33\x43\xcf",  # QUIC v2 (RFC 9369)
    b"\xff\x00\x00\x1d",  # Draft-29 (часто используется Google)
}


def is_quic_initial(payload: bytes) -> bool:
    """Точно определяет пакеты QUIC Initial, не задевая WebRTC-звонки и игры."""
    if len(payload) < 1200:
        return False

    # Проверяем Long Header (старший бит первого байта == 1)
    first_byte = payload[0]
    if (first_byte & 0x80) == 0:
        return False

    # Проверяем версию QUIC (байты 1..5)
    version = payload[1:5]
    if version in QUIC_VERSIONS or version.startswith(b"Q0"):
        return True

    return False


def extract_sni(payload: bytes) -> tuple[str, int, int] | None:
    """Строгий парсер TLS ClientHello.

    Возвращает кортеж: (имя_домена, индекс_начала_домена, длина_домена) или None.
    """
    if len(payload) < 43:
        return None

    if payload[0:1] != b"\x16" or payload[5:6] != b"\x01":
        return None

    try:
        pos = 43

        # 1. Session ID
        session_id_len = payload[pos]
        pos += 1 + session_id_len
        if pos + 2 > len(payload):
            return None

        # 2. Cipher Suites
        cipher_suites_len = struct.unpack("!H", payload[pos : pos + 2])[0]
        pos += 2 + cipher_suites_len
        if pos + 1 > len(payload):
            return None

        # 3. Compression Methods
        comp_methods_len = payload[pos]
        pos += 1 + comp_methods_len
        if pos + 2 > len(payload):
            return None

        # 4. Extensions Length
        extensions_len = struct.unpack("!H", payload[pos : pos + 2])[0]
        pos += 2
        extensions_end = min(pos + extensions_len, len(payload))

        while pos + 4 <= extensions_end:
            ext_type, ext_len = struct.unpack("!HH", payload[pos : pos + 4])
            pos += 4

            if ext_type == 0x0000 and pos + ext_len <= extensions_end:
                if ext_len >= 5 and payload[pos + 2 : pos + 3] == b"\x00":
                    name_len = struct.unpack(
                        "!H", payload[pos + 3 : pos + 5]
                    )[0]
                    name_start = pos + 5
                    if name_start + name_len <= extensions_end:
                        sni_bytes = payload[name_start : name_start + name_len]
                        return (
                            sni_bytes.decode("ascii", errors="ignore").lower(),
                            name_start,
                            name_len,
                        )
            pos += ext_len
    except (struct.error, IndexError):
        return None

    return None


def match_target_sni(payload: bytes) -> tuple[str, int, int] | None:
    """Проверяет, входит ли извлеченный SNI в список целевых доменов."""
    sni_info = extract_sni(payload)
    if not sni_info:
        return None

    hostname, start, length = sni_info
    host_bytes = hostname.encode("ascii")

    for target in TARGET_DOMAINS:
        if host_bytes == target or host_bytes.endswith(b"." + target):
            return hostname, start, length

    return None
