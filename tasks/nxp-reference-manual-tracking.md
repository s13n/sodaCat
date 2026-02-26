# Task: Track NXP reference manual revisions

**Goal**
Maintain an up-to-date local stash of NXP reference manuals in `docs/NXP/`,
track known-latest revisions in `svd/NXP/LPC.yaml`, and detect when newer
revisions are available.

**Context**
NXP distributes reference manuals as PDFs behind an authenticated download
portal. Their website uses Akamai bot protection that blocks plain HTTP
clients (curl, requests, wget). Revision metadata is only accessible via
JavaScript-rendered product pages. This means:
- Downloads must be done manually in a browser
- Automated revision checking requires a browser-engine fetch (e.g. WebFetch)
  or manual lookup — a standalone Python script cannot scrape NXP reliably
- We track known-latest revisions in the YAML config as a workaround

---

## Reference manual naming convention

Local PDFs in `docs/NXP/` follow this naming pattern:

```
UM11029 -- LPC84x (Rev. 1.7).pdf
```

Format: `{UM_NUMBER} -- {Description} (Rev. {X.Y}).pdf`

The UM number is the primary key linking local files to config entries.

---

## Phase 1 -- Identify reference manuals

### 1.1 Find UM numbers for each subfamily

Each NXP subfamily typically has one reference manual (User Manual). To find
the correct UM number:

1. Search for `site:nxp.com "LPC8xx" "user manual"` (substitute the subfamily)
2. Or browse the NXP product page for a representative chip
3. The UM number appears in the document title (e.g. "UM11029")

### 1.2 Determine download URLs

NXP download URLs follow this pattern:

```
https://www.nxp.com/webapp/Download?colCode=UM11029
```

These URLs require authentication — they redirect to a login page for
unauthenticated clients, but work in a browser with an active NXP session.

### 1.3 Record in config

Add `ref_manual` entries to each subfamily in `svd/NXP/LPC.yaml`:

```yaml
subfamilies:
  LPC84x:
    chips: [LPC844, LPC845]
    ref_manual:
      name: UM11029
      url: "https://www.nxp.com/webapp/Download?colCode=UM11029"
```

---

## Phase 2 -- Determine latest revisions

### 2.1 Check NXP product pages

Since NXP blocks plain HTTP, use a browser or browser-engine tool to visit
each manual's product page and extract the current revision and date.

The NXP document detail page URL pattern:

```
https://www.nxp.com/docs/en/user-guide/UM11029.pdf
```

Or search for the UM number on nxp.com and look for the revision in the
document metadata (typically shown as "Rev. X.Y — YYYY-MM-DD").

### 2.2 Record revision data

Add `rev` and `date` to each `ref_manual` entry:

```yaml
ref_manual:
  name: UM11029
  rev: "1.7"
  date: 2021-04-14
  url: "https://www.nxp.com/webapp/Download?colCode=UM11029"
```

The `rev` field must be quoted (YAML would otherwise parse `1.7` as a float).
The `date` field uses ISO 8601 format.

---

## Phase 3 -- Download manuals

### 3.1 Manual download

Log into nxp.com in a browser and download each manual using the
`webapp/Download` URL. Save to `docs/NXP/` using the naming convention:

```
UM11029 -- LPC84x (Rev. 1.7).pdf
```

### 3.2 Verify local stash

Run the check script to confirm everything is accounted for:

```bash
python3 tools/check_nxp_manuals.py
```

---

## Phase 4 -- Ongoing maintenance

### 4.1 Check for updates

Run the check script periodically:

```bash
python3 tools/check_nxp_manuals.py
```

Output categories:

| Category | Meaning | Action |
|----------|---------|--------|
| **UP TO DATE** | Local rev matches config rev | None |
| **UPDATE AVAILABLE** | Config rev > local file rev | Download newer revision |
| **MISSING** | In config but no local file | Download the manual |
| **UNTRACKED** | Local file not in any config | Add to config or remove |

Exit code: 0 if all current, 1 if updates or missing.

### 4.2 Update revision data

When a new revision is discovered (via browser check or community report):

1. Update `rev` and `date` in the `ref_manual` entry in `svd/NXP/LPC.yaml`
2. Run `python3 tools/check_nxp_manuals.py` — should show "UPDATE AVAILABLE"
3. Download the new revision manually
4. Rename the local file to match the new revision
5. Re-run the check script — should show "UP TO DATE"

### 4.3 Adding a new family

When adding a new NXP family (beyond LPC):

1. Create a new config file (e.g. `svd/NXP/Kinetis.yaml`)
2. Add `ref_manual` entries with UM numbers, URLs, revisions, and dates
3. Update `tools/check_nxp_manuals.py` to accept the new config via `--config`
   (or extend it to scan multiple configs)
4. Download manuals into `docs/NXP/`

---

## Known revision data (as of 2026-02)

| Subfamily | UM | Rev | Date | Coverage |
|-----------|------|-----|------|----------|
| LPC802 | UM11045 | 1.5 | 2021-03-22 | LPC802 |
| LPC804 | UM11065 | 1.4 | 2021-03-18 | LPC804 |
| LPC81x | UM10601 | 1.7 | 2021-05-27 | LPC810, LPC811, LPC812 |
| LPC82x | UM10800 | 1.4 | 2021-05-27 | LPC822, LPC824 |
| LPC83x | UM11021 | 1.1 | 2016-10-05 | LPC832, LPC834 |
| LPC84x | UM11029 | 1.7 | 2021-04-14 | LPC844, LPC845 |
| LPC86x | UM11607 | 3.1 | 2025-11-07 | LPC864, LPC865 |
| LPC540xx | UM11060 | 1.5 | 2019-11-25 | LPC540xx, LPC54S0xx |
| LPC5411x | UM10914 | 2.0 | 2018-05-09 | LPC54113, LPC54114 |
| LPC546xx | UM10912 | 2.4 | 2019-11-12 | LPC546xx |

---

## Reference

- Check script: `tools/check_nxp_manuals.py`
- Config file: `svd/NXP/LPC.yaml` (ref_manual entries under each subfamily)
- Local manual stash: `docs/NXP/`
- NXP download URL pattern: `https://www.nxp.com/webapp/Download?colCode={UM_NUMBER}`
