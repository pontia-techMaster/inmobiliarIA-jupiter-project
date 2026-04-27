"""
Property Data Extractor
Extracts property information from local HTML files (Idealista-like format)
"""

import json
import re
import sys
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import cast

from bs4 import BeautifulSoup


@dataclass
class _Location:
    street: str | None = None
    neighborhood: str | None = None
    district: str | None = None


@dataclass
class PropertyData:
    """Data class to hold property extracted information."""

    id: str | None = None
    idealista_id: int | None = None
    price: int | None = None
    property_type: str | None = None
    property_subtype: str | None = None
    street: str | None = None
    neighborhood: str | None = None
    district: str | None = None
    surface: int | None = None
    rooms: int | None = None
    bathrooms: int | None = None
    description: str | None = None
    floor: str | None = None
    is_exterior: bool | None = None
    has_elevator: bool | None = None
    images: list[str] = field(default_factory=list)
    url: str | None = None

    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class PropertyExtractor:
    """Extracts property data from HTML files."""

    APARTMENT_SUBTYPES = {
        "ático": "penthouse",
        "atico": "penthouse",
        "dúplex": "duplex",
        "duplex": "duplex",
        "estudio": "studio",
        "apartamento": "apartment",
        "piso": "flat",
    }

    HOUSE_SUBTYPES = {
        "chalet": "chalet",
        "villa": "villa",
        "adosado": "townhouse",
        "unifamiliar": "detached_house",
        "casa": "house",
    }

    def __init__(self, html_path: str):
        self.html_path = Path(html_path)
        self._load_html()

    def _load_html(self) -> None:
        if not self.html_path.exists():
            raise FileNotFoundError(f"File not found: {self.html_path}")
        with open(self.html_path, encoding="utf-8") as f:
            self.soup = BeautifulSoup(f.read(), "html.parser")

    def extract(self) -> PropertyData:
        property_type, property_subtype = self._extract_property_type_and_subtype()
        url = self._extract_url()
        idealista_id = int(url.removeprefix("https://www.idealista.com/inmueble").strip("/"))
        location = self._extract_location()

        return PropertyData(
            price=self._extract_price(),
            idealista_id=idealista_id,
            property_type=property_type,
            property_subtype=property_subtype,
            street=location.street,
            neighborhood=location.neighborhood,
            district=location.district,
            surface=self._extract_surface(),
            rooms=self._extract_rooms(),
            bathrooms=self._extract_bathrooms(),
            description=self._extract_description(),
            floor=self._extract_floor(property_type),
            is_exterior=self._extract_is_exterior(property_type),
            has_elevator=self._extract_has_elevator(),
            images=self._extract_images(),
            url=url,
        )

    def _extract_url(self) -> str:
        tag = self.soup.find("meta", property="og:url")
        content = tag.get("content") if tag else None
        return content if isinstance(content, str) else ""

    def _extract_title(self) -> str | None:
        container = self.soup.select_one(".main-info__title")
        if not container:
            return None
        parts = [
            el.get_text(strip=True)
            for key in (".main-info__title-main", ".main-info__title-minor")
            if (el := container.select_one(key))
        ]
        return ", ".join(parts) if parts else None

    def _extract_price(self) -> int | None:
        el = self.soup.select_one(".info-data .info-data-price") or self.soup.select_one(".info-data")
        if not el:
            return None
        text = el.get_text(" ", strip=True).replace("€", "").replace(" ", "").replace(".", "").strip()
        digits = "".join(filter(str.isdigit, text))
        return int(digits) if digits else None

    def _extract_property_type_and_subtype(self) -> tuple[str | None, str | None]:
        candidates = []
        if typology := self.soup.select_one(".typology"):
            candidates.append(typology.get_text(" ", strip=True))
        if title := self._extract_title():
            candidates.append(title)
        if page_title := self.soup.find("title"):
            candidates.append(page_title.get_text(" ", strip=True))

        for text in candidates:
            text_lower = text.lower()
            for key, subtype in self.APARTMENT_SUBTYPES.items():
                if key in text_lower:
                    return "apartment", subtype
            for key, subtype in self.HOUSE_SUBTYPES.items():
                if key in text_lower:
                    return "house", subtype

        return None, None

    def _extract_location(self) -> _Location:
        header_map = self.soup.select_one("#headerMap")
        if not header_map:
            return _Location()

        parts = [
            item.get_text(" ", strip=True) for item in header_map.select("li.header-map-list") if item.get_text(strip=True)
        ]

        n = len(parts)
        return _Location(
            street=parts[0] if n == 5 else None,
            neighborhood=parts[1 if n == 5 else 0].strip().removeprefix("Barrio").strip() if n > 1 else None,
            district=parts[2 if n == 5 else 1].strip().removeprefix("Distrito").strip() if n > 2 else None,
        )

    def _extract_feature_texts(self) -> list[str]:
        selectors = [
            ".info-features span",
            ".details-property-features li",
            ".details-property-feature-one li",
            ".details-property-feature-two li",
            ".details-property_features li",
        ]
        features = []
        for selector in selectors:
            for el in self.soup.select(selector):
                text = el.get_text(" ", strip=True)
                if text and text not in features:
                    features.append(text)

        if not features:
            if container := self.soup.select_one(".info-features"):
                text = container.get_text(" ", strip=True)
                if text:
                    return [text]

        return features

    def _extract_surface(self) -> int | None:
        for text in self._extract_feature_texts():
            if m := re.search(r"(\d+(?:[.,]\d+)?)\s*m²", text.lower()):
                return int(float(m.group(1).replace(",", ".")))
        return None

    def _extract_rooms(self) -> int | None:
        for text in self._extract_feature_texts():
            if m := re.search(r"(\d+)\s*hab", text.lower()):
                return int(m.group(1))
        return None

    def _extract_bathrooms(self) -> int | None:
        for text in self._extract_feature_texts():
            if m := re.search(r"(\d+)\s*bañ", text.lower()):
                return int(m.group(1))
        return None

    def _extract_floor(self, property_type: str | None) -> str | None:
        if property_type == "house":
            return None
        for text in self._extract_feature_texts():
            text_lower = text.lower()
            if "planta" in text_lower:
                if "bajo" in text_lower:
                    return "bajo"
                if "entreplanta" in text_lower:
                    return "entreplanta"
                if m := re.search(r"planta\s+([^\s,]+)", text_lower):
                    return m.group(1)
            if text_lower.strip() == "bajo":
                return "bajo"
        return None

    def _extract_is_exterior(self, property_type: str | None) -> bool | None:
        if property_type != "apartment":
            return None
        for text in self._extract_feature_texts():
            text_lower = text.lower()
            if "interior" in text_lower:
                return False
            if "exterior" in text_lower:
                return True
        return None

    def _extract_has_elevator(self) -> bool | None:
        for text in self._extract_feature_texts():
            text_lower = text.lower()
            if "sin ascensor" in text_lower:
                return False
            if "ascensor" in text_lower:
                return True
        return None

    def _extract_description(self) -> str | None:
        el = self.soup.select_one(".comment")
        if not el:
            return None
        paragraphs = el.find_all("p")
        if paragraphs:
            return "\n\n".join(p.get_text(" ", strip=True) for p in paragraphs)
        return el.get_text(" ", strip=True)

    def _extract_images(self) -> list[str]:
        urls: set[str] = set()
        page_content = str(self.soup)

        for url in re.findall(r'imageDataServiceWebp["\s:]+([^"]+\.webp)', page_content):
            if self._is_valid_image_url(url):
                urls.add(url)

        if multimedia := self.soup.select_one("#main-multimedia"):
            for img in multimedia.find_all("img"):
                if url := self._get_image_url(img):
                    if self._is_valid_image_url(url):
                        urls.add(url)

        for img in self.soup.select(".main-image img"):
            if url := self._get_image_url(img):
                if self._is_valid_image_url(url):
                    urls.add(url)

        for source in self.soup.find_all("source"):
            if srcset := source.get("srcset"):
                url = cast(str, srcset).split()[0] if " " in srcset else cast(str, srcset)
                if self._is_valid_image_url(url):
                    urls.add(url)

        return sorted(urls)

    @staticmethod
    def _is_valid_image_url(url: str) -> bool:
        return (
            bool(url)
            and not url.startswith("data:")
            and url.lower().endswith(".webp")
            and url.startswith("https://img4.idealista.com/blur/WEB_DETAIL/0/id.pro.es.image.master/")
        )

    @staticmethod
    def _get_image_url(img_tag) -> str | None:
        for prop in ("src", "data-src", "data-lazy-src", "data-original"):
            if isinstance(url := img_tag.get(prop), str):
                return cast(str, url)
        return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Extract property data from an Idealista HTML file")
    parser.add_argument("path", help="Path to the HTML file")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    try:
        data = PropertyExtractor(args.path).extract()
        print(data.to_json() if args.json else data)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error extracting data: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
