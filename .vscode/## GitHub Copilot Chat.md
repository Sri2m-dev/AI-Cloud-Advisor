## GitHub Copilot Chat

- Extension: 0.42.3 (prod)
- VS Code: 1.114.0 (e7fb5e96c0730b9deb70b33781f98e2f35975036)
- OS: win32 10.0.26200 x64
- GitHub Account: srikanth2m-dev

## Network

User Settings:
```json
  "http.systemCertificatesNode": true,
  "github.copilot.advanced.debug.useElectronFetcher": true,
  "github.copilot.advanced.debug.useNodeFetcher": false,
  "github.copilot.advanced.debug.useNodeFetchFetcher": true
```

Connecting to https://api.github.com:
- DNS ipv4 Lookup: 20.207.73.85 (38 ms)
- DNS ipv6 Lookup: Error (61 ms): getaddrinfo ENOTFOUND api.github.com
- Proxy URL: None (1 ms)
- Electron fetch (configured): HTTP 200 (26 ms)
- Node.js https: HTTP 200 (88 ms)
- Node.js fetch: HTTP 200 (292 ms)

Connecting to https://api.githubcopilot.com/_ping:
- DNS ipv4 Lookup: 140.82.113.22 (59 ms)
- DNS ipv6 Lookup: Error (56 ms): getaddrinfo ENOTFOUND api.githubcopilot.com
- Proxy URL: None (8 ms)
- Electron fetch (configured): HTTP 200 (305 ms)
- Node.js https: HTTP 200 (928 ms)
- Node.js fetch: HTTP 200 (893 ms)

Connecting to https://copilot-proxy.githubusercontent.com/_ping:
- DNS ipv4 Lookup: 20.199.39.224 (31 ms)
- DNS ipv6 Lookup: Error (32 ms): getaddrinfo ENOTFOUND copilot-proxy.githubusercontent.com
- Proxy URL: None (2 ms)
- Electron fetch (configured): HTTP 200 (413 ms)
- Node.js https: HTTP 200 (548 ms)
- Node.js fetch: HTTP 200 (601 ms)

Connecting to https://mobile.events.data.microsoft.com: HTTP 404 (220 ms)
Connecting to https://dc.services.visualstudio.com: HTTP 404 (1117 ms)
Connecting to https://copilot-telemetry.githubusercontent.com/_ping: HTTP 200 (907 ms)
Connecting to https://copilot-telemetry.githubusercontent.com/_ping: HTTP 200 (842 ms)
Connecting to https://default.exp-tas.com: HTTP 400 (201 ms)

Number of system certificates: 91

## Documentation

In corporate networks: [Troubleshooting firewall settings for GitHub Copilot](https://docs.github.com/en/copilot/troubleshooting-github-copilot/troubleshooting-firewall-settings-for-github-copilot).