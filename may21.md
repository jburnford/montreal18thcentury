# Extending the Montreal 1725 LOD Dataset
## Work Log — May 21, 2026

This document records a session of work extending the Montreal 1725 CIDOC-CRM
dataset toward LINCS publication. It picks up from the state left by the
April 16 workshop (`csv_to_cidoc.py` + `montreal1725.ttl`, 14,025 triples).

## 1. Starting Point and a Discarded Change

The session began with the repository carrying one uncommitted modification to
`leon/MTL1725_HISCO.csv`. Inspection of the diff showed it was entirely an
**Excel re-save artifact**:

- Two `numero_dt` cadastral values had been corrupted into dates
  (`4/5` → `5-Apr`, `6/7` → `7-Jun`)
- 18 DBC-link cells had been cosmetically wrapped in quotes

Nothing in the change was intentional, so it was discarded with
`git checkout` — the working tree returned to the clean committed state. (The
underlying hazard remains: opening this CSV in Excel corrupts cells like `4/5`.
Use LibreOffice Calc with the column set to "Text", or a plain text editor.)

## 2. Type Grounding for Streets

Two `crm:P2_has_type` assertions were added to the spatial model, each pointing
at an `crm:E55_Type` grounded directly to a Wikidata URI:

| Target | Type | Wikidata | Label |
|--------|------|----------|-------|
| Current street `E53_Place` (34 nodes) | street | `wd:Q79007` | "street" / "rue" |
| Historic street `E93_Presence` (34 nodes) | historic street | `wd:Q40365391` | "historic street" / "ancienne rue" |

Each QID was verified against the Wikidata API before use. The Wikidata URI is
used directly as the `E55_Type` and locally typed `a crm:E55_Type` — the
standard LINCS pattern of reusing an authority URI.

The `place/old-montreal` `E53_Place` correctly did **not** receive the street
type, and the lot `E93_Presence` nodes did not receive the historic-street type.

## 3. Type Grounding for Lots

Lots are dual-modeled (enduring `E18_Physical_Thing` + per-row `E93_Presence`).
Three new `E55_Type`s were added:

| Target | Type URI | Label |
|--------|----------|-------|
| Lot `E18` (439) | `wd:Q683595` | "land parcel" / "parcelle" |
| Lot `E18` (439) | `temp_lincs:terrier` | "land parcel defined by land register maintained by Society of Saint-Sulpice" |
| Lot `E93` presence (439) | `temp_lincs:historic_land_parcel` | "historic land parcel" |

This introduced the **`temp_lincs:` namespace** (`http://temp.lincsproject.ca/`)
for LINCS temporary IDs — placeholders to be swapped for permanent minted LINCS
URIs before final ingestion. Each `E18` lot now carries both `Q683595` and
`temp_lincs:terrier`; each `E93` lot presence carries `historic_land_parcel`.

## 4. Transfer-Mode Type Relabelling

Two of the five `transfer-mode` `E55_Type`s had opaque labels copied straight
from the CSV codes. They were given descriptive English labels:

| URI | Old label | New label |
|-----|-----------|-----------|
| `type/transfer-mode/s-m` | "s/m"@fr | "type of acquisition could not be determined"@en |
| `type/transfer-mode/n-a` | "n/a"@fr | "property that is outside of regular transaction"@en |

`achat`, `succession`, and `vente` kept their French labels. URIs and all
`E8_Acquisition` → `P2_has_type` references were untouched — only labels changed.

## 5. The Occupation Model

The largest addition: an occupation event for property-acquiring actors,
following the LINCS occupation pattern.

### Investigation

Before modeling, the CSV's occupation columns were analysed:

- **`occupation`** holds 11 broad categories (production, commerce,
  agriculture, …), not job titles.
- **`HISCO`** — despite the file name — holds only a **single HISCO
  major-group digit** (1, 4, 5, 6, 7, 9), not a full 5-digit code. It
  correlates 1:1 with `occupation`.
- Categories `other`, `unknown`, `religious institution`, and `state` carry
  no HISCO digit at all.

### Decisions (confirmed with the project lead)

| Question | Decision |
|----------|----------|
| Specific-occupation source | The HISCO major-group digit |
| Type URI scheme | `temp_lincs:` temporary IDs |
| Actors with no HISCO | Skipped — no occupation activity |
| HISCO type labels | Standard HISCO / ISCO-68 major-group names |
| Roi / Sulpicians | Full occupation activity, grounded to Wikidata |

### Structure

Each qualifying actor gets one `crm:E7_Activity`:

```turtle
<.../occupation/DES0031> a crm:E7_Activity ;
    rdfs:label "Occupation of Desautels dit Lapointe, Pierre (fils)" ;
    crm:P14_carried_out_by <.../person/DES0031> ;
    crm:P2_has_type event:OccupationEvent,
        temp_lincs:hisco_major_group_9 .
```

- `P14_carried_out_by` → the `E21_Person` (or `E74_Group`)
- `P2_has_type` → `event:OccupationEvent`
  (`http://id.lincsproject.ca/event/OccupationEvent`)
- `P2_has_type` → a specific-occupation `E55_Type`

Activities are built **once per actor** (deduplicated across acquisition rows),
not once per row.

### HISCO major-group types

One `temp_lincs:hisco_major_group_{digit}` `E55_Type` per digit present:

| Digit | Label |
|-------|-------|
| 1 | Professional, technical and related workers |
| 4 | Sales workers |
| 5 | Service workers |
| 6 | Agricultural, animal husbandry and forestry workers, fishermen and hunters |
| 7 | Production and related workers, transport equipment operators and labourers |
| 9 | **unskilled** (en) / **journalier** (fr) |

