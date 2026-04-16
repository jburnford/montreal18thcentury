#!/usr/bin/env python3
"""Convert Montreal 1725 property-ownership CSV to CIDOC-CRM RDF/Turtle."""

import csv
import re
import struct
import unicodedata
import zipfile
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, OWL, XSD, SKOS

# ---------------------------------------------------------------------------
# Namespaces
# ---------------------------------------------------------------------------
MTL = Namespace("http://montreal1725.lincsproject.ca/")
CRM = Namespace("http://www.cidoc-crm.org/cidoc-crm/")

INPUT_CSV = "leon/MTL1725_HISCO.csv"
INPUT_SHP = "leon/MTL 1725_NAD83.zip"
OUTPUT_TTL = "montreal1725.ttl"


# ---------------------------------------------------------------------------
# URI minting helpers
# ---------------------------------------------------------------------------
def slug(text):
    """Lowercase, strip diacritics, replace non-alnum with hyphens."""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    s = ascii_str.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


def safe_lot_id(numero_dt):
    """Make lot numbers URI-safe: / -> -, () -> _."""
    s = numero_dt.replace("/", "-").replace("(", "_").replace(")", "_")
    s = re.sub(r"[^a-zA-Z0-9_.-]+", "-", s)
    s = s.strip("-")
    return s


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------
def clean_date(raw):
    """Fix known date issues, return cleaned string or None."""
    raw = raw.strip()
    if not raw:
        return None
    # Fix typo: leading lowercase L -> 1
    if raw and raw[0] == "l":
        raw = "1" + raw[1:]
    return raw


def parse_date(cleaned):
    """Parse a cleaned date string. Returns (label, p82_literal, p82a_literal, p82b_literal) or None."""
    import calendar

    if not cleaned:
        return None

    # Year-only pattern: YYYY/--/--
    m = re.match(r"^(\d{4})/--/--$", cleaned)
    if m:
        year = m.group(1)
        return (
            year,
            Literal(year, datatype=XSD.gYear),
            Literal(f"{year}-01-01T00:00:00", datatype=XSD.dateTime),
            Literal(f"{year}-12-31T23:59:59", datatype=XSD.dateTime),
        )

    # Full date: YYYY/MM/DD
    m = re.match(r"^(\d{4})/(\d{2})/(\d{2})$", cleaned)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        # Clamp invalid days (e.g. Nov 31, Feb 29 in non-leap year)
        max_day = calendar.monthrange(year, month)[1]
        if day > max_day:
            print(f"  FIX: invalid date {cleaned}, clamping day {day} -> {max_day}")
            day = max_day
        iso = f"{year:04d}-{month:02d}-{day:02d}"
        return (
            iso,
            Literal(iso, datatype=XSD.date),
            Literal(f"{iso}T00:00:00", datatype=XSD.dateTime),
            Literal(f"{iso}T23:59:59", datatype=XSD.dateTime),
        )

    print(f"  WARNING: unparseable date '{cleaned}'")
    return None


