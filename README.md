# Montreal 18th-Century Property Data — CIDOC-CRM Transformation

This project transforms historical property-ownership data from 18th-century Montreal into a CIDOC-CRM Linked Open Data (LOD) knowledge graph.

## Source Data

The dataset (`leon/`) was compiled by Léon Robichaud and documents **land lots and their owners in Montreal circa 1725**, based on the second *terrier* (land register) of the Sulpician Seminary. It contains 443 property-ownership records covering cadastral parcels within the historic city.

### Files

| File | Description |
|------|-------------|
| `MTL1725_HISCO.csv` | Main dataset — 443 property records with owners, dates, occupations, and HISCO codes |
| `Datadic.txt` | Data dictionary (English field descriptions) |
| `data_info.docx` | Extended data documentation (French) |
| `rempa3_adhemarddm_table_PARCELLE.ods` | Parcelle table from the ADHÉMAR/Remparts database |
| `Lots_1725_EPSG32188_SCHEMA.zip` | GIS shapefile of lot geometries (EPSG:32188 / NAD83 MTM zone 8) |

### Key Fields

- **proprietai** — Owner name
- **numero_dt** — Cadastral number (Sulpician terrier)
- **acquisitio / dispositio** — Start/end dates of ownership
- **mode_acqui / mode_dispo** — Mode of acquisition/disposition (achat, succession, vente, etc.)
- **origine** — Ethnic origin (FR = French, C = Canadian)
- **occupation** — Occupational category (commerce, production, agriculture, service, admin/officers)
- **HISCO** — HISCO occupational classification code
- **DBC** — Link to the *Dictionary of Canadian Biography* entry (where applicable)
- **ind-id** — Unique individual identifier (links to [remparts.info](https://remparts.info))

### External Linkages

- **Dictionary of Canadian Biography**: Some individuals have DCB entries
- **Quebec Toponymy Commission**: Street names can be linked to [toponymie.gouv.qc.ca](https://toponymie.gouv.qc.ca/)
- **ADHÉMAR / Remparts**: Individual IDs link to the [Remparts](https://remparts.info) prosopographical database

## Goal

Transform this tabular data into RDF following the [CIDOC-CRM](https://www.cidoc-crm.org/) ontology, suitable for publication as Linked Open Data. The transformation will model:

- **Persons** (E21) and their occupations, origins, and biographical links
- **Property lots** (E22/E53) with cadastral identifiers and geometries
- **Ownership events** (E8 Acquisition / E10 Transfer of Custody) with temporal spans
- **Places** (E53) — streets, the city of Montreal, residences
- **Historical context** — institutions (Sulpician Seminary), modes of land transfer

## License

Source data provided by Léon Robichaud. See `leon/data_info.docx` for full documentation and terms.
