# Testing and diagnostics

## Run every automated test

On Windows PowerShell:

```powershell
.\test-all.ps1
```

The script creates isolated Python virtual environments when needed, runs both
Pytest suites, runs the Maven/JUnit suite, and validates `docker-compose.yml`.

The tests follow the practical Angry Tests rules used in this project:

- one final assertion per test;
- short tests focused on one observable failure;
- explicit, negatively worded assertion messages;
- hostile inputs instead of only happy paths;
- direct constructor arguments instead of hidden shared fixtures.

## Error response contract

Gateway failures use JSON and preserve the status returned by a Python service:

```json
{
  "error": "None of ['Дисциплины'] are in the columns",
  "status": 500
}
```

The web page reads `detail`, `error`, or `message` fields and displays the text
without interpreting it as HTML.

## Log files

Set `LOG_DIR` to choose the log folder. Docker Compose maps every service to the
repository-level `logs/` directory. Files are separated by service and purpose:

- `java-events.log` and `java-errors.log`;
- `python-engine-events.log` and `python-engine-errors.log`;
- `python-xml-engine-events.log` and `python-xml-engine-errors.log`.

Logs rotate at 10 MB. Event files contain INFO/WARN records; error files contain
ERROR records and stack traces.
