# 🤖 AI Database Manager (Local LLM Powered)

AI Database Manager is a local, AI-powered tool that allows users to interact with a SQLite database using **natural language commands**.

Instead of writing SQL manually, users describe what they want to do (read, insert, update, delete data), review the generated SQL, and execute it safely through a web interface.

The system runs **fully offline** using a locally hosted LLM (Ollama + Mistral) and focuses on **safety, correctness, and usability**.

---

## ✨ Key Features

- Natural language → SQL using a **local LLM (Ollama)**
- Human-in-the-loop SQL review before execution
- Full CRUD support (SELECT, INSERT, UPDATE, DELETE)
- Schema-aware SQL generation
- System-handled schema tasks (e.g. list tables)
- DELETE impact preview (row count before execution)
- Snapshot-based **Undo** for write operations
- Safe execution with validation and intent checks
- Clean, modern, Safari-compatible web UI
- Works fully **offline** (no cloud APIs)

---

## 🧠 How the Project Works

### High-Level Flow

1. **User enters a natural language command**  
   Example:  
```

Show first 5 customers

```

2. **System classifies the task**
- Schema tasks (e.g. list tables) are handled directly
- Data operations are sent to the LLM

3. **Local LLM generates SQL**
- The database schema is provided as context
- The LLM outputs a single SQL statement

4. **User reviews the generated SQL**
- SQL is shown on a dedicated review page
- Nothing executes automatically

5. **Execution with safety checks**
- SQL is validated
- Write operations trigger a database snapshot
- DELETE operations show affected row count

6. **Results are displayed**
- SELECT results are shown in a table
- Execution status is clearly displayed

7. **Undo support**
- The last write operation can be reverted using snapshots

---

## 🧱 System Architecture (Simplified)

```

User (Browser)
|
v
Flask Web App
|
+--> System Handlers (schema, safety)
|
+--> Local LLM (Ollama)
|
v
SQLite Database

```

---

## 🛠 Tech Stack

- **Backend:** Python, Flask
- **Database:** SQLite
- **LLM Runtime:** Ollama (Mistral model)
- **Frontend:** HTML + CSS (no frameworks)
- **OS Support:** Windows, macOS

---

## 📁 Project Structure

```

.
├── app.py
├── core/
│   ├── db.py
│   ├── llm.py
│   ├── validator.py
│   └── snapshot.py
├── templates/
│   ├── index.html
│   └── review.html
├── db/
│   └── main.db
└── README.md

```

---

## ⚙️ Setup Instructions

### 1️⃣ Prerequisites (Windows & macOS)

Make sure you have:

- Python **3.10+**
- Git
- Ollama installed

---

### 2️⃣ Install Ollama

#### macOS
Download and install from:
```

[https://ollama.com](https://ollama.com)

```

#### Windows
Download the Windows installer from:
```

[https://ollama.com](https://ollama.com)

````

After installation, verify:
```bash
ollama --version
````

---

### 3️⃣ Pull the LLM Model

Run:

```bash
ollama pull mistral
```

Start the Ollama server:

```bash
ollama serve
```

> Keep this running in the background.

---

### 4️⃣ Clone the Repository

```bash
git clone <your-repo-url>
cd ai-database-manager
```

---

### 5️⃣ Create a Python Virtual Environment

#### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

#### Windows (PowerShell)

```powershell
python -m venv venv
venv\Scripts\activate
```

---

### 6️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

> If you don’t have a `requirements.txt`, install manually:

```bash
pip install flask requests
```

---

### 7️⃣ Prepare the Database

Place your SQLite database file at:

```
db/main.db
```

You can use any SQLite database.
For testing, the **Chinook** sample database works well.

---

### 8️⃣ Run the Application

```bash
python app.py
```

You should see:

```
Running on http://127.0.0.1:5000/
```

Open that URL in your browser (Safari, Chrome, Edge supported).

---

## 🧪 Example Commands

```
List all tables
Show first 5 customers
Show invoices from Germany
Add a new customer named John Doe
Update phone number of customer with ID 5
Delete invoice with InvoiceId = 12
```

---

## 🛡 Safety Design

* SQL is **never executed automatically**
* Only one SQL statement is allowed
* Dangerous operations are blocked
* Write operations create snapshots
* Undo restores previous database state
* Schema visibility reduces hallucinations

---

## 🚧 Limitations

* Designed for SQLite (can be extended)
* LLM output may require human judgment
* Not intended for production databases
* No authentication (single-user prototype)

---

## 📌 Future Improvements

* Execution history & audit logs
* DELETE confirmation dialogs
* SQL diff preview for UPDATE
* Pagination & sorting
* Role-based access control

---

## 📜 License

This project is intended for **learning, experimentation, and prototyping**.

---

## 🙌 Acknowledgements

* Ollama for local LLM runtime
* Mistral model
* SQLite for lightweight database support

```

---

If you want next, I can:
- optimize this README for **recruiters**
- add **screenshots & diagrams**
- create a **requirements.txt**
- help you write a **resume bullet point** for this project

Just tell me on ayonaryan5@gmail.com
```
