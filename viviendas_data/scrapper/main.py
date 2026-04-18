#!/usr/bin/env python3
"""
Property Data Extractor
Extracts property information from local HTML files (Idealista-like format)
"""

from bs4 import BeautifulSoup
import json
import sys
import uuid
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict


@dataclass
class PropertyData:
    """Data class to hold property extracted information."""

    id: Optional[str] = None
    price: Optional[int] = None
    property_type: Optional[str] = None  # 'apartment' or 'house'
    property_subtype: Optional[str] = None  # 'flat', 'duplex', 'penthouse', etc.
    street: Optional[str] = None
    neighborhood: Optional[str] = None
    district: Optional[str] = None
    surface: Optional[int] = None  # m2
    rooms: Optional[int] = None
    bathrooms: Optional[int] = None
    description: Optional[str] = None
    floor: Optional[str] = None  # can be None if it is a house
    is_exterior: Optional[bool] = None  # only for apartments
    has_elevator: Optional[bool] = None
    images: List[str] = None

    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.images is None:
            self.images = []

    def to_dict(self) -> Dict:
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
        self.soup: Optional[BeautifulSoup] = None
        self._load_html()

    def _load_html(self) -> None:
        if not self.html_path.exists():
            raise FileNotFoundError(f"File not found: {self.html_path}")

        with open(self.html_path, "r", encoding="utf-8") as file:
            html_content = file.read()

        self.soup = BeautifulSoup(html_content, "html.parser")

    def extract(self) -> PropertyData:
        if not self.soup:
            raise ValueError("HTML not loaded")

        property_type, property_subtype = self._extract_property_type_and_subtype()

        return PropertyData(
            price=self._extract_price(),
            property_type=property_type,
            property_subtype=property_subtype,
            street=self._extract_street(),
            neighborhood=self._extract_neighborhood(),
            district=self._extract_district(),
            surface=self._extract_surface(),
            rooms=self._extract_rooms(),
            bathrooms=self._extract_bathrooms(),
            description=self._extract_description(),
            floor=self._extract_floor(property_type),
            is_exterior=self._extract_is_exterior(property_type),
            has_elevator=self._extract_has_elevator(),
            images=self._extract_images(),
        )

    def _extract_title(self) -> Optional[str]:
        title_container = self.soup.select_one(".main-info__title")
        if not title_container:
            return None

        main_title = title_container.select_one(".main-info__title-main")
        minor_title = title_container.select_one(".main-info__title-minor")

        parts = []
        if main_title:
            parts.append(main_title.get_text(strip=True))
        if minor_title:
            parts.append(minor_title.get_text(strip=True))

        return ", ".join(parts) if parts else None

    def _extract_price(self) -> Optional[int]:
        price_element = self.soup.select_one(".info-data .info-data-price")
        price_text = None
        
        if price_element:
            price_text = price_element.get_text(" ", strip=True)
        else:
            price_container = self.soup.select_one(".info-data")
            if price_container:
                price_text = price_container.get_text(" ", strip=True)

        if not price_text:
            return None

        price_text = price_text.replace("€", "").replace(" ", "").replace(".", "").strip()
        
        price_digits = "".join(filter(str.isdigit, price_text))
        
        if price_digits:
            return int(price_digits)
        
        return None

    def _extract_property_type_and_subtype(self) -> Tuple[Optional[str], Optional[str]]:
        candidates = []

        typology = self.soup.select_one(".typology")
        if typology:
            candidates.append(typology.get_text(" ", strip=True))

        title = self._extract_title()
        if title:
            candidates.append(title)

        page_title = self.soup.find("title")
        if page_title:
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

    def _extract_location_parts(self) -> List[str]:
        header_map = self.soup.select_one("#headerMap")
        if not header_map:
            return []

        list_items = header_map.select("li.header-map-list")
        parts = []

        for item in list_items:
            text = item.get_text(" ", strip=True)
            if text:
                parts.append(text)

        return parts

    def _extract_street(self) -> Optional[str]:
        parts = self._extract_location_parts()
        return parts[0] if len(parts) > 0 else None

    def _extract_neighborhood(self) -> Optional[str]:
        parts = self._extract_location_parts()
        if len(parts) > 1:
            neighborhood = parts[1]
            # Remove "Barrio " prefix if present
            if neighborhood.startswith("Barrio "):
                neighborhood = neighborhood[7:]  # Remove "Barrio " (7 characters)
            return neighborhood
        return None

    def _extract_district(self) -> Optional[str]:
        parts = self._extract_location_parts()
        if len(parts) > 2:
            district = parts[2]
            # Remove "Distrito " prefix if present
            if district.startswith("Distrito "):
                district = district[9:]  # Remove "Distrito " (9 characters)
            return district
        return None

    def _extract_feature_texts(self) -> List[str]:
        selectors = [
            ".info-features span",
            ".details-property-features li",
            ".details-property-feature-one li",
            ".details-property-feature-two li",
            ".details-property_features li",
        ]

        features = []

        for selector in selectors:
            elements = self.soup.select(selector)
            for el in elements:
                text = el.get_text(" ", strip=True)
                if text and text not in features:
                    features.append(text)

        if features:
            return features

        container = self.soup.select_one(".info-features")
        if container:
            text = container.get_text(" ", strip=True)
            if text:
                return [text]

        return []

    def _extract_surface(self) -> Optional[int]:
        for text in self._extract_feature_texts():
            match = re.search(r"(\d+(?:[.,]\d+)?)\s*m²", text.lower())
            if match:
                surface_str = match.group(1).replace(",", ".")
                return int(float(surface_str))

        return None

    def _extract_rooms(self) -> Optional[int]:
        for text in self._extract_feature_texts():
            match = re.search(r"(\d+)\s*hab", text.lower())
            if match:
                return int(match.group(1))

            match = re.search(r"(\d+)\s*habitacion", text.lower())
            if match:
                return int(match.group(1))

        return None

    def _extract_bathrooms(self) -> Optional[int]:
        for text in self._extract_feature_texts():
            match = re.search(r"(\d+)\s*bañ", text.lower())
            if match:
                return int(match.group(1))

        return None

    def _extract_floor(self, property_type: Optional[str]) -> Optional[str]:
        if property_type == "house":
            return None

        for text in self._extract_feature_texts():
            text_lower = text.lower()

            if "planta" in text_lower:
                if "bajo" in text_lower:
                    return "bajo"
                if "entreplanta" in text_lower:
                    return "entreplanta"
                match = re.search(r"planta\s+([^\s,]+)", text_lower)
                if match:
                    return match.group(1)

            if "bajo" == text_lower.strip():
                return "bajo"

        return None

    def _extract_is_exterior(self, property_type: Optional[str]) -> Optional[bool]:
        if property_type != "apartment":
            return None

        for text in self._extract_feature_texts():
            text_lower = text.lower()

            if "interior" in text_lower:
                return False
            if "exterior" in text_lower:
                return True

        return None

    def _extract_has_elevator(self) -> Optional[bool]:
        for text in self._extract_feature_texts():
            text_lower = text.lower()

            if "sin ascensor" in text_lower:
                return False
            if "con ascensor" in text_lower:
                return True
            if "ascensor" in text_lower:
                return True

        return None

    def _extract_description(self) -> Optional[str]:
        comment_element = self.soup.select_one(".comment")
        if not comment_element:
            return None

        paragraphs = comment_element.find_all("p")
        if paragraphs:
            text_parts = [p.get_text(" ", strip=True) for p in paragraphs]
            return "\n\n".join(text_parts)

        return comment_element.get_text(" ", strip=True)

    def _extract_images(self) -> List[str]:
        urls = set()
        page_content = str(self.soup)

        webp_pattern = r'imageDataServiceWebp["\s:]+([^"]+\.webp)'
        matches = re.findall(webp_pattern, page_content)

        for url in matches:
            if self._is_valid_image_url(url):
                urls.add(url)

        multimedia_section = self.soup.select_one("#main-multimedia")
        if multimedia_section:
            images = multimedia_section.find_all("img")
            for img in images:
                url = self._get_image_url(img)
                if url and self._is_valid_image_url(url):
                    urls.add(url)

        main_images = self.soup.select(".main-image img")
        for img in main_images:
            url = self._get_image_url(img)
            if url and self._is_valid_image_url(url):
                urls.add(url)

        sources = self.soup.find_all("source")
        for source in sources:
            srcset = source.get("srcset")
            if srcset:
                url = srcset.split()[0] if " " in srcset else srcset
                if url and self._is_valid_image_url(url):
                    urls.add(url)

        return sorted(urls)

    @staticmethod
    def _is_valid_image_url(url: str) -> bool:
        if not url or url.startswith("data:"):
            return False

        if not url.lower().endswith(".webp"):
            return False

        required_pattern = (
            "https://img4.idealista.com/blur/WEB_DETAIL/0/id.pro.es.image.master/"
        )
        return url.startswith(required_pattern)

    @staticmethod
    def _get_image_url(img_tag) -> Optional[str]:
        return (
            img_tag.get("src")
            or img_tag.get("data-src")
            or img_tag.get("data-lazy-src")
            or img_tag.get("data-original")
        )


