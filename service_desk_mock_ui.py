import tkinter as tk
from tkinter import scrolledtext
import threading
import json
import copy
import requests
import logging
import ast

logging.basicConfig(
    format="%(asctime)s  %(levelname)s  %(name)s: %(message)s",
    level=logging.INFO,       
    datefmt="%Y-%m-%d %H:%M:%S",
	force=True
)
logger = logging.getLogger(__name__)

class ChatClient:
	def __init__(self, root: tk.Tk, endpoint):
		self.root = root
		self.endpoint = endpoint
		self.root.title("Service Desk Mock UI")
		self.root.configure(bg="#1e1e1e")
		self.log = logging.getLogger(self.__class__.__name__)
		self.log.debug("UI initialised")

		self.history: list[dict[str, str]] = []

		self.chat = scrolledtext.ScrolledText(
			root,
			wrap="word",
			state="disabled",
			width=90,
			height=30,
			relief="flat",
			bg="#1e1e1e",
			fg="white",
			insertbackground="white",
			font=("Segoe UI", 12),
			highlightthickness=0,
		)
		self.chat.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

		self.chat.tag_config(
			"user",
			foreground="#80c8ff",
			justify="left",
			lmargin1=6, lmargin2=6, rmargin=120,
			spacing1=2, spacing3=2,
			font=("Segoe UI", 12, "bold"),
		)
		self.chat.tag_config(
			"agent",
			foreground="#dedede",
			justify="right",
			lmargin1=120, lmargin2=120, rmargin=6,
			spacing1=2, spacing3=2,
			font=("Segoe UI", 12),
		)
		
		entry_frame = tk.Frame(root, bg="#1e1e1e")
		entry_frame.pack(fill="x", padx=10, pady=(0, 10))

		self.entry = tk.Entry(
			entry_frame,
			bg="#2b2b2b", fg="white", insertbackground="white",
			relief="flat", font=("Segoe UI", 12)
		)
		self.entry.pack(side="left", fill="x", expand=True, ipady=6)
		self.entry.bind("<Return>", self._on_send)

		send_btn = tk.Button(
			entry_frame, text="Send", command=self._on_send,
			bg="#3a3a3a", fg="white",
			activebackground="#4a4a4a", activeforeground="white",
			relief="flat", padx=12, pady=6,
		)
		send_btn.pack(side="right", padx=(6, 0))

	def _on_send(self, event=None):
		text = self.entry.get().strip()
		if not text:
			return
		self.entry.delete(0, tk.END)
		self._append_line(f"User: {text}\n", "user")
		self.history.append({"role": "user", "content": text})
		self._send_payload({"messages": copy.deepcopy(self.history)})
	
	def _send_payload(self, payload: dict):
		threading.Thread(target=self._call_api, args=(payload,), daemon=True).start()

	def _call_api(self, payload):
		try:
			# print("here is the payload to the API")
			# print(payload)
			resp = requests.post(self.endpoint, json=payload, timeout=30)

			resp.raise_for_status()
			body_text = resp.text.strip()

			if resp.headers.get("content-type", "").startswith("application/json"):
				data = resp.json()
			else:
				try:
					data = json.loads(body_text)
				except Exception:
					try:
						data = ast.literal_eval(body_text)
					except Exception:
						data = {"content": body_text}
		except Exception as exc:
			data = {"content": f"[Error] {exc}"}

		# print("Here is the response from the API")
		# print(data)
		# print()
		# print()

		if not isinstance(data, dict):
			data = {"content": str(data)}

		self.root.after(0, lambda: self._handle_response(data))

	def _handle_response(self, resp: dict):
		content = resp.get("content", "")
		data_block = resp.get("data")

		if data_block and data_block.get("cmds"):
			self.log.debug(f"Needs user approval for command: {data_block}")
			self._append_line(f"Agent: {content}\n", "agent")
			self._render_approval_ui(resp)
		else:
			self._append_line(f"Agent: {content}\n", "agent")
			if content:
				self.history.append({"role": "assistant", "content": content})

	def _append_line(self, line: str, tag: str):
		self.chat.configure(state="normal")
		self.chat.insert(tk.END, line, tag)
		self.chat.configure(state="disabled")
		self.chat.yview(tk.END)

	def _render_approval_ui(self, resp: dict):
		self.chat.configure(state="normal")
		cmds = resp["data"]["cmds"]       
		self.chat.insert(tk.END, " ", "agent") 

		spacer = tk.Frame(self.chat, bg="#1e1e1e")
		spacer.grid_columnconfigure(0, weight=1)  

		inner = tk.Frame(spacer, bg="#1e1e1e")
		inner.grid(row=0, column=1, sticky="e")   

		cmd_vars = []                             
		for idx, cmd_obj in enumerate(cmds):
			var = tk.IntVar(value=0)            
			row = tk.Frame(inner, bg="#1e1e1e")
			row.pack(anchor="e", pady=2)

			tk.Radiobutton(row, text="Approve", variable=var, value=1,
						bg="#1e1e1e", fg="#198754", selectcolor="#1e1e1e",
						activebackground="#1e1e1e").pack(side="right", padx=4)
			tk.Radiobutton(row, text="Deny", variable=var, value=0,
						bg="#1e1e1e", fg="#dc3545", selectcolor="#1e1e1e",
						activebackground="#1e1e1e").pack(side="right", padx=4)
			tk.Label(row, text=f"{idx+1}. {cmd_obj['command']}", fg="#dedede",
					bg="#1e1e1e", font=("Segoe UI", 11)).pack(side="right", padx=6)

			cmd_vars.append((var, cmd_obj))
		
		submit_button = tk.Button(inner, text="Submit", bg="#3a3a3a", fg="white", relief="flat",
			activebackground="#4a4a4a", padx=12, pady=6,
			)
		
		submit_button.pack(anchor="e", pady=(6, 2))
		submit_button.configure(
			command=lambda: self._submit_cmds(resp=resp, cmd_vars=cmd_vars, submit_button=submit_button)
		)

		self.chat.window_create(tk.END, window=spacer)
		self.chat.insert(tk.END, "\n")
		self.chat.configure(state="disabled")
		self.chat.yview(tk.END)

	def _submit_cmds(self, resp: dict, cmd_vars, submit_button):
		new_data = {"cmds": []}
		decision_lines = []
		submit_button.config(state=tk.DISABLED)

		for var, cmd_obj in cmd_vars:
			choice = bool(var.get())
			cmd_obj = copy.deepcopy(cmd_obj)
			cmd_obj["execute"] = choice
			new_data["cmds"].append(cmd_obj)

			decision_lines.append(
				f"{'✓' if choice else '✗'} {cmd_obj['command']}"
			)

		self.history.append({"role": "user", "content": "", "data": new_data})

		self._send_payload({"messages": copy.deepcopy(self.history)})
		
def start_UI(endpoint = "http://localhost:8000/api/sendMessage"):
	root = tk.Tk()
	ChatClient(root, endpoint)
	root.mainloop()

if __name__ == "__main__":
	start_UI("http://localhost:8000/api/sendMessage")