# DemonFF - Blender scripts for working with Renderware & R*/SA-MP/open.mp formats in Blender
# 2023 - 2026 spicybung

# This is a fork of DragonFF by Parik27 - maintained by Psycrow, and various others!
# Check it out at: https://github.com/Parik27/DragonFF

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


SAMP_IDE_RANGE = range(18631, 20000)
SAMP_CUSTOM_IDE_RANGE = range(15065, 16000)


def load_retail_sa_catalog():
    from pathlib import Path

    filepath = Path(__file__).with_name("sa_retail_ide.tsv")
    records = {}
    if not filepath.is_file():
        return records
    with filepath.open("r", encoding="utf-8") as source:
        for line in source:
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 4:
                continue
            try:
                model_id = int(fields[0])
            except ValueError:
                continue
            records.setdefault(model_id, {
                "id": model_id,
                "model": fields[1],
                "txd": fields[2],
                "section": "objs",
                "file": fields[3],
            })
    return records


def load_retail_sa_names():
    from pathlib import Path

    filepath = Path(__file__).with_name("sa_retail_ide.tsv")
    names = {}
    if filepath.is_file():
        with filepath.open("r", encoding="utf-8") as source:
            for line in source:
                fields = line.rstrip("\n").split("\t")
                if len(fields) != 4:
                    continue
                try:
                    model_id = int(fields[0])
                except ValueError:
                    continue
                names[normalize_model_name(fields[1])] = {
                    "id": model_id, "model": fields[1],
                    "txd": fields[2], "file": fields[3], "section": "objs",
                }
    return names


def normalize_model_name(value):
    name = str(value or "").strip().replace("\\", "/").split("/")[-1]
    if name.lower().endswith(".dff"):
        name = name[:-4]
    return name.lower()


def parse_ide_records(filepath):
    records = []
    section = None
    with open(filepath, "r", encoding="latin-1") as source:
        for number, line in enumerate(source, 1):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            key = line.lower()
            if key in {"objs", "tobj", "anim"}:
                section = key
                continue
            if key == "end":
                section = None
                continue
            if section is None:
                continue
            fields = [field.strip() for field in line.split(",")]
            if len(fields) < 3:
                continue
            try:
                model_id = int(fields[0], 10)
            except ValueError:
                continue
            model_name = fields[1]
            if not model_name:
                continue
            records.append({
                "id": model_id,
                "model": model_name,
                "txd": fields[2],
                "section": section,
                "file": str(filepath),
                "line": number,
            })
    return records


def build_ide_catalog(retail_paths=(), samp_paths=()):
    catalog = {"retail_by_id": {}, "retail_by_name": {},
               "samp_by_id": {}, "samp_by_name": {}, "conflicts": []}
    retail_records = load_retail_sa_catalog()
    catalog["retail_by_id"].update(retail_records)
    catalog["retail_by_name"].update(load_retail_sa_names())
    for family, paths in (("retail", retail_paths), ("samp", samp_paths)):
        ids = catalog[family + "_by_id"]
        names = catalog[family + "_by_name"]
        for filepath in paths:
            for record in parse_ide_records(filepath):
                previous = ids.get(record["id"])
                if previous and normalize_model_name(previous["model"]) != normalize_model_name(record["model"]):
                    catalog["conflicts"].append((family, previous, record))
                ids[record["id"]] = record
                names[normalize_model_name(record["model"])] = record
    return catalog


def compare_ide_catalog(catalog):
    comparisons = []
    for model_name, samp_record in catalog["samp_by_name"].items():
        retail_record = catalog["retail_by_name"].get(model_name)
        if retail_record is None:
            continue
        comparisons.append({
            "model": model_name,
            "retail_id": retail_record["id"],
            "samp_id": samp_record["id"],
            "same_id": retail_record["id"] == samp_record["id"],
            "same_txd": retail_record["txd"].lower() == samp_record["txd"].lower(),
        })
    return comparisons
