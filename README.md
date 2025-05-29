## Development
1. `source ./.venv/bin/activate`
2. `python -m src.app`

## Deployments
You may need to allow nginx to access the service.
- `sudo setsebool -P httpd_can_network_connect 1`

## cheryl.service
- `bash deploy/install_cheryl.sh`
- `systemctl start cheryl.service`
- `journalctl -u cheryl.service -f`

to temporarily change SELinux context of file:
- `sudo chcon -t etc_t /home/jakob/Projects/hey-cheryl/.env`
