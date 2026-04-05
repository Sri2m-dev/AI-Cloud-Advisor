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
- DNS ipv4 Lookup: 20.207.73.85 (33 ms)
- DNS ipv6 Lookup: Error (32 ms): getaddrinfo ENOTFOUND api.github.com
- Proxy URL: None (1 ms)
- Electron fetch (configured): HTTP 200 (29 ms)
- Node.js https: HTTP 200 (109 ms)
- Node.js fetch: HTTP 200 (288 ms)

Connecting to https://api.githubcopilot.com/_ping:
- DNS ipv4 Lookup: 140.82.113.21 (64 ms)
- DNS ipv6 Lookup: Error (122 ms): getaddrinfo ENOTFOUND api.githubcopilot.com
- Proxy URL: None (2 ms)
- Electron fetch (configured): HTTP 200 (267 ms)
- Node.js https: HTTP 200 (882 ms)
- Node.js fetch: HTTP 200 (864 ms)

Connecting to https://copilot-proxy.githubusercontent.com/_ping:
- DNS ipv4 Lookup: 20.199.39.224 (89 ms)
- DNS ipv6 Lookup: Error (87 ms): getaddrinfo ENOTFOUND copilot-proxy.githubusercontent.com
- Proxy URL: None (4 ms)
- Electron fetch (configured): HTTP 200 (629 ms)
- Node.js https: HTTP 200 (691 ms)
- Node.js fetch: HTTP 200 (603 ms)

Connecting to https://mobile.events.data.microsoft.com: HTTP 404 (354 ms)
Connecting to https://dc.services.visualstudio.com: HTTP 404 (1254 ms)
Connecting to https://copilot-telemetry.githubusercontent.com/_ping: HTTP 200 (831 ms)
Connecting to https://copilot-telemetry.githubusercontent.com/_ping: HTTP 200 (899 ms)
Connecting to https://default.exp-tas.com: HTTP 400 (111 ms)

Number of system certificates: 91

## Documentation

In corporate networks: [Troubleshooting firewall settings for GitHub Copilot](https://docs.github.com/en/copilot/troubleshooting-github-copilot/troubleshooting-firewall-settings-for-github-copilot).