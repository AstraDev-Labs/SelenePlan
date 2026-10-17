# Academic and Scientific References

This document records the foundational academic literature, instrument descriptions, planetary ephemeris frameworks, and cartographic standards upon which SelenePlan is constructed.

---

## 1. Lunar Instruments & Digital Elevation Topography

1. **Smith, D. E., Zuber, M. T., Neumann, G. A., et al. (2010).**
   *"The Lunar Orbiter Laser Altimeter Investigation on the Lunar Reconnaissance Orbiter Mission."*
   *Space Science Reviews*, 150(1–4), pp. 209–241.
   DOI: [10.1007/s11214-009-9512-y](https://doi.org/10.1007/s11214-009-9512-y).
   *Relevance:* Source for LOLA South Polar gridded DEMs (LDEM) and altimetry measurement accuracy.

2. **Robinson, M. S., Brylow, S. M., Tschimmel, M., et al. (2010).**
   *"Lunar Reconnaissance Orbiter Camera (LROC) Instrument Overview."*
   *Space Science Reviews*, 150(1–4), pp. 81–124.
   DOI: [10.1007/s11214-010-9634-2](https://doi.org/10.1007/s11214-010-9634-2).
   *Relevance:* High-resolution Narrow Angle Camera (NAC) orthoimagery used for crater detection ML and landing hazard identification.

3. **Archinal, B. A., Acton, C. H., A'Hearn, M. F., et al. (2018).**
   *"Report of the IAU/IAG Working Group on Cartographic Coordinates and Rotational Elements: 2015."*
   *Celestial Mechanics and Dynamical Astronomy*, 130(3), 22.
   DOI: [10.1007/s10569-017-9805-5](https://doi.org/10.1007/s10569-017-9805-5).
   *Relevance:* Foundation for the Mean Earth / Polar Axis (ME) reference frame, IAU2000 Moon reference sphere ($R = 1,737.4\text{ km}$), and planetocentric latitude definitions.

---

## 2. Ephemeris & Geodesy Toolkits

4. **Acton, C. H. (1996).**
   *"Ancillary data services of NASA's Navigation and Ancillary Information Facility."*
   *Planetary and Space Science*, 44(1), pp. 65–70.
   DOI: [10.1016/0032-0633(95)00107-7](https://doi.org/10.1016/0032-0633(95)00107-7).
   *Relevance:* NAIF SPICE toolkit and planetary kernels (`de430.bsp`, `naif0012.tls`, `moon_pa_de421_1900-2050.bpc`) for astronomical Sun and Earth vector computations.

5. **Annex, A., Pearson, B., Seignovert, B., et al. (2020).**
   *"SpiceyPy: a Pythonic Wrapper for the SPICE Toolkit."*
   *Journal of Open Source Software*, 5(46), 2050.
   DOI: [10.21105/joss.02050](https://doi.org/10.21105/joss.02050).
   *Relevance:* Python bindings used in `selene-geo` and `illumination-service`.

---

## 3. Polar Illumination, Shadow, and Earth Communication Visibility

6. **Mazarico, E., Neumann, G. A., Smith, D. E., Zuber, M. T., & Torrence, M. H. (2011).**
   *"Illumination conditions of the lunar polar regions using LOLA topography."*
   *Icarus*, 211(2), pp. 1066–1081.
   DOI: [10.1016/j.icarus.2010.10.030](https://doi.org/10.1016/j.icarus.2010.10.030).
   *Relevance:* Horizon-mask algorithm, lunar grazing angles, and golden baseline values for Shackleton and connecting ridges.

7. **Gläser, P., Scholten, F., De Rosa, D., et al. (2018).**
   *"Illumination conditions at the lunar south pole using high resolution LRO LOLA and SELENE TC topography."*
   *Planetary and Space Science*, 162, pp. 170–178.
   DOI: [10.1016/j.pss.2017.07.006](https://doi.org/10.1016/j.pss.2017.07.006).
   *Relevance:* Azimuthal horizon profile validation and sub-pixel penumbra discretization.

8. **Speyerer, E. J., & Robinson, M. S. (2013).**
   *"Persistently illuminated regions at the lunar poles: Ideal sites for future exploration."*
   *Icarus*, 222(1), pp. 122–136.
   DOI: [10.1016/j.icarus.2012.10.010](https://doi.org/10.1016/j.icarus.2012.10.010).
   *Relevance:* Quantitative identification of connecting ridges and Malapert Mountain candidate sites.

9. **De Rosa, D., Bussey, B., Cahill, J. T., et al. (2012).**
   *"Characterisation of the lunar search space for future landing sites using LOLA data."*
   *Planetary and Space Science*, 74(1), pp. 224–246.
   DOI: [10.1016/j.pss.2012.08.012](https://doi.org/10.1016/j.pss.2012.08.012).
   *Relevance:* Landing ellipse safety evaluation combining slope, roughness, and Earth visibility.

---

## 4. Lunar Impact Craters & Morphometry

10. **Robbins, S. J. (2019).**
    *"A new global database of lunar impact craters $>1-2\text{ km}$."*
    *Journal of Geophysical Research: Planets*, 124(4), pp. 871–892.
    DOI: [10.1029/2018JE005592](https://doi.org/10.1029/2018JE005592).
    *Relevance:* Crater boundary labels and morphometry ground truth for hazard ML evaluation.

---

## 5. Optimization, Canonical Data Structures & Cryptography

11. **Rundgren, A., Jordan, P., & Erdtman, S. (2020).**
    *"JSON Canonicalization Scheme (JCS)."*
    *RFC 8785*, Internet Engineering Task Force (IETF).
    DOI: [10.17487/RFC8785](https://www.rfc-editor.org/info/rfc8785).
    *Relevance:* Specification for deterministic, byte-exact serialization of plan JSON payloads prior to hashing and digital signing.

12. **Bernstein, D. J., Duif, N., Lange, T., Schwabe, P., & Yang, B. Y. (2012).**
    *"High-speed high-security signatures."*
    *Journal of Cryptographic Engineering*, 2(2), pp. 77–89.
    DOI: [10.1007/s13389-012-0027-1](https://doi.org/10.1007/s13389-012-0027-1).
    *Relevance:* Curve25519 / Ed25519 digital signature algorithm implemented via HashiCorp Vault Transit engine.

13. **Kochenderfer, M. J., & Wheeler, T. A. (2019).**
    *"Algorithms for Optimization."*
    *MIT Press*, Cambridge, MA.
    *Relevance:* Formulation of multi-objective optimization, soft scoring Pareto surfaces, and admissible heuristics in time-expanded graph search.
