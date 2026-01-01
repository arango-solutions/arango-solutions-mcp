# Reasoner Pod

AI-powered reasoning engine with OpenCode integration for intelligent task execution.

---

## 📋 Prerequisites

### 1. OpenCode Setup (Windows)

#### Step 1: Install OpenCode
```bash
npm install -g opencode-ai
```

#### Step 2: Configure LLM Provider (OpenAI)
```bash
opencode auth login
```
Follow the prompts to authenticate with your OpenAI API key.

#### Step 3: Start OpenCode Server
```bash
opencode serve --hostname 0.0.0.0 --port 4099
```

**Verify it's running:**
```bash
curl http://localhost:4099/global/health
```

---

### 2. ArangoDB Setup

#### Run ArangoDB Instance
```bash
docker run -d \
  --name arangodb \
  -p 8529:8529 \
  -e ARANGO_ROOT_PASSWORD=test \
  arangodb:latest
```

**Verify it's running:**
```bash
curl http://localhost:8529/_api/version
```

**Access Web UI:**
- URL: http://localhost:8529
- Username: `root`
- Password: `test`

---

### 3. Docker & Docker Compose

Ensure Docker Desktop is installed and running on Windows.

---

## 🚀 Running Reasoner Pod

### Using Docker Compose

```bash
docker-compose up -d
```

This will:
- Build the Reasoner Pod container
- Start the service on port 8000
- Connect to OpenCode and ArangoDB

**Check if it's running:**
```bash
curl http://localhost:8000/health
```

### View Logs
```bash
docker-compose logs -f reasoner-pod
```

### Stop Service
```bash
docker-compose down
```

---

## 📡 API Usage Sequence

### Step 1: Register MCP Server (Optional but Recommended)

If you want to use database tools, register the ArangoDB MCP server:

**Endpoint:** `POST http://localhost:8000/mcp/register`

**Payload:**
```json
{
  "name": "arangodb",
  "config": {
    "type": "local",
    "command": [
      "docker",
      "run",
      "-i",
      "--rm",
      "--network", "host",
      "-e", "ARANGO_HOSTS=http://host.docker.internal:8529",
      "-e", "ARANGO_ROOT_USERNAME=root",
      "-e", "ARANGO_ROOT_PASSWORD=test",
      "-e", "ARANGO_DEFAULT_DB_NAME=_system",
      "arangodb/mcp-arangodb:latest"
    ],
    "enabled": true
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "MCP server 'arangodb' registered successfully",
  "server_name": "arangodb"
}
```

---

### Step 2: Create Job

**Endpoint:** `POST http://localhost:8000/jobs`

**Payload:**
```json
{
  "request": "list all collections"
}
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Job created and queued for processing"
}
```

**Save the `job_id` for the next step!**

---

### Step 3: Check Job Status

**Endpoint:** `GET http://localhost:8000/jobs/{job_id}`

**Replace `{job_id}` with the job ID from Step 2.**

**Example:**
```bash
curl http://localhost:8000/jobs/550e8400-e29b-41d4-a716-446655440000
```

**Response (after ~15 seconds):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "user_request": "list all collections",
  
  "plan": [
    "Connect to database",
    "List all collections",
    "Format results"
  ],
  
  "steps": [
    {
      "step_num": 1,
      "description": "Executed plan using OpenCode build agent with MCP tools",
      "tool_used": "opencode_build_agent",
      "result": "Found 2 collections: flights, airports",
      "duration_ms": 2082.88
    }
  ],
  
  "final_result": "Here are the available collections:\n\n- flights\n- airports",
  
  "created_at": "2026-01-01T12:00:00Z",
  "completed_at": "2026-01-01T12:00:15Z",
  "duration_seconds": 14.5,
  "progress_percentage": 100.0
}
```

**Job Statuses:**
- `pending` - Job queued, not started yet
- `planning` - Generating execution plan
- `executing` - Executing the plan
- `completed` - Job finished successfully ✅
- `failed` - Job failed with error ❌

**⏱️ Note:** Jobs typically take 10-20 seconds to complete. Poll the status endpoint every 3-5 seconds.

---

## 🧪 Quick Test

```bash
# 1. Register MCP (one-time setup)
curl -X POST http://localhost:8000/mcp/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "arangodb",
    "config": {
      "type": "local",
      "command": ["docker", "run", "-i", "--rm", "--network", "host", "-e", "ARANGO_HOSTS=http://host.docker.internal:8529", "-e", "ARANGO_ROOT_USERNAME=root", "-e", "ARANGO_ROOT_PASSWORD=test", "-e", "ARANGO_DEFAULT_DB_NAME=_system", "arangodb/mcp-arangodb:latest"],
      "enabled": true
    }
  }'

