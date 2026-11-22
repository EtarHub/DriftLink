import json
import socket
import ssl
import time
import urllib.request


def resolve_via_doh(hostname: str) -> str | None:
    """Получает честный IP-адрес через Яндекс.DoH (JSON API) или Cloudflare DoH, исключая gaierror."""
    doh_endpoints = [
        f"https://common.dot.dns.yandex.net/resolve?name={hostname}&type=A",
        f"https://cloudflare-dns.com/dns-query?name={hostname}&type=A",
    ]
    for url in doh_endpoints:
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/dns-json"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for ans in data.get("Answer", []):
                    if ans.get("type") == 1:  # A-запись (IPv4)
                        return ans.get("data")
        except Exception:
            continue

    # Запасной вариант — системный DNS
    try:
        return socket.gethostbyname(hostname)
    except Exception:
        return None


def test_current_connection(timeout: float = 2.5) -> tuple[bool, int, str]:
    """Проверяет прохождение TLS Handshake до YouTube через активный обход.

    Возвращает: (успех: bool, задержка_мс: int, сообщение: str)
    """
    test_hosts = ("www.youtube.com", "i.ytimg.com")
    context = ssl.create_default_context()
    total_ms = 0

    for host in test_hosts:
        target_ip = resolve_via_doh(host)
        if not target_ip:
            return False, 0, f"Не удалось получить IP для {host}"

        start_time = time.perf_counter()
        try:
            # Подключаемся напрямую по IP, но передаем server_hostname для SNI в TLS ClientHello
            with socket.create_connection((target_ip, 443), timeout=timeout) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    _ = ssock.version()
            elapsed = int((time.perf_counter() - start_time) * 1000)
            total_ms += elapsed
        except TimeoutError:
            return False, 0, f"Таймаут DPI на {host}"
        except ConnectionResetError:
            return False, 0, f"Сброс (RST) на {host}"
        except ssl.SSLError as e:
            return False, 0, f"Ошибка TLS ({e.reason})"
        except Exception as e:
            return False, 0, f"Ошибка ({type(e).__name__})"

    avg_ms = total_ms // len(test_hosts)
    return True, avg_ms, f"Успешно ({avg_ms} мс)"