class BatchExtractor:
    """Batch extractor for processing multiple HTML files."""

    def __init__(
        self,
        source_dir: str = "source_html",
        output_file: str = "parsed_properties.json",
    ):
        self.source_dir = Path(source_dir)
        self.output_file = Path(output_file)
        self.results: List[Dict] = []
        self.errors: List[Dict] = []

    def find_html_files(self) -> List[Path]:
        if not self.source_dir.exists():
            raise FileNotFoundError(f"Source directory not found: {self.source_dir}")

        html_files = list(self.source_dir.rglob("*.html"))
        return sorted(html_files)

    def process_file(self, html_file: Path) -> Optional[Dict]:
        try:
            extractor = PropertyExtractor(str(html_file))
            data = extractor.extract()

            result = data.to_dict()
            result["source_file"] = str(html_file.relative_to(self.source_dir))
            return result

        except Exception as e:
            error_info = {
                "file": str(html_file.relative_to(self.source_dir)),
                "error": str(e),
                "error_type": type(e).__name__,
            }
            self.errors.append(error_info)
            return None

    def process_all(self, verbose: bool = True) -> Dict:
        html_files = self.find_html_files()

        if verbose:
            print(f"Found {len(html_files)} HTML files in {self.source_dir}")
            print("=" * 60)

        self.results = []
        self.errors = []

        for i, html_file in enumerate(html_files, 1):
            if verbose:
                print(f"[{i}/{len(html_files)}] Processing: {html_file.name}...", end=" ")

            result = self.process_file(html_file)

            if result:
                self.results.append(result)
                if verbose:
                    print("[OK]")
            else:
                if verbose:
                    print("[ERROR]")

        if verbose:
            print("=" * 60)
            print(f"Completed: {len(self.results)} successful, {len(self.errors)} errors")

        return {
            "total_files": len(html_files),
            "successful": len(self.results),
            "errors": len(self.errors),
        }

    def save_results(self, verbose: bool = True) -> None:
        output_data = {
            "properties": self.results,
            "metadata": {
                "total_properties": len(self.results),
                "extraction_errors": len(self.errors),
                "errors": self.errors,
            },
        }

        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        if verbose:
            print(f"\n[SUCCESS] Results saved to: {self.output_file}")
            print(f"  - {len(self.results)} properties extracted")
            if self.errors:
                print(f"  - {len(self.errors)} errors (see metadata.errors in JSON)")

    def run(self, verbose: bool = True) -> None:
        try:
            self.process_all(verbose=verbose)
            self.save_results(verbose=verbose)
        except Exception as e:
            print(f"Fatal error: {e}")
            raise


