# Creating the Montreal 1725 LOD Dataset
## Work Log - April 16, 2026

This document records the complete process of transforming Leon Robichaud's Montreal 1725 property-ownership dataset into a CIDOC-CRM Linked Open Data knowledge graph.

## 1. Setting Up the Repository

We started with a folder of source files provided by Leon Robichaud documenting land lots and their owners in Montreal circa 1725, based on the second *terrier* (land register) of the Sulpician Seminary.

### Source Files

| File | Description |
|------|-------------|
| `MTL1725_HISCO.csv` | 443 property-ownership records with owners, dates, occupations, HISCO codes |
| `Datadic.txt` | English data dictionary |
| `data_info.docx` | Extended documentation (French) |
| `rempa3_adhemarddm_table_PARCELLE.ods` | Parcelle table from the ADHEMAR/Remparts database |
| `Lots_1725_EPSG32188_SCHEMA.zip` | GIS shapefile of lot geometries (EPSG:32188) |

We initialized a Git repository, created a `.gitignore` to exclude Windows Zone.Identifier artifacts from WSL, wrote a README, and pushed to `git@github.com:jburnford/montreal18thcentury.git`.

### Encoding Verification

The CSV was suspected to be ISO 8859-1, but hex analysis confirmed it is valid **UTF-8** (`c3 a9` = e, `c3 a7` = c). The garbled accent issue only occurs when Excel opens the file without detecting UTF-8. No conversion was needed.

## 2. Designing the CIDOC-CRM Data Model

The data model was developed iteratively through whiteboard sessions and diagram reviews with a modeling expert.

### Spatial Model

The spatial model uses a dual representation for lots and a historic/current distinction for streets:

- **Lots** are modeled as both:
  - `E18_Physical_Thing` -- the enduring cadastral lot
  - `E93_Presence` -- the lot during a specific ownership period, carrying the WKT polygon geometry
- **Historic streets** (as they existed in 1725) are `E93_Presence` nodes
- **Current streets** (modern equivalents) are `E53_Place` nodes
- **Old Montreal** is an `E53_Place` that contains all current streets

Key properties:
- `P195_was_a_presence_of` -- connects lot E93 to lot E18
- `P10_falls_within` -- lot E93 falls within a street E93 (both are spacetime volumes)
- `P161_has_spatial_projection` -- maps historic street E93 to current street E53
- `P89_falls_within` -- current street E53 within Old Montreal E53
- `P169i_spacetime_volume_is_defined_by` -- attaches WKT geometry to E93 nodes

### Ownership Model

Each CSV row represents one property acquisition. The model evolved through several iterations:

1. **Initial proposal**: Two E8_Acquisition events per row (acquisition + disposition), with P23_transferred_title_from on dispositions
2. **Simplification**: Removed P23 (we know who acquired, not who they acquired from)
3. **Final model**: One `E8_Acquisition` per row, using the `acquisitio` date for the event timespan. The `acquisitio` and `dispositio` dates together define the `E52_Time-Span` of the lot `E93_Presence` (the ownership period)

Properties on E8_Acquisition:
- `P22_transferred_title_to` -- the person/group who acquired the lot
- `P24_transferred_title_of` -- the enduring lot (E18)
- `P2_has_type` -- mode of acquisition (achat, succession, etc.) as E55_Type
- `P4_has_time-span` -- the acquisition date

### Person Model

- `type_propr = "individu"` maps to `E21_Person`
- All other `type_propr` values (succession, religieux, religieuses, etat, paroisse) map to `E74_Group`
- Each person/group gets an `E33_E41_Linguistic_Appellation` for their name
- Persons with `ind-id` get an `E42_Identifier` linking to remparts.info
- 22 persons with DBC (Dictionary of Canadian Biography) links get an additional `E42_Identifier`
- No `P2_has_type` properties on persons/groups (occupation, origin, sex are not typed on the entity)

### Property Corrections During Modeling

