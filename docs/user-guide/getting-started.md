# Getting Started

From zero to finding your first document in 10 minutes.

## 1. Install

Open PowerShell and paste:

```powershell
irm https://raw.githubusercontent.com/ksteptoe/sfdump/main/bootstrap.ps1 | iex
```

This downloads and installs everything you need.

## 2. Configure

Run the setup wizard:

```
sf setup
```

Enter your Salesforce credentials when prompted:

- Consumer Key (from Connected App)
- Consumer Secret (from Connected App)
- Username (your Salesforce email)
- Password + Security Token

## 3. Test

Verify your connection works:

```
sf test
```

Look for: **"Connection successful!"**

## 4. Export

Download everything from Salesforce:

```
sf dump
```

Wait for completion. This downloads all files and data.

When complete, you'll see a summary showing how many files were downloaded.

**Custom location:** To export to a specific folder:
```
sf dump -d /path/to/my-export
```

## 5. Find Documents

Launch the viewer:

```
sf view
```

Then:

1. Click the **Explorer** tab
2. Type a customer or project name in the search box
3. Click any document to preview it

Done! You can now find any document in your archive.

## Command Reference

| Command | What it does |
|---------|--------------|
| `sf setup` | Configure credentials |
| `sf test` | Verify connection |
| `sf dump` | Export everything |
| `sf view` | Browse your data |
| `sf status` | List available exports |

## Need Help?

- [Detailed Quickstart](quickstart.md) — Step-by-step with explanations
- [Finding Documents](finding_documents.md) — Search tips and techniques
- [FAQ](faq.md) — Common questions answered
