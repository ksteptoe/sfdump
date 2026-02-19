# Security

This guide covers authentication, access control, and credential management for sfdump deployments.

---

## HR Viewer Password

The HR Viewer displays sensitive Contact records (employees and contractors). It is protected by a password that administrators configure on each database.

### How It Works

- The password is stored as a **SHA-256 hash** in the `viewer_config` table inside the SQLite database (`meta/sfdata.db`).
- The hash is checked client-side in the Streamlit viewer — the user enters the password and it is hashed and compared.
- If no password hash is stored, the HR Viewer is accessible without a password.
- The password protects the HR Viewer only. The Object Viewer and Finance Viewer are not password-protected.

### Setting a Password

Use `sfdump set-password` to add or change the password on a database.

**Auto-detect the latest export** (recommended):

```bash
sfdump set-password
```

This finds the most recent export in `./exports/` and sets the password on its `meta/sfdata.db`.

**Specify an export directory:**

```bash
sfdump set-password -d exports/export-2026-01-26
```

**Specify a database file directly:**

```bash
sfdump set-password --db /path/to/sfdata.db
```

You will be prompted to enter and confirm the password:

```
Password: ********
Repeat for confirmation: ********
Password set on exports/export-2026-01-26/meta/sfdata.db
```

### Changing a Password

Run `sfdump set-password` again on the same database. The new hash replaces the old one.

### Removing a Password

To make the HR Viewer accessible without a password:

```bash
sfdump set-password --remove
sfdump set-password --remove -d exports/export-2026-01-26
sfdump set-password --remove --db /path/to/sfdata.db
```

### Baking a Password at Build Time

When building (or rebuilding) the SQLite database, you can set the password in one step:

```bash
sfdump build-db --hr-password
```

This prompts for the password during the build and stores the hash in the newly created database. Useful for automated or scripted deployments where you rebuild the database regularly.

### Verifying a Password Is Set

You can inspect the database directly:

```bash
sqlite3 exports/export-2026-01-26/meta/sfdata.db \
  "SELECT value FROM viewer_config WHERE key = 'hr_password_hash';"
```

If a hash is returned, the HR Viewer is password-protected. An empty result means no password is configured.

### Security Considerations

- **The password hash is SHA-256** — this is a one-way hash; the plaintext password is not stored anywhere.
- **The database file is the single source of truth** — there are no environment variables, config files, or external services involved. Copying the database copies the password configuration.
- **Transport security** — the Streamlit viewer runs over HTTP by default. If you expose the viewer on a network, consider placing it behind a reverse proxy with HTTPS.
- **The password is not per-user** — all HR Viewer users share the same password. For user-level access control, use network-level restrictions.
- **Choose a strong password** — the hash is stored in a SQLite file that could be read by anyone with filesystem access to the database.

---

## Salesforce Credentials

sfdump authenticates to Salesforce using the **OAuth Client Credentials** flow. No username or password is needed — only the Connected App's Consumer Key and Consumer Secret.

### What You Need

| Credential | Environment Variable | Description |
|---|---|---|
| Consumer Key | `SF_CLIENT_ID` | From the Connected App in Salesforce Setup |
| Consumer Secret | `SF_CLIENT_SECRET` | From the same Connected App |
| Instance URL | `SF_LOGIN_URL` | Your Salesforce instance (e.g. `https://yourcompany.my.salesforce.com`) |

### Creating a Connected App

1. In Salesforce, go to **Setup > Apps > App Manager > New Connected App**
2. Enable **OAuth Settings**
3. Set the callback URL to `https://localhost` (not used for client_credentials, but required by Salesforce)
4. Select these OAuth scopes:
   - `api` — Access and manage your data
   - `refresh_token, offline_access` — Perform requests at any time
5. Save the app
6. Under **Manage** > **Edit Policies**:
   - Set **Permitted Users** to "Admin approved users are pre-authorized"
   - Set **IP Relaxation** to "Relax IP restrictions" (or configure trusted IP ranges)
7. Under **Manage** > **Profiles** or **Permission Sets**, assign the app to the appropriate user profile
8. Enable **Client Credentials Flow**:
   - Go to **Manage** > **Edit Policies**
   - Enable "Enable Client Credentials Flow"
   - Set the **Run As** user — this user's permissions determine what data sfdump can access

### Configuring sfdump

Run `sf setup` to create the `.env` file interactively:

```bash
sf setup
```

Or create the `.env` file manually:

```env
SF_AUTH_FLOW=client_credentials
SF_CLIENT_ID=3MVG9_YOUR_CONSUMER_KEY_HERE
SF_CLIENT_SECRET=YOUR_CONSUMER_SECRET_HERE
SF_LOGIN_URL=https://yourcompany.my.salesforce.com
```

### Testing the Connection

```bash
sf test
```

This authenticates and runs a test query. If it succeeds, sfdump is ready to export.

### Credential Security

- **Never commit `.env` to Git** — it is listed in `.gitignore` by default.
- **Restrict filesystem access** — the `.env` file contains the Consumer Secret in plaintext.
- **Use a dedicated Connected App** — create one specifically for sfdump rather than reusing an existing app.
- **Scope the Run As user** — the Connected App's Run As user determines what data sfdump can access. Use a user with read-only access to the objects you need.
- **Rotate the Consumer Secret** periodically — regenerate it in Salesforce Setup and update the `.env` file.

---

## Web Server OAuth (Invoice PDFs)

Invoice PDFs are rendered by a Visualforce page in Salesforce and require a real user session, which the Client Credentials flow cannot provide. A separate **Web Server (Authorization Code + PKCE)** flow is used for invoice PDF downloads.

```bash
sfdump login-web          # Opens browser for SSO login
sf sins                   # Download invoice PDFs using the web session
```

The web session token is stored locally and used only for invoice PDF requests. All other sfdump operations use the Client Credentials flow.

---

## Network Access and Viewer Sharing

When you run `sf view`, the Streamlit viewer starts on `localhost:8501` by default. To share with other users on your network:

1. Note the **Network URL** shown when the viewer starts (e.g. `http://192.168.1.100:8501`)
2. Share this URL with users on the same network

For wider access, see the [Shared Network Drive](../user-guide/shared_network_drive.md) guide.

### Recommendations for Production Deployments

- **Use HTTPS** — place the Streamlit viewer behind a reverse proxy (nginx, Caddy, etc.) with TLS termination.
- **Restrict network access** — use firewall rules to limit who can reach the viewer port.
- **Run as a service** — on Linux, create a systemd unit; on Windows, use Task Scheduler or a service wrapper.
- **Separate the database from credentials** — the SQLite database can be copied to a read-only location for the viewer. The `.env` file is only needed for exports, not for viewing.