Several CRM property corrections were made based on expert review:
- `P168` (for E53_Place geometry) corrected to `P169` (for E93 spacetime volumes)
- `P161_has_spatial_projection` (lot to street) corrected to `P10_falls_within` (both are E93)
- `P166_was_a_presence_of` corrected to `P195_was_a_presence_of` (lot E93 to E18)
- Inverse form `P195i` corrected to `P195` (forward direction: E93 -> E18)

## 3. Data Quality Issues

Analysis of the 443-row CSV revealed:

- **3 exact duplicate rows** (same lot + person + dates): rows 150, 18, 340 -- deduplicated
- **1 empty row** (row 14): skipped
- **1 date typo**: `l727/12/30` (lowercase L instead of 1) in row 331 -- auto-corrected
- **2 invalid dates**: `1736/11/31` (November has 30 days) and `1730/02/29` (not a leap year) -- clamped to valid dates
- **12 year-only dates**: Format `YYYY/--/--` -- handled with P82a = Jan 1, P82b = Dec 31 of that year
- **174 rows (39%) without `ind-id`**: Persons not yet indexed in the biographical database -- URIs minted from slugified names
- **Leading tabs in DBC URLs**: Stripped during cleaning

## 4. Building the Conversion Script

The conversion script `csv_to_cidoc.py` is a single Python file using `rdflib` for graph construction and Turtle serialization.

### URI Minting Strategy

All URIs under `http://montreal1725.lincsproject.ca/`:

| Entity | Pattern |
|--------|---------|
| Person (with ind-id) | `person/{ind-id}` |
| Person (no ind-id) | `person/{slug(name)}` |
| Group | `group/{ind-id or slug(name)}` |
| Lot E18 | `lot/{safe(numero_dt)}` |
| Lot E93 | `lot-presence/{row_id}` |
| Historic Street E93 | `street/{slug(rue_devant)}` |
| Current Street E53 | `current-street/{slug(rue_devant)}` |
| E8 Acquisition | `acquisition/{row_id}` |
| E52 Time-Span (event) | `timespan/{row_id}` |
| E52 Time-Span (presence) | `timespan/{row_id}-presence` |
| E55 Type | `type/{category}/{slug(value)}` |
| E73 Information Object | `toponymie/{no_seq}` |

The `slug()` function strips diacritics, lowercases, and replaces non-alphanumeric characters with hyphens. The `safe_lot_id()` function handles lot numbers like `327(2)/327(3)` by replacing `/` with `-` and parentheses with `_`.

### Date Handling

| Pattern | P82 | P82a | P82b |
|---------|-----|------|------|
| Full date `1710/09/29` | `"1710-09-29"^^xsd:date` | `"1710-09-29T00:00:00"^^xsd:dateTime` | `"1710-09-29T23:59:59"^^xsd:dateTime` |
| Year only `1731/--/--` | `"1731"^^xsd:gYear` | `"1731-01-01T00:00:00"^^xsd:dateTime` | `"1731-12-31T23:59:59"^^xsd:dateTime` |

## 5. Adding GIS Data

### Lot Polygons

The lot shapefile (`MTL 1725_NAD83.zip`) was initially provided in EPSG:32188 but was later replaced with a WGS84 version, so no reprojection was needed. The shapefile is parsed directly from the zip (reading .shp and .dbf binary formats with `struct`) and matched to lots via `numero_dt`. 439 polygon geometries were attached to lot E93 presences as WKT via `P169i_spacetime_volume_is_defined_by`.

### Street Lines

A second GIS file (`Rues-Lignes.zip`) was provided containing street centerlines as GeoJSON MultiLineStrings in EPSG:32188. These required reprojection to WGS84 using `pyproj`. A name mapping table translates the GeoJSON's inverted name format ("Saint-Paul, rue") to the CSV's format ("rue Saint-Paul"). 24 street line geometries were attached to street E93 presences.

## 6. Grounding Streets to External Authority