# ---------------------------------------------------------------------------
# Shapefile reading
# ---------------------------------------------------------------------------
def load_geometries(shp_zip_path):
    """Read shapefile from zip, return dict of numero_dt -> WKT POLYGON string."""
    geometries = {}

    with zipfile.ZipFile(shp_zip_path) as z:
        shp_data = z.read("MTL 1725.shp")
        dbf_data = z.read("MTL 1725.dbf")

    # Parse DBF to get numero_dt for each record
    num_records = struct.unpack_from("<I", dbf_data, 4)[0]
    header_size = struct.unpack_from("<H", dbf_data, 8)[0]
    record_size = struct.unpack_from("<H", dbf_data, 10)[0]

    # Parse field descriptors to find numero_dt offset
    fields = []
    offset = 32
    while dbf_data[offset] != 0x0D:
        name = dbf_data[offset : offset + 11].replace(b"\x00", b"").decode()
        ftype = chr(dbf_data[offset + 11])
        flen = dbf_data[offset + 16]
        fields.append((name, ftype, flen))
        offset += 32

    # Find numero_dt field position
    field_offset = 1  # byte 0 is deletion flag
    numero_dt_start = None
    numero_dt_len = None
    for name, ftype, flen in fields:
        if name == "numero_dt":
            numero_dt_start = field_offset
            numero_dt_len = flen
            break
        field_offset += flen

    # Read all numero_dt values
    dbf_records = []
    for i in range(num_records):
        rec_offset = header_size + i * record_size
        rec = dbf_data[rec_offset : rec_offset + record_size]
        numero_dt = rec[numero_dt_start : numero_dt_start + numero_dt_len].decode("latin-1").strip()
        dbf_records.append(numero_dt)

    # Parse SHP file
    shp_offset = 100  # skip header
    for i in range(num_records):
        rec_num = struct.unpack_from(">I", shp_data, shp_offset)[0]
        content_len = struct.unpack_from(">I", shp_data, shp_offset + 4)[0] * 2
        shape_type = struct.unpack_from("<I", shp_data, shp_offset + 8)[0]

        if shape_type == 5:  # Polygon
            num_parts = struct.unpack_from("<I", shp_data, shp_offset + 44)[0]
            num_points = struct.unpack_from("<I", shp_data, shp_offset + 48)[0]

            # Read part indices
            parts_offset = shp_offset + 52
            parts = []
            for p in range(num_parts):
                parts.append(struct.unpack_from("<I", shp_data, parts_offset + p * 4)[0])

            # Read points
            points_offset = parts_offset + num_parts * 4
            points = []
            for p in range(num_points):
                x, y = struct.unpack_from("<2d", shp_data, points_offset + p * 16)
                points.append((x, y))

            # Build WKT
            if num_parts == 1:
                ring = ", ".join(f"{x} {y}" for x, y in points)
                wkt = f"POLYGON(({ring}))"
            else:
                rings = []
                for pi in range(num_parts):
                    start = parts[pi]
                    end = parts[pi + 1] if pi + 1 < num_parts else num_points
                    ring = ", ".join(f"{x} {y}" for x, y in points[start:end])
                    rings.append(f"({ring})")
                wkt = f"POLYGON({', '.join(rings)})"

            numero_dt = dbf_records[i]
            if numero_dt:
                geometries[numero_dt] = wkt

        shp_offset += 8 + content_len

    return geometries


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------
def bind_namespaces(g):
    g.bind("mtl1725", MTL)
    g.bind("crm", CRM)
    g.bind("rdf", RDF)
    g.bind("rdfs", RDFS)
    g.bind("owl", OWL)
    g.bind("xsd", XSD)
    g.bind("skos", SKOS)


def build_type_vocabulary(g):
    """Create all E55_Type instances."""
    vocabs = {
        "transfer-mode": ["achat", "succession", "vente", "s/m", "n/a"],
    }
    for category, values in vocabs.items():
        for val in values:
            uri = MTL[f"type/{category}/{slug(val)}"]
            g.add((uri, RDF.type, CRM.E55_Type))
            g.add((uri, RDFS.label, Literal(val, lang="fr")))


def build_old_montreal(g):
    """Create the Old Montreal singleton place."""
    uri = MTL["place/old-montreal"]
    g.add((uri, RDF.type, CRM.E53_Place))
    g.add((uri, RDFS.label, Literal("Vieux-Montréal", lang="fr")))
    g.add((uri, RDFS.label, Literal("Old Montreal", lang="en")))
    return uri


def get_or_create_person(g, row, seen_persons):
    """Create or retrieve a person/group entity. Returns URI."""
    ind_id = row["ind-id"].strip()
    name = row["proprietai"].strip()
    type_propr = row["type_propr"].strip()

    if not name and not ind_id:
        return None

    # Determine URI
    if ind_id:
        key = ind_id
        if type_propr == "individu":
            uri = MTL[f"person/{ind_id}"]
        else:
            uri = MTL[f"group/{ind_id}"]
    else:
        key = slug(name)
        if type_propr == "individu":
            uri = MTL[f"person/{key}"]
        else:
            uri = MTL[f"group/{key}"]

    if key in seen_persons:
        return seen_persons[key]
    seen_persons[key] = uri

    # Class
    if type_propr == "individu":
        g.add((uri, RDF.type, CRM.E21_Person))
    else:
        g.add((uri, RDF.type, CRM.E74_Group))

    # Label
    g.add((uri, RDFS.label, Literal(name, lang="fr")))

    # Appellation
    appellation_local = ind_id if ind_id else key
    app_uri = MTL[f"appellation/{appellation_local}"]
    g.add((app_uri, RDF.type, CRM["E33_E41_Linguistic_Appellation"]))
    g.add((app_uri, RDFS.label, Literal(name, lang="fr")))
    g.add((app_uri, CRM.P190_has_symbolic_content, Literal(name)))
    g.add((uri, CRM.P1_is_identified_by, app_uri))

    # Remparts.info identifier (if ind-id present)
    if ind_id:
        id_uri = MTL[f"identifier/{ind_id}-remparts"]
        g.add((id_uri, RDF.type, CRM.E42_Identifier))
        g.add((id_uri, RDFS.label, Literal(f"{ind_id} (remparts.info)")))
        g.add((id_uri, CRM.P190_has_symbolic_content, Literal(ind_id)))
        g.add((uri, CRM.P1_is_identified_by, id_uri))

    # DBC identifier (if present)
    dbc = row.get("DBC", "").strip()
    if dbc:
        dbc_uri = MTL[f"identifier/{appellation_local}-dbc"]
        g.add((dbc_uri, RDF.type, CRM.E42_Identifier))
        g.add((dbc_uri, RDFS.label, Literal(f"DBC entry for {name}")))
        g.add((dbc_uri, CRM.P190_has_symbolic_content, Literal(dbc)))
        g.add((uri, CRM.P1_is_identified_by, dbc_uri))

    return uri


