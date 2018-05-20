#!/usr/bin/env python3
"""Converts a directory tree containing resource topology data to a single
XML document.

Usage as a script:

    resourcegroup_yaml_to_xml.py <input directory> [<output file>] [<downtime output file>]

If output file not specified or downtime output file not specified, results are printed to stdout.

Usage as a module

    from converters.resourcegroup_yaml_to_xml import get_rgsummary_rgdowntime_xml
    rgsummary_xml, rgdowntime_xml = get_rgsummary_rgdowntime_xml(input_dir[, output_file, downtime_output_file])

where the return value `xml` is a string.

"""
import argparse
from argparse import ArgumentParser

import anymarkup
import pprint
import sys
from pathlib import Path

from app.topology import Tables, Topology
from app.utils import ensure_list, to_xml

class RGError(Exception):
    """An error with converting a specific RG"""
    def __init__(self, rg, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)
        self.rg = rg


class DowntimeError(Exception):
    """An error with converting a specific piece of downtime info"""
    def __init__(self, downtime, rg, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)
        self.downtime = downtime
        self.rg = rg


def get_rgsummary_rgdowntime(indir="topology", contacts_file=None):
    contacts_data = None
    if contacts_file:
        contacts_data = anymarkup.parse_file(contacts_file)
    topology = get_topology(indir, contacts_data)
    return topology.get_resource_summary(), topology.get_downtimes()


def get_topology(indir="topology", contacts_data=None):
    root = Path(indir)
    support_centers = anymarkup.parse_file(root / "support-centers.yaml")
    service_types = anymarkup.parse_file(root / "services.yaml")
    tables = Tables(contacts=contacts_data, service_types=service_types, support_centers=support_centers)
    topology = Topology(tables)

    for facility_path in root.glob("*/FACILITY.yaml"):
        name = facility_path.parts[-2]
        id_ = anymarkup.parse_file(facility_path)["ID"]
        topology.add_facility(name, id_)
    for site_path in root.glob("*/*/SITE.yaml"):
        facility, name = site_path.parts[-3:-1]
        id_ = anymarkup.parse_file(site_path)["ID"]
        topology.add_site(facility, name, id_)
    for yaml_path in root.glob("*/*/*.yaml"):
        facility, site, name = yaml_path.parts[-3:]
        if name == "SITE.yaml": continue
        if name.endswith("_downtime.yaml"): continue

        name = name.replace(".yaml", "")
        rg = anymarkup.parse_file(yaml_path)
        downtime_yaml_path = yaml_path.with_name(name + "_downtime.yaml")
        downtimes = None
        if downtime_yaml_path.exists():
            downtimes = ensure_list(anymarkup.parse_file(downtime_yaml_path))

        topology.add_rg(facility, site, name, rg)
        if downtimes:
            for downtime in downtimes:
                topology.add_downtime(site, name, downtime)

    return topology


def main(argv):
    parser = ArgumentParser()
    parser.add_argument("indir", help="input dir for topology data")
    parser.add_argument("outfile", nargs='?', type=argparse.FileType('w'), default=sys.stdout, help="output file for rgsummary")
    parser.add_argument("downtimefile", nargs='?', type=argparse.FileType('w'), default=sys.stdout, help="output file for rgdowntime")
    parser.add_argument("--contacts", help="contacts yaml file")
    args = parser.parse_args(argv[1:])

    try:
        rgsummary, rgdowntime = get_rgsummary_rgdowntime(args.indir, args.contacts)
        print(to_xml(rgsummary), file=args.outfile)
        print(to_xml(rgdowntime), file=args.downtimefile)
    except RGError as e:
        print("Error happened while processing RG:", file=sys.stderr)
        pprint.pprint(e.rg, stream=sys.stderr)
        raise
    except DowntimeError as e:
        print("Error happened while processing downtime:", file=sys.stderr)
        pprint.pprint(e.downtime, stream=sys.stderr)
        print("RG:", file=sys.stderr)
        pprint.pprint(e.rg, stream=sys.stderr)
        raise

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))