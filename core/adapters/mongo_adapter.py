"""
MongoDB Adapter
Uses pymongo. LLM generates JSON-based MongoDB queries.
Schema is inferred by sampling documents from each collection.
"""

import json
from core.adapters.base import DatabaseAdapter


class MongoAdapter(DatabaseAdapter):

    @property
    def dialect(self):
        return "mongodb"

    @property
    def is_nosql(self):
        return True

    @property
    def supports_snapshot(self) -> bool:
        return True

    # --------------------------------------------------
    # Connection
    # --------------------------------------------------
    def connect(self):
        from pymongo import MongoClient

        host = self.config.get("host", "localhost")
        port = int(self.config.get("port", 27017))
        username = self.config.get("username", "")
        password = self.config.get("password", "")
        database = self.config.get("database", "test")

        if username and password:
            uri = f"mongodb://{username}:{password}@{host}:{port}/{database}"
        else:
            uri = f"mongodb://{host}:{port}/"

        self._client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        self._db = self._client[database]

    def disconnect(self):
        if hasattr(self, "_client") and self._client:
            self._client.close()
            self._client = None
            self._db = None

    def test_connection(self) -> bool:
        try:
            self.connect()
            self._client.admin.command("ping")
            self.disconnect()
            return True
        except Exception:
            return False

    # --------------------------------------------------
    # Schema (inferred from sampling)
    # --------------------------------------------------
    def get_schema(self) -> str:
        self.connect()
        collections = self._db.list_collection_names()
        schema = ""

        for coll_name in collections:
            schema += f"\nCOLLECTION {coll_name}:\n"
            # Sample up to 5 documents to infer fields
            sample = list(self._db[coll_name].find().limit(5))
            fields = set()
            for doc in sample:
                for key in doc.keys():
                    if key != "_id":
                        val = doc[key]
                        ftype = type(val).__name__
                        fields.add((key, ftype))

            for field_name, field_type in sorted(fields):
                schema += f"  - {field_name} ({field_type})\n"

            if not fields:
                schema += "  (empty collection)\n"

        self.disconnect()
        return schema

    def list_tables(self) -> list:
        self.connect()
        collections = self._db.list_collection_names()
        self.disconnect()
        return collections

    # --------------------------------------------------
    # Execution
    # --------------------------------------------------
    def execute(self, query: str) -> tuple:
        """
        Expects the LLM to produce a JSON query like:
        {
            "operation": "find",
            "collection": "users",
            "filter": {"age": {"$gt": 25}},
            "projection": {"name": 1, "age": 1},
            "limit": 50
        }

        Supported operations:
        - find, aggregate, count
        - insertOne, insertMany
        - updateOne, updateMany
        - deleteOne, deleteMany
        """
        self.connect()
        try:
            cmd = json.loads(query)
        except json.JSONDecodeError:
            self.disconnect()
            raise ValueError("Invalid MongoDB query JSON. Expected a JSON object.")

        operation = cmd.get("operation", "find")
        coll_name = cmd.get("collection", "")
        coll = self._db[coll_name]

        columns = []
        rows = []

        if operation == "find":
            filt = cmd.get("filter", {})
            proj = cmd.get("projection", None)
            limit = cmd.get("limit", 50)
            sort = cmd.get("sort", None)

            cursor = coll.find(filt, proj)
            if sort:
                cursor = cursor.sort(list(sort.items()))
            cursor = cursor.limit(limit)

            docs = list(cursor)
            if docs:
                columns = list(docs[0].keys())
                rows = [[str(doc.get(c, "")) for c in columns] for doc in docs]

        elif operation == "aggregate":
            pipeline = cmd.get("pipeline", [])
            docs = list(coll.aggregate(pipeline))
            if docs:
                columns = list(docs[0].keys())
                rows = [[str(doc.get(c, "")) for c in columns] for doc in docs]

        elif operation == "count":
            filt = cmd.get("filter", {})
            cnt = coll.count_documents(filt)
            columns = ["count"]
            rows = [[cnt]]

        elif operation == "insertOne":
            doc = cmd.get("document", {})
            result = coll.insert_one(doc)
            columns = ["inserted_id"]
            rows = [[str(result.inserted_id)]]

        elif operation == "insertMany":
            docs = cmd.get("documents", [])
            result = coll.insert_many(docs)
            columns = ["inserted_count"]
            rows = [[len(result.inserted_ids)]]

        elif operation == "updateOne":
            filt = cmd.get("filter", {})
            update = cmd.get("update", {})
            result = coll.update_one(filt, update)
            columns = ["matched", "modified"]
            rows = [[result.matched_count, result.modified_count]]

        elif operation == "updateMany":
            filt = cmd.get("filter", {})
            update = cmd.get("update", {})
            result = coll.update_many(filt, update)
            columns = ["matched", "modified"]
            rows = [[result.matched_count, result.modified_count]]

        elif operation == "deleteOne":
            filt = cmd.get("filter", {})
            result = coll.delete_one(filt)
            columns = ["deleted"]
            rows = [[result.deleted_count]]

        elif operation == "deleteMany":
            filt = cmd.get("filter", {})
            result = coll.delete_many(filt)
            columns = ["deleted"]
            rows = [[result.deleted_count]]

        else:
            self.disconnect()
            raise ValueError(f"Unsupported MongoDB operation: {operation}")

        self.disconnect()
        return columns, rows

    # --------------------------------------------------
    # Safety
    # --------------------------------------------------
    def preview_delete(self, query: str):
        try:
            cmd = json.loads(query)
        except json.JSONDecodeError:
            return None

        op = cmd.get("operation", "")
        if "delete" not in op.lower():
            return None

        self.connect()
        coll = self._db[cmd.get("collection", "")]
        filt = cmd.get("filter", {})
        count = coll.count_documents(filt)
        self.disconnect()
        return count

    # --------------------------------------------------
    # Snapshots
    # --------------------------------------------------
    def take_snapshot(self, filepath: str) -> bool:
        import subprocess
        try:
            host = self.config.get("host", "localhost")
            port = int(self.config.get("port", 27017))
            username = self.config.get("username", "")
            password = self.config.get("password", "")
            database = self.config.get("database", "test")

            if username and password:
                uri = f"mongodb://{username}:{password}@{host}:{port}/{database}"
            else:
                uri = f"mongodb://{host}:{port}/"

            cmd = [
                "mongodump",
                "--uri", uri,
                "--archive=" + filepath,
                "--gzip"
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return True
        except Exception:
            return False

    def restore_snapshot(self, filepath: str) -> bool:
        import subprocess
        try:
            host = self.config.get("host", "localhost")
            port = int(self.config.get("port", 27017))
            username = self.config.get("username", "")
            password = self.config.get("password", "")
            database = self.config.get("database", "test")

            if username and password:
                uri = f"mongodb://{username}:{password}@{host}:{port}/{database}"
            else:
                uri = f"mongodb://{host}:{port}/"

            cmd = [
                "mongorestore",
                "--uri", uri,
                "--archive=" + filepath,
                "--gzip",
                "--drop"
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return True
        except Exception:
            return False