def get_or_create_lot(g, row, seen_lots, geometries=None):
    """Create or retrieve lot E18 + E93. Returns (e18_uri, e93_uri)."""
    numero_dt = row["numero_dt"].strip()
    if not numero_dt:
        return None, None

    if numero_dt in seen_lots:
        return seen_lots[numero_dt]

    lot_id = safe_lot_id(numero_dt)
    e18_uri = MTL[f"lot/{lot_id}"]
    e93_uri = MTL[f"lot-presence/{lot_id}"]

    # E18 Physical Thing (enduring lot)
    g.add((e18_uri, RDF.type, CRM.E18_Physical_Thing))
    g.add((e18_uri, RDFS.label, Literal(f"Lot {numero_dt}")))

    # E93 Presence (1725 snapshot)
    g.add((e93_uri, RDF.type, CRM.E93_Presence))
    g.add((e93_uri, RDFS.label, Literal(f"Lot {numero_dt} (1725)")))
    g.add((e93_uri, CRM.P195_was_a_presence_of, e18_uri))

    # Geometry from shapefile
    if geometries and numero_dt in geometries:
        g.add((e93_uri, CRM["P169i_spacetime_volume_is_defined_by"], Literal(geometries[numero_dt])))

    seen_lots[numero_dt] = (e18_uri, e93_uri)
    return e18_uri, e93_uri


def get_or_create_street(g, row, seen_streets):
    """Create or retrieve street E93 + E53. Returns E93 URI or None."""
    rue = row["rue_devant"].strip()
    if not rue or rue == "n/a":
        return None

    if rue in seen_streets:
        return seen_streets[rue]

    rue_slug = slug(rue)
    e93_uri = MTL[f"street/{rue_slug}"]
    e53_uri = MTL[f"current-street/{rue_slug}"]

    # Historic street (E93 Presence)
    g.add((e93_uri, RDF.type, CRM.E93_Presence))
    g.add((e93_uri, RDFS.label, Literal(f"{rue} (1725)", lang="fr")))
    g.add((e93_uri, CRM.P161_has_spatial_projection, e53_uri))

    # Current street (E53 Place)
    g.add((e53_uri, RDF.type, CRM.E53_Place))
    g.add((e53_uri, RDFS.label, Literal(rue, lang="fr")))
    g.add((e53_uri, CRM.P89_falls_within, MTL["place/old-montreal"]))

    seen_streets[rue] = e93_uri
    return e93_uri


def build_timespan(g, row_id, suffix, cleaned_date):
    """Create an E52 Time-Span for a specific event. Returns URI or None."""
    parsed = parse_date(cleaned_date)
    if not parsed:
        return None

    label, p82, p82a, p82b = parsed
    ts_uri = MTL[f"timespan/{row_id}-{suffix}"]

    g.add((ts_uri, RDF.type, CRM["E52_Time-Span"]))
    g.add((ts_uri, RDFS.label, Literal(label)))
    g.add((ts_uri, CRM.P82_at_some_time_within, p82))
    g.add((ts_uri, CRM.P82a_begin_of_the_begin, p82a))
    g.add((ts_uri, CRM.P82b_end_of_the_end, p82b))

    return ts_uri


def build_acquisition_event(g, row, person_uri, e18_uri):
    """Create the incoming E8 Acquisition event."""
    row_id = row["id"].strip()
    mode = row["mode_acqui"].strip()
    acq_date = clean_date(row["acquisitio"])

    if not person_uri or not e18_uri:
        return

    e8_uri = MTL[f"acquisition/{row_id}-acq"]
    name = row["proprietai"].strip()
    numero_dt = row["numero_dt"].strip()

    g.add((e8_uri, RDF.type, CRM.E8_Acquisition))
    g.add((e8_uri, RDFS.label, Literal(f"Acquisition of lot {numero_dt} by {name}")))
    g.add((e8_uri, CRM.P24_transferred_title_of, e18_uri))
    g.add((e8_uri, CRM.P22_transferred_title_to, person_uri))

    # Mode of transfer
    if mode:
        type_uri = MTL[f"type/transfer-mode/{slug(mode)}"]
        g.add((e8_uri, CRM.P2_has_type, type_uri))

    # Time-span
    ts_uri = build_timespan(g, row_id, "acq", acq_date)
    if ts_uri:
        g.add((e8_uri, CRM["P4_has_time-span"], ts_uri))