# 2. Create job
JOB_ID=$(curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"request": "list all collections"}' \
  | jq -r '.job_id')

echo "Job ID: $JOB_ID"

# 3. Wait a bit
sleep 15

# 4. Check status
curl http://localhost:8000/jobs/$JOB_ID | jq
```

---

## 📚 Additional API Endpoints

### Health Check
```bash
GET http://localhost:8000/health
```

### Readiness Check
```bash
GET http://localhost:8000/health/ready
```

### Job Statistics
```bash
GET http://localhost:8000/health/stats
```

### MCP Status
```bash
GET http://localhost:8000/mcp/status
```

### MCP Tools List
```bash
GET http://localhost:8000/mcp/tools
```

### Prometheus Metrics
```bash
GET http://localhost:8000/metrics
```

**Example metrics tracked:**
- Job counts by status (pending, completed, failed)
- Job duration by status
- Active jobs count
- API request counts and duration
- OpenCode request counts and duration

---

## 🔧 Configuration

Environment variables can be set in `.env` file or docker-compose.yml:

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Environment mode | `production` |
| `OPENCODE_BASE_URL` | OpenCode server URL | `http://host.docker.internal:4099` |
| `OPENCODE_PROVIDER` | LLM provider | `openai` |
| `OPENCODE_MODEL` | LLM model | `gpt-4o` |
| `LOG_LEVEL` | Logging level | `INFO` |

---

## 📁 Project Structure

```
reasoner_pod/
├── reasoner_pod/           # Main application code
│   ├── agents/            # Reasoning agents
│   │   └── reasoner.py    # Main reasoning logic
│   ├── api/               # FastAPI routes
│   │   ├── routes/        # API endpoints
│   │   │   ├── health.py  # Health & metrics
│   │   │   ├── jobs.py    # Job management
│   │   │   └── mcp.py     # MCP registration
│   │   └── schemas/       # Request/response models
│   ├── clients/           # External service clients
│   │   └── opencode.py    # OpenCode API client
│   ├── core/              # Core business logic
│   │   ├── job_store.py   # Job storage
│   │   ├── models.py      # Domain models
│   │   └── worker.py      # Background worker
│   ├── middleware/        # Request middleware
│   │   ├── error_handler.py
│   │   ├── logging.py
│   │   └── metrics.py
│   ├── utils/             # Utility functions
│   │   ├── docker.py
│   │   ├── logging.py
│   │   └── metrics.py
│   ├── config.py          # Configuration
│   ├── dependencies.py    # FastAPI dependencies
│   └── main.py            # Application entry point
├── docker-compose.yml     # Docker compose configuration
├── Dockerfile             # Container definition
├── requirements.txt       # Python dependencies (6 packages)
└── README.md              # This file
```

---

## 🐛 Troubleshooting

### OpenCode Connection Failed
```bash
# Check if OpenCode is running
curl http://localhost:4099/global/health

# Restart OpenCode
opencode serve --hostname 0.0.0.0 --port 4099
```

### ArangoDB Connection Failed
```bash
# Check if ArangoDB is running
docker ps | grep arangodb

# Restart ArangoDB
docker restart arangodb
```

### Reasoner Pod Logs
```bash
docker-compose logs -f reasoner-pod
```

### Job Stuck in "executing" Status
- Jobs take 10-20 seconds to complete
- Wait longer before checking status
- Check OpenCode logs for errors
- Verify MCP server is registered (if using database operations)

---

## 🛑 Stopping Services

```bash
# Stop Reasoner Pod
docker-compose down

# Stop ArangoDB
docker stop arangodb

# Stop OpenCode
# Press Ctrl+C in the terminal running OpenCode
```

---

## 📦 Dependencies

### System Requirements
- **Python 3.11+**
- **Docker & Docker Compose**
- **Node.js** (for OpenCode)

### External Services
- **OpenCode** (npm package) - LLM gateway
- **ArangoDB** (optional) - For database operations
- **OpenAI API Key** - For LLM access

### Python Packages (6 total)
- `fastapi` & `uvicorn` - Web framework
- `pydantic` & `pydantic-settings` - Data validation & config
- `httpx` - HTTP client for OpenCode
- `prometheus-client` - Metrics collection
- `python-json-logger` - Structured logging

---

## 📄 License

MIT License

---

## 🤝 Support

For issues or questions, check the logs:
```bash
docker-compose logs -f reasoner-pod
```

---