Digit 9 was initially given the standard HISCO name, which collides with
digit 7 (HISCO combines major groups 7/8/9). At the project lead's request it
was relabelled "unskilled" / "journalier" to keep production and unskilled
labour distinguishable.

### Exception actors

"Roi de France" and "Séminaire de Saint-Sulpice de Paris" — both `E74_Group` —
have no HISCO code. They were given full occupation activities grounded to
Wikidata concepts instead:

- Roi de France → `wd:Q3439798` (King of France and Navarre)
- Séminaire de Saint-Sulpice → `wd:Q522379` (Society of Saint-Sulpice)

### Result

**266 occupation activities** created (98 of 365 actors skipped for lack of
occupation data); 9 new `E55_Type`s (OccupationEvent, 6 HISCO groups, 2
exception concepts).

## 6. Source Data Corrections

The per-actor occupation pass flagged two actors with inconsistent occupation
coding across their rows. The project lead supplied the corrections:

| Actor | Rows | Correction |
|-------|------|------------|
| Dudevoir, Claude (`DUD0001`) | id 373 | `admin/officers`,HISCO `1` → `commerce`,HISCO `4` |
| Payet, Marguerite | id 219, 222, 408, 418 | occupation → `unknown`; HISCO `7` → blank |

The corrections were applied in **both** places:

1. **`leon/MTL1725_HISCO.csv`** — 5 lines edited directly, preserving the
   file's CRLF line endings and UTF-8 encoding.
2. **`csv_to_cidoc.py`** — a documented `ROW_CORRECTIONS` map, applied during
   CSV cleaning and logged like the existing date/dedup fixes. It is idempotent
   (silent when the CSV already matches) and keeps the conversion correct if
   the source file is ever re-supplied by the provider.

Effect: Dudevoir's occupation activity now uses HISCO 4 (Sales workers);
Payet, Marguerite — now occupation `unknown` with no HISCO — receives no
occupation activity. Occupation activities dropped 267 → 266.

## 7. LINCS Compliance Validation

The output was validated against the LINCS application profile across all
applicable categories. The Turtle parses cleanly (16,774 triples, 0 errors).

**Result: 6 PASS, 4 WARN, 1 FAIL.**

### PASS

- **Namespaces** — all 16 properties and 12 classes are valid CRM; no invented
  properties
- **Structure** — all 3,543 typed entities have `rdfs:label` + `rdf:type`; all
  604 `E33_E41`/`E42` nodes have `P190_has_symbolic_content`
- **Temporal datatypes** — 878/878 `P82a`/`P82b` are `xsd:dateTime`; no
  time-span missing begin/end
- **Event-centric** — occupations correctly modeled as `E7_Activity` +
  `event:OccupationEvent`
- **Referential integrity** — 0 dangling URIs, 0 untyped local subjects
- **No blank nodes** — every intermediate node has a minted URI

### WARN

- **Label language tags** — 2,700 of 3,550 `rdfs:label`s lack a language tag
- **P82 datatype** — acquisition time-spans type `P82` as `xsd:date`/`xsd:gYear`;
  LINCS expects a human-readable `xsd:string`
- **Transfer-mode types** — 5 `E55_Type`s still use internal `mtl1725:` URIs
- **Geometry modeling** — 463 geometries attach as plain literals via
  `P169i_spacetime_volume_is_defined_by` (whose range is `E95_Spacetime_Primitive`,
  not a literal); LINCS's documented pattern is `P168` on `E53_Place`. Needs a
  LINCS modeling decision. Coordinate order is correct (lon lat) and the
  literals are not `geo:wktLiteral`, so the hard FAIL trigger is avoided.

### FAIL

- **Authority URIs** — 342 `E21_Person`, 23 `E74_Group`, 35 `E53_Place` carry
  **no `owl:sameAs`** to external authorities. LINCS requires VIAF/Wikidata for
  people and GeoNames for places. The dataset holds the raw material (DBC
  links, remparts.info IDs, toponymie references) but none is a resolvable
  authority URI link.

## 8. Final Output

`montreal1725.ttl` — **16,774 triples** (up from 14,025).

| CRM Class | Count |
|-----------|-------|
| E52_Time-Span | 878 |
| E93_Presence | 473 |
| E8_Acquisition | 439 |
| E18_Physical_Thing | 439 |
| E33_E41_Linguistic_Appellation | 365 |
| E21_Person | 342 |
| E7_Activity | 266 |
| E42_Identifier | 239 |
| E53_Place | 35 |
| E73_Information_Object | 25 |
| E74_Group | 23 |
| E55_Type | 19 |

New namespaces this session: `wd:` (`http://www.wikidata.org/entity/`),
`temp_lincs:` (`http://temp.lincsproject.ca/`),
`event:` (`http://id.lincsproject.ca/event/`).

All work was committed (`13980af`) and pushed to
`git@github.com:jburnford/montreal18thcentury.git`.

## 9. Outstanding Next Steps

Toward LINCS ingestion, in priority order:

1. **Ground persons and places to external authorities** (the one FAIL) —
   Wikidata/VIAF for persons (the ~22 with DBC entries first), GeoNames for
   streets. Use the WikidataMCP vector search for disambiguation.
2. **Add language tags** to the 2,700 untagged labels.
3. **Resolve the geometry modeling question** with the LINCS contact —
   `P169i` + minted `E95_Spacetime_Primitive` node, or `P168` projection onto
   the `E53` streets.
4. **Ground or relabel** the 5 internal transfer-mode types.
5. **Add dataset-level metadata** — a `void:Dataset` / `dcterms` block with
   attribution to Léon Robichaud, a license, and a named-graph URI.
6. **Swap `temp_lincs:` placeholders** (`terrier`, `historic_land_parcel`, the
   HISCO major groups) for permanent minted LINCS URIs.