def build_disposition_event(g, row, person_uri, e18_uri):
    """Create the outgoing E8 Acquisition (disposition) event."""
    row_id = row["id"].strip()
    mode = row["mode_dispo"].strip()
    disp_date = clean_date(row["dispositio"])

    if not e18_uri:
        return

    numero_dt = row["numero_dt"].strip()
    name = row["proprietai"].strip()

    e8_uri = MTL[f"acquisition/{row_id}-disp"]

    g.add((e8_uri, RDF.type, CRM.E8_Acquisition))
    g.add((e8_uri, RDFS.label, Literal(f"Disposition of lot {numero_dt} from {name}")))
    g.add((e8_uri, CRM.P24_transferred_title_of, e18_uri))

    # Mode of transfer
    if mode and mode not in ("",):
        type_uri = MTL[f"type/transfer-mode/{slug(mode)}"]
        g.add((e8_uri, CRM.P2_has_type, type_uri))

    # Time-span
    ts_uri = build_timespan(g, row_id, "disp", disp_date)
    if ts_uri:
        g.add((e8_uri, CRM["P4_has_time-span"], ts_uri))


# ---------------------------------------------------------------------------
# CSV loading and cleaning
# ---------------------------------------------------------------------------
def load_csv(path):
    """Load and clean the CSV. Returns list of row dicts."""
    rows = []
    seen = set()
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Strip all fields
            for k in row:
                if row[k]:
                    row[k] = row[k].strip()
                else:
                    row[k] = ""

            # Fix date typos
            for field in ("acquisitio", "dispositio"):
                if row[field] and row[field][0] == "l":
                    print(f"  FIX: date typo in row {row['id']}: '{row[field]}' -> '1{row[field][1:]}'")
                    row[field] = "1" + row[field][1:]

            # Strip tabs from DBC
            row["DBC"] = row.get("DBC", "").strip()

            # Skip empty rows
            if not row.get("proprietai") and not row.get("numero_dt"):
                print(f"  SKIP: empty row {row.get('id', '?')}")
                continue

            # Deduplicate
            dedup_key = (row["numero_dt"], row["proprietai"], row["acquisitio"], row["dispositio"])
            if dedup_key in seen:
                print(f"  SKIP: duplicate row {row['id']} (lot={row['numero_dt']}, person={row['proprietai']})")
                continue
            seen.add(dedup_key)

            rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("Loading CSV...")
    rows = load_csv(INPUT_CSV)
    print(f"  {len(rows)} rows after cleaning")

    print("Loading shapefile geometries...")
    geometries = load_geometries(INPUT_SHP)
    print(f"  {len(geometries)} lot geometries loaded")

    g = Graph()
    bind_namespaces(g)

    # Build type vocabulary
    build_type_vocabulary(g)

    # Build Old Montreal
    build_old_montreal(g)

    # Tracking dicts
    seen_persons = {}
    seen_lots = {}
    seen_streets = {}

    print("Processing rows...")
    for row in rows:
        # Person or Group
        person_uri = get_or_create_person(g, row, seen_persons)

        # Lot (E18 + E93)
        e18_uri, e93_uri = get_or_create_lot(g, row, seen_lots, geometries)

        # Street (E93 + E53) and link lot to street
        street_uri = get_or_create_street(g, row, seen_streets)
        if street_uri and e93_uri:
            g.add((e93_uri, CRM.P10_falls_within, street_uri))

        # Acquisition event
        build_acquisition_event(g, row, person_uri, e18_uri)

        # Disposition event
        build_disposition_event(g, row, person_uri, e18_uri)

    # Serialize
    print(f"Serializing {len(g)} triples...")
    g.serialize(OUTPUT_TTL, format="turtle")
    print(f"Wrote {OUTPUT_TTL}")

    # Summary
    type_counts = {}
    for s, p, o in g.triples((None, RDF.type, None)):
        label = str(o).split("/")[-1]
        type_counts[label] = type_counts.get(label, 0) + 1
    print("\nEntity counts by type:")
    for t, c in sorted(type_counts.items()):
        print(f"  {t}: {c}")


if __name__ == "__main__":
    main()
