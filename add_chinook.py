from core.connection_manager import test_new_connection, add_connection

config = {
    "host": "localhost",
    "port": 5432,
    "username": "ayonaryan",
    "password": "",
    "database": "chinook"
}

print("Testing connection:", test_new_connection("postgresql", config))
print("Adding connection:", add_connection("Chinook", "postgresql", config))
