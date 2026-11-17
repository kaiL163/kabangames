# Automotive emblem sources

The downloaded images are stored locally with opaque filenames. The catalog uses real automotive marks, including historical marques. Brand names and marks belong to their respective owners.

Source and attribution details for the added files are in `sources.json`:

- https://github.com/filippofilip95/car-logos-dataset — automotive logo catalog; individual original source URLs are retained.
- https://commons.wikimedia.org/wiki/Category:SVG_logos_of_car_symbols — standalone symbols. Per-file author/license metadata is preserved in the manifest.
- https://github.com/simple-icons/simple-icons — CC0 standalone Dacia, Acura, Infiniti, Mazda symbols.

The original downloads are not repainted. When a source includes a detached caption, the quiz shows only the graphic through an SVG viewport. The full original remains available after the round. `backend/car_puzzles.json` records the reviewed regions and any dedicated symbol asset. Quiz masks are applied after selecting the clean symbol.
