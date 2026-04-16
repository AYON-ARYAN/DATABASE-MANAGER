"""
Redis Adapter
Uses redis-py. LLM generates Redis commands.
Schema is inferred by scanning key patterns and types.
"""

import json
from core.adapters.base import DatabaseAdapter


class RedisAdapter(DatabaseAdapter):

    @property
    def dialect(self):
        return "redis"

    @property
    def is_nosql(self):
        return True

    # --------------------------------------------------
    # Connection
    # --------------------------------------------------
    def connect(self):
        import redis as redis_lib
        self._client = redis_lib.Redis(
            host=self.config.get("host", "localhost"),
            port=int(self.config.get("port", 6379)),
            password=self.config.get("password", "") or None,
            db=int(self.config.get("db_number", 0)),
            decode_responses=True,
            socket_timeout=5,
        )

    def disconnect(self):
        if hasattr(self, "_client") and self._client:
            self._client.close()
            self._client = None

    def test_connection(self) -> bool:
        try:
            self.connect()
            self._client.ping()
            self.disconnect()
            return True
        except Exception:
            return False

    # --------------------------------------------------
    # Schema (key patterns + types)
    # --------------------------------------------------
    def get_schema(self) -> str:
        self.connect()
        schema = "REDIS KEY SPACE:\n"

        # Sample up to 100 keys
        cursor, keys = self._client.scan(count=100)
        all_keys = list(keys)

        # Group by type
        type_map = {}
        for key in all_keys[:100]:
            ktype = self._client.type(key)
            if ktype not in type_map:
                type_map[ktype] = []
            type_map[ktype].append(key)

        for ktype, kkeys in type_map.items():
            schema += f"\n  TYPE: {ktype} ({len(kkeys)} keys sampled)\n"
            for k in kkeys[:10]:
                schema += f"    - {k}\n"
            if len(kkeys) > 10:
                schema += f"    ... and {len(kkeys) - 10} more\n"

        total = self._client.dbsize()
        schema += f"\n  TOTAL KEYS IN DB: {total}\n"

        self.disconnect()
        return schema

    def list_tables(self) -> list:
        """For Redis, 'tables' = key type groups."""
        self.connect()
        cursor, keys = self._client.scan(count=100)
        types = set()
        for key in keys:
            types.add(f"{self._client.type(key)}")
        self.disconnect()
        return sorted(types)

    # --------------------------------------------------
    # Execution
    # --------------------------------------------------
    def execute(self, query: str) -> tuple:
        """
        Expects the LLM to produce a JSON command like:
        {
            "command": "GET",
            "args": ["mykey"]
        }

        Or for multi-step:
        {
            "commands": [
                {"command": "SET", "args": ["key1", "value1"]},
                {"command": "GET", "args": ["key1"]}
            ]
        }
        """
        self.connect()

        try:
            cmd = json.loads(query)
        except json.JSONDecodeError:
            # Fallback: treat as raw Redis command string
            parts = query.strip().split()
            cmd = {"command": parts[0], "args": parts[1:]}

        results_columns = []
        results_rows = []

        if "commands" in cmd:
            # Multi-command
            for step in cmd["commands"]:
                command = step.get("command", "").upper()
                args = step.get("args", [])
                result = self._client.execute_command(command, *args)
                results_rows.append([command, str(result)])
            results_columns = ["command", "result"]
        else:
            command = cmd.get("command", "").upper()
            args = cmd.get("args", [])
            result = self._client.execute_command(command, *args)

            # Format result based on type
            if isinstance(result, list):
                results_columns = ["index", "value"]
                results_rows = [[i, str(v)] for i, v in enumerate(result)]
            elif isinstance(result, dict):
                results_columns = ["key", "value"]
                results_rows = [[str(k), str(v)] for k, v in result.items()]
            elif isinstance(result, set):
                results_columns = ["member"]
                results_rows = [[str(v)] for v in result]
            else:
                results_columns = ["result"]
                results_rows = [[str(result)]]

        self.disconnect()
        return results_columns, results_rows

    # --------------------------------------------------
    # Safety
    # --------------------------------------------------
    def preview_delete(self, query: str):
        try:
            cmd = json.loads(query)
        except json.JSONDecodeError:
            return None

        command = cmd.get("command", "").upper()
        if command not in ("DEL", "UNLINK", "FLUSHDB", "FLUSHALL"):
            return None

        if command in ("FLUSHDB", "FLUSHALL"):
            self.connect()
            count = self._client.dbsize()
            self.disconnect()
            return count

        # DEL / UNLINK — count the keys
        args = cmd.get("args", [])
        self.connect()
        count = sum(1 for k in args if self._client.exists(k))
        self.disconnect()
        return count
