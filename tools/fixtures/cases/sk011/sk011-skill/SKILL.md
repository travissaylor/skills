---
name: sk011-skill
description: A fixture skill that names tailnet addresses in prose and in a fenced block, next to lookalikes that must stay quiet.
---

# Fixture

Reach the build box at 100.100.12.34 from any device on the tailnet.
Its dashboard is at https://devbox.example-tailnet.ts.net once Serve is on.
The last hop answers at 100.64.1.2.
Its IPv6 address is fd7a:115c:a1e0::1234 on the same tailnet.
Lookalikes stay quiet: 100.20.3.4, 100.128.0.1, 1100.64.1.2, v100.64.1.2, 100.64%.
Ranges and shared addresses stay quiet: 100.64.0.0/10, fd7a:115c:a1e0::/48, 100.100.100.100.
Names that only contain ts.net stay quiet: api.ts.net.example.org, *.ts.net, host.ts.network.

```bash
ssh dev@100.64.0.1
```
