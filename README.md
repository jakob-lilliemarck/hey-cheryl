## Development
1. `source ./.venv/bin/activate`
2. `python -m src.app`

## Deployments
You may need to allow nginx to access the service.
- `sudo setsebool -P httpd_can_network_connect 1`
