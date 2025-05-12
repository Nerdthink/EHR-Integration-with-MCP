# mcp_server.py
import sqlite3, json
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from mcp.server.fastmcp import FastMCP, Context

DB_PATH = "ehr.db"


# ── lifespan keeps one DB connection open ───────────────────────────────
@asynccontextmanager
async def lifespan(server) -> AsyncIterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


mcp = FastMCP("EHR‑Gateway", lifespan=lifespan)


# ── helpers ─────────────────────────────────────────────────────────────
def row_to_dict(cursor, row):
    return {d[0]: row[i] for i, d in enumerate(cursor.description)}


def run_q(conn, q, params=()):
    conn.row_factory = row_to_dict
    cur = conn.execute(q, params)
    return [dict(r) for r in cur.fetchall()]


# ── tools ───────────────────────────────────────────────────────────────
@mcp.tool(description="List all patient IDs")
def list_patients(ctx: Context) -> list[str]:
    conn = ctx.request_context.lifespan_context  # type: ignore
    return [r["id"] for r in run_q(conn, "SELECT id FROM patients")]


@mcp.tool(description="Get core demographics")
def get_patient_info(patient_id: str, ctx: Context) -> dict:
    conn = ctx.request_context.lifespan_context  # type: ignore
    rows = run_q(
        conn,
        "SELECT id, first_name, last_name, sex, dob FROM patients WHERE id=?",
        (patient_id,),
    )
    return rows[0] if rows else {}


@mcp.tool(description="Latest vitals (limit=3)")
def get_vitals(patient_id: str, ctx: Context, limit: int = 3) -> list[dict]:
    conn = ctx.request_context.lifespan_context  # type: ignore
    return run_q(
        conn,
        "SELECT taken, bp, hr, temp, weight_kg, blood_glucose_mmol_per_l FROM vitals "
        "WHERE patient_id=? ORDER BY taken DESC LIMIT ?",
        (patient_id, limit),
    )


@mcp.tool(description="Active medications")
def get_medications(patient_id: str, ctx: Context) -> list[dict]:
    conn = ctx.request_context.lifespan_context  # type: ignore
    return run_q(
        conn,
        "SELECT drug, dose, start, IFNULL(stop,'ongoing') AS stop "
        "FROM meds WHERE patient_id=?",
        (patient_id,),
    )


@mcp.tool(description="Problem / social / surgical history (limit=5)")
def get_history(patient_id: str, ctx: Context, limit: int = 5) -> list[dict]:
    conn = ctx.request_context.lifespan_context  # type: ignore
    return run_q(
        conn,
        "SELECT kind, details, recorded FROM history "
        "WHERE patient_id=? ORDER BY recorded DESC LIMIT ?",
        (patient_id, limit),
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
