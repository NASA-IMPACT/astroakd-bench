"""Conservative curated seed objects for *candidate* astronomical questions.

The coordinates are approximate ICRS centers, *not reference answers*.
They intentionally are not presented as independently validated astrometry.
Validation against archives belongs to milestone 0.3.0.
"""

from __future__ import annotations

from dataclasses import dataclass


SEED_CATALOG_VERSION = "0.2.0"


@dataclass(frozen=True)
class SkyTarget:
    name: str
    ra_deg: float
    dec_deg: float


TARGETS: tuple[SkyTarget, ...] = (
    SkyTarget("M31", 10.6847, 41.2688),
    SkyTarget("M33", 23.4621, 30.6602),
    SkyTarget("M51", 202.4696, 47.1952),
    SkyTarget("M81", 148.8882, 69.0653),
    SkyTarget("M82", 148.9685, 69.6797),
    SkyTarget("M87", 187.7059, 12.3911),
    SkyTarget("M101", 210.8023, 54.3492),
    SkyTarget("M104", 189.9976, -11.6231),
    SkyTarget("NGC 1068", 40.6696, -0.0133),
    SkyTarget("NGC 4151", 182.6357, 39.4057),
    SkyTarget("NGC 3783", 174.7573, -37.7386),
    SkyTarget("NGC 5548", 214.4980, 25.1369),
    SkyTarget("NGC 1275", 49.9507, 41.5117),
    SkyTarget("NGC 253", 11.8880, -25.2880),
    SkyTarget("NGC 5128", 201.3650, -43.0190),
    SkyTarget("NGC 7027", 316.7600, 42.2300),
    SkyTarget("NGC 6543", 269.6390, 66.6330),
    SkyTarget("NGC 7009", 315.4020, -11.3630),
    SkyTarget("NGC 7662", 351.4800, 42.5350),
    SkyTarget("NGC 7293", 337.4100, -20.8370),
    SkyTarget("NGC 1976", 83.8221, -5.3911),
    SkyTarget("NGC 6720", 283.3975, 33.0285),
)

# Explicit finite options: no arbitrary archive/database names synthesized.
RADII_ARCMIN = (2, 3, 5, 8, 10)
HEASARC_CATALOGS = ("xmmmaster", "chanmaster")
VIZIER_CATALOGS = ("II/246", "I/355")
