# Area of Interest (AOI) Specification

Specification recorded per Roadmap P-0 and Task 1.5.

## 1. Selected Area of Interest
- **Site Name:** Shackleton Crater Rim and Connecting Ridge
- **Region:** Lunar South Pole ($89.5^\circ\text{S}$ to $90.0^\circ\text{S}$)
- **Coordinate Reference System:** Lunar South Pole Stereographic (`IAU_2015:30100` / `PROJCS["Moon_South_Pole_Stereographic", ...]`)
- **Central Meridian:** $0.0^\circ$ (pointing toward Prime Meridian / Earth)
- **Bounding Box (Stereographic Metres):**
  - $X_{\min} = -10,000\text{ m}$, $X_{\max} = +10,000\text{ m}$ (East-West span: $20\text{ km}$)
  - $Y_{\min} = -10,000\text{ m}$, $Y_{\max} = +10,000\text{ m}$ (North-South span: $20\text{ km}$)
  - Nominal Area: $400\text{ km}^2$
- **Target Pixel Resolution:** $20.0\text{ m/pixel}$ ($1,000 \times 1,000$ cells)

## 2. Scientific Significance
1. **High Illumination Peaks:** The rims of Shackleton crater and the Connecting Ridge receive some of the highest cumulative solar illumination on the Moon ($> 80\%$ annual sunlight).
2. **Traversability Challenges:** High-slope crater walls ($> 25^\circ$) juxtaposed with traversable ridge crests ($< 12^\circ$).
3. **Permanently Shadowed Regions (PSRs):** Shackleton interior is permanently shadowed and suspected to harbor cold-trapped water ice.
4. **Earth Direct Line-of-Sight:** Near-continuous comms visibility with periodic occultations driven by lunar libration ($\approx \pm 6^\circ$ wobble).

## 3. Reference Data Sources
- **DEM:** LRO LOLA South Polar Gridded Data Record (PGDR), $20\text{ m/pixel}$ polar stereographic raster.
  - Source: NASA PDS Geosciences Node (`https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/`)
  - License: Public Domain (US Government work).
  - Terms: Open redistribution with standard NASA/LOLA attribution.
