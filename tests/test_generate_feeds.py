import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("generate_feeds", ROOT / "scripts" / "generate_feeds.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class GenerateFeedsTests(unittest.TestCase):
    def generate(self, with_ranges=True):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        output = Path(temp.name) / "feeds"
        geo = (ROOT / "tests" / "fixtures" / "geo-ip-feed.csv").read_bytes()
        ranges = (ROOT / "tests" / "fixtures" / "ip-ranges.json").read_bytes() if with_ranges else None
        manifest = MODULE.generate(output, geo, ranges, ROOT / "data" / "country_continents.json")
        return output, manifest

    def test_ipv6_is_excluded_and_adjacent_prefixes_are_collapsed(self):
        output, _ = self.generate()
        self.assertEqual((output / "countries" / "US.txt").read_text(), "3.2.34.0/25\n15.230.0.0/24\n")

    def test_country_and_subdivision_feeds(self):
        output, _ = self.generate()
        self.assertEqual((output / "subdivisions" / "US-OH.txt").read_text(), "3.2.34.0/25\n")
        self.assertEqual((output / "countries" / "IL.txt").read_text(), "51.84.0.0/24\n")

    def test_locality_and_hierarchy_feeds(self):
        output, _ = self.generate()
        canonical = output / "localities" / "US" / "US-OH" / "new-albany.txt"
        hierarchical = output / "hierarchy" / "north-america" / "countries" / "US" / "subdivisions" / "US-OH" / "localities" / "new-albany.txt"
        self.assertEqual(canonical.read_text(), hierarchical.read_text())

    def test_aws_region_and_border_group_feeds(self):
        output, _ = self.generate()
        self.assertEqual((output / "aws-regions" / "us-east-2.txt").read_text(), "3.2.34.0/25\n")
        self.assertEqual((output / "network-border-groups" / "us-east-1-atl-1.txt").read_text(), "15.230.1.0/24\n")

    def test_manifest_contains_source_identity(self):
        output, manifest = self.generate()
        disk_manifest = json.loads((output / "manifest.json").read_text())
        self.assertEqual(disk_manifest["sources"]["ip_ranges"]["sync_token"], "1234567890")
        self.assertEqual(manifest["unknown_country_codes"], [])

    def test_skip_ranges_still_generates_geo_feeds(self):
        output, _ = self.generate(with_ranges=False)
        self.assertTrue((output / "all.txt").is_file())
        self.assertFalse((output / "aws-regions").exists())


if __name__ == "__main__":
    unittest.main()
