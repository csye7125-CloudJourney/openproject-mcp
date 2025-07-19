# OpenProject MCP Server

A Model Context Protocol (MCP) server that enables Claude to interact with OpenProject instances. This server provides tools for managing projects, work packages, and users through natural language conversations.

## Features

- **Project Management**: List projects, get project details
- **Work Package Management**: List, view, create work packages
- **User Management**: List users in the OpenProject instance
- **Simple & Lightweight**: Built with the official MCP Python SDK
- **Async Support**: Full async/await support for better performance

## Installation

### From source

```bash
git clone <repository-url>
cd openproject-mcp-server
pip install -e .
```

## Configuration

The server is configured using environment variables:

### Required Variables

- `OPENPROJECT_BASE_URL`: Your OpenProject instance URL (e.g., `https://openproject.example.com`)
- `OPENPROJECT_API_KEY`: Your OpenProject API key

### Optional Variables

- `OPENPROJECT_TIMEOUT`: Request timeout in seconds (default: 30)
- `OPENPROJECT_VERIFY_SSL`: Verify SSL certificates (default: true)
- `LOG_LEVEL`: Logging level (default: INFO)
- `LOG_FORMAT`: Log format - json or text (default: json)

## Usage

### With Claude Desktop

Add to your Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "openproject": {
      "command": "python",
      "args": ["-m", "openproject_mcp_server"],
      "env": {
        "OPENPROJECT_BASE_URL": "https://your-openproject.com",
        "OPENPROJECT_API_KEY": "your-api-key"
      }
    }
  }
}
```

### Standalone (for testing)

```bash
# Set environment variables
export OPENPROJECT_BASE_URL="https://your-openproject.com"
export OPENPROJECT_API_KEY="your-api-key"

# Run the server
python -m openproject_mcp_server
```

### Docker Deployment

#### Quick Start with Docker

```bash
# 1. Copy environment template
cp .env.docker .env

# 2. Edit .env with your OpenProject details
nano .env

# 3. Build and run
./docker-build.sh
docker-compose -f docker-compose.mcp-only.yml up -d
```

#### Docker Commands

```bash
# Build the image
docker build -t openproject-mcp-server:latest .

# Run with environment file
docker run --env-file .env openproject-mcp-server:latest

# Run with inline environment variables
docker run \
  -e OPENPROJECT_BASE_URL=https://your-openproject.com \
  -e OPENPROJECT_API_KEY=your-api-key \
  openproject-mcp-server:latest
```

#### Docker Compose Options

- `docker-compose.yml` - Complete setup with OpenProject + MCP Server
- `docker-compose.mcp-only.yml` - MCP Server only (for existing OpenProject)

See [DOCKER.md](DOCKER.md) for detailed Docker deployment guide.

## Available Tools

### Project Management

- **list_projects**: List all accessible projects with optional filtering
  - Optional filters: status, name (partial match)
- **get_project_details**: Get detailed information about a specific project
  - Required: project_id

### Work Package Management

- **list_work_packages**: List work packages with optional filtering
  - Optional: project_id, filters (assignee, status, type)
- **get_work_package**: Get detailed information about a specific work package
  - Required: work_package_id
- **create_work_package**: Create a new work package
  - Required: subject, project_id, type_id
  - Optional: description, assignee_id

### User Management

- **list_users**: List all users in the OpenProject instance

## Example Conversations with Claude

Once configured, you can ask Claude things like:

- "Show me all active projects"
- "What work packages are in project 5?"
- "Create a new task called 'Update documentation' in project 1 with type 1"
- "What's the status of work package 123?"
- "List all users in the system"

## Development

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd openproject-mcp-server

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .
black --check .
mypy .
```

### Project Structure

```
openproject-mcp-server/
├── src/openproject_mcp_server/
│   ├── __init__.py
│   ├── __main__.py        # Entry point
│   ├── server.py          # Main MCP server implementation
│   ├── api_client.py      # OpenProject API client
│   └── config.py          # Configuration management
├── tests/                 # Test suite
└── pyproject.toml        # Project configuration
```

## Security

- API keys are handled securely and never logged
- All inputs are validated to prevent injection attacks
- SSL certificate verification is enabled by default
- Simple error handling with user-friendly messages

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License.

## Changelog

### v0.1.0

- Initial release with official MCP Python SDK
- Complete project and work package management
- Async HTTP client with retry logic and rate limiting
- Comprehensive configuration management with Pydantic v2
- Input validation and security measures
- Structured logging with JSON support
- Graceful shutdown handling
- Comprehensive test suite (47 tests passing)
- Integration tests for full MCP workflow
- Docker containerization with multi-stage builds
- Docker Compose configurations for easy deployment
- Complete Docker deployment documentation