Streets were grounded to the Commission de toponymie du Quebec website (`toponymie.gouv.qc.ca`). Each entry has a unique `no_seq` identifier with URL pattern: `https://toponymie.gouv.qc.ca/ct/ToposWeb/Fiche.aspx?no_seq={ID}`

The grounding is modeled as:
- `E73_Information_Object` for the toponymie.gouv.qc.ca web page
- `P129_is_about` linking the E73 to the E53 current street
- `P190_has_symbolic_content` holding the full URL

### Historical Street Name Changes

Several 1725 street names have changed:

| 1725 Name | Modern Name | no_seq |
|-----------|-------------|--------|
| rue Saint-Joseph | Rue Saint-Sulpice (renamed 1863) | 215048 |
| rue Saint-Charles | Place Jacques-Cartier | 213896 |
| Place du Marche | Place Royale (renamed 1891) | 214981 |
| rue Augustine | Rue McGill (formerly rue Saint-Augustin) | 214341 |
| rue Saint-Guillaume | Rue Dollard (renamed 1863) | 213510 |
| chemin du bord du fleuve | Rue de la Commune | 327282 |
| rue Capitale | Rue de la Capitale | 213305 |
| rue Saint-Sacrement | Rue du Saint-Sacrement | 215045 |
| rue Bonsecours | Rue de Bonsecours | 213229 |

### Not Groundable (4 streets)

- **Fortifications** -- refers to the city walls, not a street
- **petite rue** -- generic descriptor, not a toponym
- **passage entre rue Saint-Paul et rue Capitale** -- descriptive reference, not a named street
- **rue Saint-Francois** -- mapped to Saint-Francois-Xavier (likely abbreviated in 18th-century sources)

## 7. Final Output

The final RDF dataset `montreal1725.ttl` contains **14,025 triples** with the following entity counts:

| CRM Class | Count | Description |
|-----------|-------|-------------|
| E18_Physical_Thing | 439 | Enduring cadastral lots |
| E93_Presence | 473 | Lot presences (439) + street presences (34) |
| E8_Acquisition | 439 | Property acquisition events |
| E52_Time-Span | 878 | Acquisition dates (439) + ownership periods (439) |
| E21_Person | 342 | Individual property owners |
| E74_Group | 23 | Religious orders, state, estates of deceased |
| E33_E41_Linguistic_Appellation | 365 | Person/group names |
| E42_Identifier | 239 | Remparts.info IDs + DBC links |
| E53_Place | 35 | Current streets (34) + Old Montreal (1) |
| E73_Information_Object | 25 | Toponymie.gouv.qc.ca references |
| E55_Type | 5 | Modes of transfer |

## 8. Tools and Dependencies

- **Python 3** with `rdflib` (graph construction/serialization), `pyproj` (coordinate reprojection)
- **No external databases** -- pure file-based transformation
- **Input**: CSV + shapefiles/GeoJSON
- **Output**: Single Turtle (.ttl) file

## 9. Repository Structure

```
montreal18thcentury/
  README.md                  -- Project overview
  CLAUDE.md                  -- Data model documentation
  csv_to_cidoc.py            -- Conversion script
  montreal1725.ttl           -- Generated RDF output (14,025 triples)
  leon/
    MTL1725_HISCO.csv        -- Source CSV (443 records)
    Datadic.txt              -- Data dictionary
    data_info.docx           -- Extended documentation (French)
    rempa3_adhemarddm_table_PARCELLE.ods  -- Parcelle table
    Lots_1725_EPSG32188_SCHEMA.zip        -- Lot polygons (original)
    MTL 1725_NAD83.zip       -- Lot polygons (WGS84)
    Rues-Lignes.zip          -- Street line geometries (EPSG:32188)
```

## 10. Next Steps

- Web visualization (Leaflet.js map with lot polygons and street lines)
- Wikidata grounding for persons with DBC entries (22 candidates)
- HISCO occupational classification grounding to external vocabulary
- LINCS compatibility validation
- Loading into a triplestore for SPARQL querying
