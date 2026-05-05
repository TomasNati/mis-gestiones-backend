#!/usr/bin/env python3
"""
backup_db.py
- Reads DATABASE_URL from .env (format: postgresql+psycopg2://user:pass@host:port/dbname?...) or fallbacks
- Best-effort ensures pg_dump exists (may require admin rights)
- Runs pg_dump with parsed values, using PGPASSWORD in the subprocess env (not CLI)

Usage: python backup_db.py
Put DATABASE_URL=postgresql+psycopg2://user:password@host:5432/dbname?sslmode=require in .env
"""

import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlparse, parse_qs, unquote

ENV_FILE = ".env"


def parse_env(path=ENV_FILE):
    env = {}
    if not os.path.exists(path):
        return env
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", line)
            if not m:
                continue
            k, v = m.group(1), m.group(2).strip()
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            v = re.split(r"\s+#", v, 1)[0].strip()
            env[k] = v
    return env


def parse_database_url(dburl):
    p = urlparse(dburl)
    user = unquote(p.username) if p.username else None
    password = unquote(p.password) if p.password else None
    host = p.hostname or "localhost"
    port = p.port or 5432
    db = p.path[1:] if p.path and p.path.startswith("/") else (p.path or None)
    query = parse_qs(p.query)
    return {"user": user, "password": password, "host": host, "port": port, "db": db, "query": query}


# Automatic installer removed. The script now validates pg_dump presence and errors if missing.
# Install instructions are provided separately.


def build_pg_dump_cmd(pg_dump_path, host, port, user, db, file_path):
    # Use connection parameters rather than embedding password on CLI
    return [
        pg_dump_path,
        "--host", str(host),
        "--port", str(port),
        "--username", str(user),
        "--dbname", str(db),
        "--file", str(file_path),
        "--format", "plain",
        "--verbose",
    ]


def main():
    env = parse_env()
    dburl = env.get("DATABASE_URL") or env.get("DATABASEURI") or env.get("DATABASE")

    parsed = {}
    if dburl:
        parsed = parse_database_url(dburl)
    else:
        parsed["host"] = env.get("DB_HOST") or env.get("PGHOST") or "localhost"
        parsed["port"] = int(env.get("DB_PORT") or env.get("PGPORT") or 5432)
        parsed["user"] = env.get("DB_USER") or env.get("PGUSER")
        parsed["password"] = env.get("DB_PASSWORD") or env.get("PGPASSWORD")
        parsed["db"] = env.get("DB_NAME") or env.get("PGDATABASE")

    missing = [k for k in ("user", "db", "host") if not parsed.get(k)]
    if missing:
        print("Missing required DB values:", ", ".join(missing))
        print("Ensure DATABASE_URL is present in .env or provide DB_USER, DB_NAME, DB_HOST.")
        sys.exit(2)

    pg_dump_path = shutil.which("pg_dump")
    if not pg_dump_path:
        print("pg_dump not found in PATH. Please install the PostgreSQL client (pg_dump) and ensure it's on PATH.")
        sys.exit(3)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"db-backup{ts}.sql"
    filepath = os.path.abspath(filename)

    cmd = build_pg_dump_cmd(pg_dump_path, parsed.get("host"), parsed.get("port", 5432), parsed.get("user"), parsed.get("db"), filepath)

    run_env = os.environ.copy()
    if parsed.get("password"):
        run_env["PGPASSWORD"] = parsed.get("password")

    print("Running: ", " ".join(shlex.quote(x) for x in cmd))
    try:
        res = subprocess.run(cmd, env=run_env)
        if res.returncode == 0:
            print("Backup completed:", filepath)
            sys.exit(0)
        else:
            print("pg_dump exited with code", res.returncode)
            sys.exit(res.returncode)
    except FileNotFoundError:
        print("pg_dump executable not found. Aborting.")
        sys.exit(5)
    except Exception as e:
        print("Error running pg_dump:", e)
        sys.exit(6)


if __name__ == "__main__":
    main()
