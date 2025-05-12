# app.py
"""
Mini‑EHR demo (MCP‑secured)
──────────────────────────
Adds two security layers:
1. **Password‑protected tool calls** – every MCP resource must receive the user‑supplied password
   (the server should validate and raise an error on wrong creds).
2. **Minimal‑context filter for ChatGPT** – strips *all* personal identifiers and only passes the
   slices (info / vitals / medications / history) that the user’s question actually needs.

Usage:
$ streamlit run secure_mini_ehr_app.py

Prerequisites: `streamlit`, `openai`, `mcp`, and a running `mcp_server.py` that accepts a
`password` parameter in each tool.
"""

from __future__ import annotations

import atexit, asyncio, json, os, re, subprocess
from collections.abc import Iterable
from datetime import datetime, date
from typing import Any, Dict
import pandas as pd

import numpy as np  # noqa: F401 – MCP may return numpy scalars
import streamlit as st
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
# ───────────── Config ────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    st.error("Set OPENAI_API_KEY in your environment before launching the app.")
    st.stop()

client = OpenAI(api_key=OPENAI_API_KEY)
SERVER_CMD = ["python", "mcp_server.py"]
proc = subprocess.Popen(SERVER_CMD, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
atexit.register(lambda: proc.poll() is None and proc.terminate())

# ───────────── Helpers ───────────────────────────────────────────────────


def _unwrap(raw: Any, *, parse_json: bool = False):
    if hasattr(raw, "content") and raw.content:
        payloads = [getattr(t, "text", str(t)).strip() for t in raw.content]
    elif isinstance(raw, Iterable) and not isinstance(raw, (str, bytes)):
        payloads = [getattr(t, "text", str(t)).strip() for t in raw]
    else:
        payloads = re.findall(r"text='(.*?)'", str(raw), flags=re.S)
        payloads = [p.strip() for p in payloads]

    if parse_json:
        out: List[str | dict] = []
        for ch in payloads:
            if ch.lstrip().startswith("{") and ch.rstrip().endswith("}"):
                try:
                    out.append(json.loads(ch))
                    continue
                except json.JSONDecodeError:
                    pass
            out.append(ch)
        return out
    return payloads


def _call_tool(tool: str, **kwargs):
    async def _inner():
        async with stdio_client(
            StdioServerParameters(command="python", args=["mcp_server.py"])
        ) as (r, w):
            async with ClientSession(r, w) as sess:
                await sess.initialize()
                return await sess.call_tool(tool, kwargs)

    return asyncio.run(_inner())


def safe_call(tool: str, *, password: str, parse_json: bool = False, **kwargs):
    kwargs.setdefault("password", password)
    raw = _call_tool(tool, **kwargs)
    data = _unwrap(raw, parse_json=parse_json)

    if isinstance(data, list) and len(data) == 1:
        data = data[0]

    def _is_error(x):
        return isinstance(x, str) and x.startswith("Error executing tool")

    if _is_error(data) or (isinstance(data, list) and data and _is_error(data[0])):
        raise RuntimeError(data if isinstance(data, str) else data[0])
    return data


# ───────────── PII scrubbers ─────────────────────────────────────────────


def _age(dob: str | None) -> int | None:
    if not dob:
        return None
    try:
        birth = datetime.strptime(dob, "%Y-%m-%d").date()
        today = date.today()
        return (
            today.year
            - birth.year
            - ((today.month, today.day) < (birth.month, birth.day))
        )
    except ValueError:
        return None


def sanitized_info(full: Dict[str, Any]):
    return {
        k: v
        for k, v in {"age": _age(full.get("dob")), "sex": full.get("sex")}.items()
        if v is not None
    }


def build_ctx(query: str, *, info, vitals, meds, hx):
    q = query.lower()
    ctx: Dict[str, Any] = {}
    if any(w in q for w in ("age", "sex", "demograph")):
        ctx["info"] = info
    if any(w in q for w in ("vital", "bp", "heart", "temp", "weight")):
        ctx["vitals"] = vitals
    if any(w in q for w in ("med", "drug", "prescrip")):
        ctx["medications"] = meds
    if any(w in q for w in ("history", "surgery", "smok")):
        ctx["history"] = hx
    if not ctx:
        ctx["info"] = info
    return ctx


def show_table(obj: Any):
    if isinstance(obj, dict):
        st.table(pd.DataFrame([obj]))
    elif isinstance(obj, list):
        try:
            st.table(pd.DataFrame(obj))
        except ValueError:  # list of primitives
            st.write(obj)
    else:
        st.write(obj)


# ───────────── UI ────────────────────────────────────────────────────────

st.set_page_config(page_title="Mini‑EHR (secure)", layout="wide")
st.title("🔒 Mini‑EHR demo (MCP‑secured)")

password = st.sidebar.text_input(
    "Password", type="password", help="Example: doctor_secret"
)
if not password:
    st.stop()

try:
    patients = safe_call("list_patients", password=password)
except RuntimeError as e:
    st.error(e)
    st.stop()

pid = st.sidebar.selectbox("Select patient", patients)
if not pid:
    st.stop()

try:
    full_info = safe_call(
        "get_patient_info", password=password, patient_id=pid, parse_json=True
    )
    vitals = safe_call("get_vitals", password=password, patient_id=pid, parse_json=True)
    meds = safe_call(
        "get_medications", password=password, patient_id=pid, parse_json=True
    )
    hx = safe_call("get_history", password=password, patient_id=pid, parse_json=True)
except RuntimeError as e:
    st.error(e)
    st.stop()

ui_tabs = st.tabs(["Demographics", "Vitals", "Medications", "History"])
with ui_tabs[0]:
    show_table(full_info)
with ui_tabs[1]:
    show_table(vitals)
with ui_tabs[2]:
    show_table(meds)
with ui_tabs[3]:
    show_table(hx)

clean_info = sanitized_info(full_info)

st.markdown("---")
st.subheader("Ask the AI about this patient (name & DOB withheld)")
question = st.text_input("Your question", placeholder="e.g. Any red flags?")
if st.button("Ask") and question:
    ctx = build_ctx(question, info=clean_info, vitals=vitals, meds=meds, hx=hx)
    messages = [
        {
            "role": "system",
            "content": """You are a clinical assistant supporting a doctor during a consultation. Your role is to provide medically accurate, evidence-backed suggestions strictly based on the PATIENT_CONTEXT provided.

            Your responsibilities include:

            Interpreting the patient’s demographic data, vitals, medication, and medical history.

            Identifying important clinical findings the doctor should consider.

            Suggesting relevant follow-up questions the doctor might ask the patient to clarify symptoms or uncover hidden risk factors.

            Recommending appropriate investigations or diagnostic tests, based on the current clinical picture.

            Offering evidence-backed differential diagnoses, and helping the doctor rule in/out possibilities based on data.

            Providing treatment options or next clinical steps, referencing current standards of care where applicable.

            ⚠️ Important constraints:

            Only use information contained in PATIENT_CONTEXT.

            If the data is insufficient to draw conclusions, clearly state so.

            Do not guess. Do not invent symptoms or conditions not explicitly supported by the data.

            Present suggestions clearly and concisely, grouping them by category (e.g., questions to ask the patient, investigations, possible diagnoses, treatment options).

            Always prioritize clinical safety and relevance.""",
        },
        {"role": "system", "content": f"PATIENT_CONTEXT = {json.dumps(ctx)}"},
        {"role": "user", "content": question},
    ]
    with st.spinner("Thinking…"):
        reply = client.chat.completions.create(
            model="gpt-4o", messages=messages, temperature=0.6
        )
    st.success(reply.choices[0].message.content)
