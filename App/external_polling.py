import threading
import time
import requests
from datetime import datetime
from typing import Callable, Optional

DEFAULT_POLL_INTERVAL = 2.0
DEFAULT_TIMEOUT = 10.0
MAX_BACKOFF = 30.0
BACKOFF_FACTOR = 2.0

class Poller:
    def __init__(
        self,
        server_url: str,
        on_new: Callable[[list], None],
        since: Optional[str] = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.server_url = server_url  # erwartet vollen Endpoint, z.B. "http://host:8000/messages"
        self.on_new = on_new
        self.since = since
        self.poll_interval = float(poll_interval)
        self.timeout = float(timeout)

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self, daemon=True):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=daemon)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run(self):
        backoff = self.poll_interval
        while not self._stop_event.is_set():
            try:
                params = {}
                if self.since:
                    params["since"] = self.since

                # Verwende Event.wait für unterbrechbares Warten zwischen Requests
                resp = requests.get(self.server_url, params=params, timeout=self.timeout)

                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except ValueError:
                        data = []

                    if isinstance(data, list) and data:
                        # update since auf größtes timestamp-Feld falls vorhanden
                        try:
                            timestamps = [m.get("timestamp") for m in data if isinstance(m, dict) and m.get("timestamp")]
                            if timestamps:
                                self.since = max(timestamps)
                        except Exception:
                            pass

                        try:
                            self.on_new(data)
                        except Exception as e:
                            print("Poller: Callback-Fehler:", e)

                        # nach Erhalt von Nachrichten sofort ohne Backoff weitermachen
                        backoff = self.poll_interval
                        # kurze Pause, damit GUI nicht mit zu vielen Updates überflutet wird
                        if self._stop_event.wait(0.1):
                            break
                        continue
                    else:
                        # keine neuen Nachrichten -> normales Intervall
                        if self._stop_event.wait(self.poll_interval):
                            break
                        backoff = self.poll_interval
                else:
                    print(f"Poller: HTTP {resp.status_code}, retry in {max(self.poll_interval,5.0)}s")
                    if self._stop_event.wait(max(self.poll_interval, 5.0)):
                        break
                    backoff = min(MAX_BACKOFF, backoff * BACKOFF_FACTOR)
            except requests.RequestException as e:
                # Netzwerkfehler: exponentielles Backoff zwischen Versuchen
                print("Poller: Netzwerkfehler:", e, f"(retry in {backoff:.1f}s)")
                if self._stop_event.wait(backoff):
                    break
                backoff = min(MAX_BACKOFF, backoff * BACKOFF_FACTOR)
            except Exception as e:
                # unerwarteter Fehler: loggen und kurz warten
                print("Poller: Unerwarteter Fehler:", e)
                if self._stop_event.wait(self.poll_interval):
                    break