class PropertyFormatter:
    """Formats property data for output."""

    @staticmethod
    def pretty_print(data: PropertyData) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append("PROPERTY DATA EXTRACTION")
        lines.append("=" * 60)

        lines.append(f"\nID: {data.id}")
        lines.append(f"Price: {data.price}")
        lines.append(f"Property Type: {data.property_type}")
        lines.append(f"Property Subtype: {data.property_subtype}")
        lines.append(f"Street: {data.street}")
        lines.append(f"Neighborhood: {data.neighborhood}")
        lines.append(f"District: {data.district}")
        lines.append(f"Surface: {data.surface}")
        lines.append(f"Rooms: {data.rooms}")
        lines.append(f"Bathrooms: {data.bathrooms}")
        lines.append(f"Floor: {data.floor}")
        lines.append(f"Is Exterior: {data.is_exterior}")
        lines.append(f"Has Elevator: {data.has_elevator}")

        lines.append("\nDescription:")
        lines.append(f"  {data.description}")

        lines.append(f"\nImages ({len(data.images)}):")
        for i, url in enumerate(data.images, 1):
            lines.append(f"  {i}. {url}")

        lines.append("=" * 60)
        return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract property data from Idealista HTML files"
    )
    parser.add_argument(
        "path", nargs="?", help="Path to HTML file or directory (for batch mode)"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--batch", action="store_true", help="Batch process all HTML files in directory"
    )
    parser.add_argument(
        "--source-dir",
        default="source_html",
        help="Source directory for batch mode (default: source_html)",
    )
    parser.add_argument(
        "--output",
        default="parsed_properties.json",
        help="Output file for batch mode (default: parsed_properties.json)",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress progress messages in batch mode"
    )

    args = parser.parse_args()

    if args.batch:
        try:
            batch = BatchExtractor(source_dir=args.source_dir, output_file=args.output)
            batch.run(verbose=not args.quiet)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error during batch processing: {e}")
            sys.exit(1)
        return

    if not args.path:
        parser.print_help()
        sys.exit(1)

    try:
        extractor = PropertyExtractor(args.path)
        data = extractor.extract()

        if args.json:
            print(data.to_json())
        else:
            print(PropertyFormatter.pretty_print(data))

    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error extracting data: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()