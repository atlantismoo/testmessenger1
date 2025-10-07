import tkinter as tk
from tkinter import ttk
import threading
import uuid

from external_network import send_message, build_timestamp
from external_polling import Poller

# --------- CONFIG ----------
SERVER_URL = "http://127.0.0.1:8000"   # <-- Server-IP:PORT
ME = "user1"
PEER = "user2"
# --------------------------

def convo_id():
    a, b = sorted([ME, PEER])
    return f"{a}__{b}"

# ----------------- UI -----------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Simple 1:1 Messenger")
        self.geometry("700x480")

        # chat display
        self.txt = tk.Text(self, state="disabled", wrap="word")
        self.txt.pack(fill="both", expand=True, padx=6, pady=6)

        # input
        frm = ttk.Frame(self)
        frm.pack(fill="x", padx=6, pady=(0,6))
        self.var = tk.StringVar()
        ent = ttk.Entry(frm, textvariable=self.var)
        ent.pack(side="left", fill="x", expand=True)
        ent.bind("<Return>", self.send)
        btn = ttk.Button(frm, text="Send", command=self.send)
        btn.pack(side="right")

        # Poller (GET endpoint: SERVER_URL + "/messages")
        poll_url = SERVER_URL.rstrip("/") + "/messages"
        # Poller erwartet, dass der Server bei GET /messages?since=... eine Liste von Nachrichten
        # zurückgibt — hier behandeln wir empfangene Listen als kompletter oder inkrementeller Verlauf.
        self.poller = Poller(poll_url, on_new=self._on_new, since=None)
        self.poller.start()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def refresh(self, msgs):
        # msgs: Liste von Nachrichten (dicts) vom Server
        self.txt.config(state="normal")
        self.txt.delete("1.0", "end")
        for m in msgs:
            self.txt.insert("end", f"{m.get('from')} ({m.get('timestamp','')}) [{m.get('status','')}]\n{m.get('message')}\n\n")
        self.txt.config(state="disabled")
        self.txt.see("end")

    def send(self, event=None):
        text = self.var.get().strip()
        if not text:
            return
        msg = {
            "id": str(uuid.uuid4()),
            "from": ME,
            "to": PEER,
            "timestamp": build_timestamp(),
            "message": text,
            "status": "pending"
        }
        self.var.set("")
        # send in background
        threading.Thread(target=self._do_send, args=(msg,), daemon=True).start()

    def _do_send(self, msg):
        post_url = SERVER_URL.rstrip("/") + "/messages"
        ok, resp = send_message(post_url, msg["from"], msg["to"], msg["message"])
        # optional: Statushandling; hier nur Debug-Prints
        if not ok:
            print("Send failed:", resp)
        # kein lokales Store-Update mehr; rely auf Poller to fetch latest

    def _on_new(self, msgs):
        # Poller runs in background thread; marshal to main thread
        def handle():
            # Server liefert hier wahlweise komplette Konversation oder nur neue Nachrichten.
            # Für Einfachheit: sortiere nach timestamp und zeige alles an.
            try:
                if not isinstance(msgs, list):
                    return
                msgs_sorted = sorted(msgs, key=lambda x: x.get("timestamp",""))
                self.refresh(msgs_sorted)
            except Exception as e:
                print("Poller callback error:", e)
        self.after(0, handle)

    def on_close(self):
        try:
            self.poller.stop()
        except Exception:
            pass
        self.destroy()

# --------------- start ---------------
if __name__ == "__main__":
    app = App()
    app.mainloop()