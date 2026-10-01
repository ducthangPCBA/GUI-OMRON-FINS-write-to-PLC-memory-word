import ipaddress
import threading
import tkinter as tk
from tkinter import ttk
from fins import FinsClient
from typing import List, Optional


def encode_binary_word(value: str) -> bytes:
    bits = value.strip()
    if len(bits) != 16 or any(bit not in "01" for bit in bits):
        raise ValueError("Giá trị phải gồm chính xác 16 ký tự 0 hoặc 1.")
    return int(bits, 2).to_bytes(2, byteorder="big")


def decode_binary_word(data: bytes) -> str:
    if len(data) != 2:
        raise ValueError(f"PLC trả về {len(data)} byte; cần đúng 2 byte cho một word.")
    return format(int.from_bytes(data, byteorder="big"), "016b")


class PlcWordTool:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("FINS Word Console")
        self.root.geometry("680x660")
        self.root.minsize(620, 620)
        self.root.configure(bg="#f2f4ef")

        self.ip_var = tk.StringVar(value="192.168.250.1")
        self.address_var = tk.StringVar(value="D0")
        self.bit_vars = [tk.IntVar(value=0) for _ in range(16)]
        self.bit_buttons: List[tk.Button] = []
        self.status_var = tk.StringVar(value="Sẵn sàng kết nối")
        self._build_ui()

    def _build_ui(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#f2f4ef")
        style.configure("TLabel", background="#f2f4ef", foreground="#25332f", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 23), foreground="#172722")
        style.configure("Hint.TLabel", foreground="#65736d", font=("Segoe UI", 9))
        style.configure("TEntry", padding=(10, 9), fieldbackground="#ffffff", font=("Consolas", 12))
        style.configure("Primary.TButton", font=("Segoe UI Semibold", 10), padding=(18, 11),
                        background="#176b58", foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", "#105541"), ("disabled", "#aebbb5")])
        style.configure("Secondary.TButton", font=("Segoe UI Semibold", 10), padding=(18, 11),
                        background="#e1e9e3", foreground="#174b3d")
        style.map("Secondary.TButton", background=[("active", "#d1ded5"), ("disabled", "#e6e9e6")])

        page = ttk.Frame(self.root, padding=(28, 20, 28, 18))
        page.pack(fill="both", expand=True)

        ttk.Label(page, text="FINS / WORD ACCESS", foreground="#17745d",
                  font=("Segoe UI Semibold", 9)).pack(anchor="w", pady=(0, 7))
        ttk.Label(page, text="PLC Read / Write", style="Title.TLabel").pack(anchor="w")
        ttk.Label(page, text="Đọc hoặc ghi một word 16-bit qua FINS.", style="Hint.TLabel").pack(
            anchor="w", pady=(4, 14))

        connection = ttk.Frame(page)
        connection.pack(fill="x", pady=(0, 11))
        ttk.Label(connection, text="ĐỊA CHỈ IP PLC").grid(row=0, column=0, sticky="w", pady=(0, 7))
        ttk.Label(connection, text="ĐỊA CHỈ Ô NHỚ").grid(row=0, column=1, sticky="w", padx=(14, 0), pady=(0, 7))
        self.ip_entry = ttk.Entry(connection, textvariable=self.ip_var)
        self.ip_entry.grid(row=1, column=0, sticky="ew")
        self.address_entry = ttk.Entry(connection, textvariable=self.address_var)
        self.address_entry.grid(row=1, column=1, sticky="ew", padx=(14, 0))
        connection.columnconfigure(0, weight=3)
        connection.columnconfigure(1, weight=2)
        ttk.Label(page, text="Ví dụ địa chỉ: D0, W10, H2, CIO100").pack(anchor="w", pady=(0, 14))

        ttk.Label(page, text="GIÁ TRỊ WORD · 16 BIT").pack(anchor="w", pady=(0, 5))
        bit_grid = ttk.Frame(page)
        bit_grid.pack(fill="x", pady=(0, 7))
        for bit_index in range(15, -1, -1):
            row = 0 if bit_index >= 8 else 1
            column = 15 - bit_index if bit_index >= 8 else 7 - bit_index
            cell = ttk.Frame(bit_grid)
            cell.grid(row=row, column=column, padx=3, pady=2, sticky="ew")
            ttk.Label(cell, text=f"BIT {bit_index}", style="Hint.TLabel").pack(pady=(0, 2))
            button = tk.Button(
                cell,
                text="0",
                width=4,
                height=1,
                font=("Consolas", 13, "bold"),
                relief="flat",
                bd=0,
                cursor="hand2",
                command=lambda index=bit_index: self._toggle_bit(index),
            )
            button.pack(fill="x")
            self.bit_buttons.append(button)
            self._paint_bit(bit_index)
        for column in range(8):
            bit_grid.columnconfigure(column, weight=1, uniform="bit")

        ttk.Label(page, text="Bấm từng ô để đổi 0/1. Read sẽ cập nhật trạng thái bit từ PLC.",
                  style="Hint.TLabel").pack(anchor="w", pady=(2, 12))

        actions = ttk.Frame(page)
        actions.pack(fill="x")
        self.read_button = ttk.Button(actions, text="Read  ↑", style="Secondary.TButton",
                                      command=lambda: self._start_operation("read"))
        self.read_button.pack(side="left", fill="x", expand=True, padx=(0, 7))
        self.write_button = ttk.Button(actions, text="Write  ↓", style="Primary.TButton",
                                       command=lambda: self._start_operation("write"))
        self.write_button.pack(side="left", fill="x", expand=True, padx=(7, 0))

        ttk.Separator(page).pack(fill="x", pady=(16, 10))
        ttk.Label(page, textvariable=self.status_var, wraplength=540).pack(anchor="w")
        ttk.Label(page, text="FINS mặc định · cổng 9600", style="Hint.TLabel").pack(anchor="w", pady=(5, 0))

        self.root.bind("<Return>", lambda _event: self._start_operation("read"))

    def _start_operation(self, action: str) -> None:
        host = self.ip_var.get().strip()
        address = self.address_var.get().strip()
        try:
            ipaddress.ip_address(host)
            if not address:
                raise ValueError("Hãy nhập địa chỉ ô nhớ, ví dụ D0.")
            payload = encode_binary_word(self._get_bit_string()) if action == "write" else None
        except ValueError as error:
            self.status_var.set(str(error))
            return

        self._set_busy(True)
        verb = "Đang đọc" if action == "read" else "Đang ghi"
        self.status_var.set(f"{verb} {address} trên {host}…")
        threading.Thread(target=self._run_operation, args=(action, host, address, payload), daemon=True).start()

    def _run_operation(self, action: str, host: str, address: str, payload: Optional[bytes]) -> None:
        result: Optional[str] = None
        error_text: Optional[str] = None
        client = None
        try:
            client = FinsClient(host=host, port=9600)
            client.connect()
            if action == "read":
                response = client.memory_area_read(address)
            else:
                response = client.memory_area_write(address, payload)
            if not response.ok:
                raise RuntimeError(response.status_text or f"FINS response code: {response.code!r}")
            if action == "read":
                result = decode_binary_word(bytes(response.data))
        except Exception as error:
            error_text = str(error) or error.__class__.__name__
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
        self.root.after(0, self._finish_operation, action, address, result, error_text)

    def _finish_operation(self, action: str, address: str, result: Optional[str],
                          error_text: Optional[str]) -> None:
        self._set_busy(False)
        if error_text:
            self.status_var.set(f"Thao tác thất bại: {error_text}")
        elif action == "read" and result is not None:
            self._set_bit_string(result)
            self.status_var.set(f"Đã đọc {address}: {result}")
        else:
            self.status_var.set(f"Đã ghi thành công {address}: {self._get_bit_string()}")

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.read_button.configure(state=state)
        self.write_button.configure(state=state)

    def _get_bit_string(self) -> str:
        return "".join(str(self.bit_vars[index].get()) for index in range(15, -1, -1))

    def _set_bit_string(self, bits: str) -> None:
        for index, bit in zip(range(15, -1, -1), bits):
            self.bit_vars[index].set(int(bit))
            self._paint_bit(index)

    def _toggle_bit(self, bit_index: int) -> None:
        self.bit_vars[bit_index].set(1 - self.bit_vars[bit_index].get())
        self._paint_bit(bit_index)

    def _paint_bit(self, bit_index: int) -> None:
        button = self.bit_buttons[15 - bit_index]
        is_on = self.bit_vars[bit_index].get() == 1
        button.configure(
            text=str(self.bit_vars[bit_index].get()),
            bg="#176b58" if is_on else "#e1e9e3",
            fg="#ffffff" if is_on else "#294139",
            activebackground="#105541" if is_on else "#d1ded5",
            activeforeground="#ffffff" if is_on else "#174b3d",
        )


if __name__ == "__main__":
    window = tk.Tk()
    PlcWordTool(window)
    window.mainloop()