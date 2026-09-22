"""Current membership of Congress, from the official lists.

  House:  https://clerk.house.gov/xml/lists/MemberData.xml
  Senate: https://www.senate.gov/general/contact_information/senators_cfm.xml

Used to confirm every followed politician is still in office, and to attach
party and state without relying on memory.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

HOUSE_URL = "https://clerk.house.gov/xml/lists/MemberData.xml"
SENATE_URL = "https://www.senate.gov/general/contact_information/senators_cfm.xml"


@dataclass
class Member:
    bioguide: str
    chamber: str  # house / senate
    name: str
    last: str
    first: str
    party: str
    state: str
    district: str | None  # "11", "At Large", or None for senators


def parse_house(xml_text: str) -> dict[str, Member]:
    root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    out: dict[str, Member] = {}
    for m in root.findall(".//member"):
        mi = m.find("member-info")
        if mi is None:
            continue
        bid = mi.findtext("bioguideID", "").strip()
        if not bid:
            continue
        sd = m.findtext("statedistrict", "").strip()
        out[bid] = Member(
            bioguide=bid, chamber="house",
            name=mi.findtext("official-name", "").strip(),
            last=mi.findtext("lastname", "").strip(),
            first=mi.findtext("firstname", "").strip(),
            party=mi.findtext("party", "").strip(),
            state=sd[:2],
            district=mi.findtext("district", "").strip() or sd[2:],
        )
    return out


def parse_senate(xml_text: str) -> dict[str, Member]:
    root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    out: dict[str, Member] = {}
    for m in root.findall(".//member"):
        bid = m.findtext("bioguide_id", "").strip()
        if not bid:
            continue
        first = m.findtext("first_name", "").strip()
        last = m.findtext("last_name", "").strip()
        out[bid] = Member(
            bioguide=bid, chamber="senate", name=f"{first} {last}", last=last, first=first,
            party=m.findtext("party", "").strip(), state=m.findtext("state", "").strip(), district=None,
        )
    return out
