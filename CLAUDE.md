# Montreal 18th-Century Property Data — CIDOC-CRM Transformation

## Project Goal

Transform Léon Robichaud's Montreal 1725 property-ownership dataset into CIDOC-CRM Linked Open Data (RDF/Turtle). The source data documents land lots and their owners based on the Sulpician Seminary's second *terrier* (land register).

## Repository

- **GitHub**: `git@github.com:jburnford/montreal18thcentury.git`
- **Local**: `/home/jic823/montreal18thcentury`

## Source Data

All source files are in `leon/`:

| File | Description |
|------|-------------|
| `MTL1725_HISCO.csv` | 443 property-ownership records (UTF-8, CRLF line endings) |
| `Datadic.txt` | English field descriptions |
| `data_info.docx` | Extended documentation (French) |
| `rempa3_adhemarddm_table_PARCELLE.ods` | Parcelle table from ADHÉMAR/Remparts database |
| `Lots_1725_EPSG32188_SCHEMA.zip` | GIS shapefile (EPSG:32188 / NAD83 MTM zone 8) |

**Encoding note**: The CSV is valid UTF-8. Excel may mangle French accents when opening it (displays é as Ã©). This is an Excel problem, not a data problem.

### Key Fields (CSV)

- `id` — unique row identifier
- `numero_dt` — cadastral number (Sulpician terrier)
- `rue_devant` — street the lot fronts onto
- `proprietai` — owner name
- `acquisitio` / `dispositio` — start/end dates of ownership (YYYY/MM/DD)
- `mode_acqui` / `mode_dispo` — mode of acquisition/disposition (achat, succession, vente, concession, s/m)
- `origine` — ethnic origin (FR = French, C = Canadian)
- `occupation` — occupational category (commerce, production, agriculture, service, admin/officers, other, unknown)
- `HISCO` — HISCO occupational classification code
- `sexe` — M, F, or n/a
- `type_propr` — individual, organisation, or succession (estate of deceased)
- `DBC` — Dictionary of Canadian Biography link (when applicable)
- `ind-id` — individual identifier linking to remparts.info
- `url-ind-id` — base URL for remparts.info biographical pages

## CIDOC-CRM Data Model

### Skills

Always load the `cidoc-crm` skill before modeling work. Also consult `lincs-profile` and `lincs-validate` when checking LINCS compatibility.

### Namespace

Use `http://montreal1725.lincsproject.ca/` as the project namespace (prefix: `mtl1725:`).

### Spatial Model (from whiteboard — IMG_6399.jpg)

```
Lot (E93_Presence)
  --P10_falls_within--> Historic Street (E93_Presence)
    --P168_place_is_defined_by--> line geometry
    --P161_has_spatial_projection--> Current Street (E53_Place)
      --P89_falls_within--> Old Montreal (E53_Place)
  --P167_was_within--> Old Montreal (E53_Place)  [possibly redundant/inferred]
```

- **Lots** and **historic streets** are E93_Presence (spacetime volumes — places at a specific time, 1725)
- **Current streets** and **Old Montreal** are E53_Place (enduring spatial extents)
- Historic-to-current street mapping uses P161_has_spatial_projection

### Ownership Model (under discussion)

Each CSV row records an ownership period: person held title to a lot between two dates.

**Current approach**: Two E8_Acquisition events per row:

1. **Incoming** (acquisition): P22_transferred_title_to the owner, P24_transferred_title_of the lot, typed by mode_acqui
2. **Outgoing** (disposition): P23_transferred_title_from the owner, P24_transferred_title_of the lot, typed by mode_dispo

**Open modeling questions** (not yet resolved):
- Whether to explicitly model ownership as E30_Right with P104_is_subject_to
- Whether P24 should point to the E53_Place (enduring lot) or E93_Presence (1725 lot)
- Deduplication strategy for shared transfer events (one person's disposition = another's acquisition)
- Vocabulary for modes of transfer: project SKOS vocab vs external authority (Wikidata/AAT)

### Person Model

- E21_Person identified by ind-id (remparts.info URI)
- E33_E41_Linguistic_Appellation for name (from `proprietai`)
- Occupation via E55_Type (HISCO code provides external grounding)
- Ethnic origin (FR/C) via E55_Type
- DBC link as owl:sameAs or P1_is_identified_by with E42_Identifier
- `type_propr` = "succession" means the entity is an estate of a deceased person, not a living individual — model differently

### External Authorities

| Domain | Authority | Example |
|--------|-----------|---------|
| Persons | remparts.info | `https://remparts.info/adhemar_php/bio18.php?I_NUMERO=` + ind-id |
| Persons | Dictionary of Canadian Biography | DBC field |
| Streets | Commission de toponymie du Québec | `https://toponymie.gouv.qc.ca/` |
| Occupations | HISCO | Codes in HISCO field |
| Entities | Wikidata | Use MCP vector search for disambiguation (see global CLAUDE.md) |

### Output Format

- RDF/Turtle (.ttl)
- Standard prefixes: `rdf:`, `rdfs:`, `owl:`, `xsd:`, `skos:`, `crm:`
- Every entity MUST have `rdfs:label`
- Dates route through E52_Time-Span with P82, P82a, P82b
- Places route through events, never directly on persons

## Development Notes

- This is a WSL environment; see global CLAUDE.md for package installation conventions
- The GIS shapefile contains WKT polygon geometries for each lot (EPSG:32188)
- CSV has CRLF line endings (Windows-origin)
