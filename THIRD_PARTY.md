# Third-Party Licenses and Dataset Usage Notice

This document details the licensing terms for third-party software libraries, tools, and planetary datasets utilized within SelenePlan v1.0.0.

---

## 1. Core Python Dependencies

| Package | Version Range | License | Project URL / Source |
| :--- | :--- | :--- | :--- |
| **FastAPI** | `^0.115` | MIT | [tiangolo/fastapi](https://github.com/tiangolo/fastapi) |
| **Pydantic** | `^2.9` | MIT | [pydantic/pydantic](https://github.com/pydantic/pydantic) |
| **SQLAlchemy** | `^2.0` | MIT | [sqlalchemy/sqlalchemy](https://github.com/sqlalchemy/sqlalchemy) |
| **Alembic** | `^1.13` | MIT | [sqlalchemy/alembic](https://github.com/sqlalchemy/alembic) |
| **NumPy** | `^1.26 / ^2.0` | BSD-3-Clause | [numpy/numpy](https://github.com/numpy/numpy) |
| **SciPy** | `^1.14` | BSD-3-Clause | [scipy/scipy](https://github.com/scipy/scipy) |
| **Rasterio** | `^1.3` | BSD-3-Clause | [rasterio/rasterio](https://github.com/rasterio/rasterio) |
| **Zarr** | `^3.0` | MIT | [zarr-developers/zarr-python](https://github.com/zarr-developers/zarr-python) |
| **SpiceyPy** | `^6.0` | MIT | [SpiceyPy/SpiceyPy](https://github.com/SpiceyPy/SpiceyPy) |
| **NetworkX** | `^3.3` | BSD-3-Clause | [networkx/networkx](https://github.com/networkx/networkx) |
| **Cryptography** | `^43.0` | Apache-2.0 / BSD-3 | [pyca/cryptography](https://github.com/pyca/cryptography) |
| **PyJWT** | `^2.9` | MIT | [jpadilla/pyjwt](https://github.com/jpadilla/pyjwt) |
| **WeasyPrint** | `^62.0` | BSD-3-Clause | [Kozea/WeasyPrint](https://github.com/Kozea/WeasyPrint) |
| **Jinja2** | `^3.1` | BSD-3-Clause | [pallets/jinja](https://github.com/pallets/jinja) |
| **ONNX Runtime** | `^1.19` | MIT | [microsoft/onnxruntime](https://github.com/microsoft/onnxruntime) |
| **OpenCV Python** | `^4.10` | Apache-2.0 | [opencv/opencv-python](https://github.com/opencv/opencv-python) |
| **Pytest** | `^8.0` | MIT | [pytest-dev/pytest](https://github.com/pytest-dev/pytest) |
| **Ruff** | `^0.6` | MIT / Apache-2.0 | [astral-sh/ruff](https://github.com/astral-sh/ruff) |

---

## 2. Frontend Web Dependencies

| Package | Version Range | License | Project URL / Source |
| :--- | :--- | :--- | :--- |
| **React** | `^18.3` | MIT | [facebook/react](https://github.com/facebook/react) |
| **React DOM** | `^18.3` | MIT | [facebook/react](https://github.com/facebook/react) |
| **Vite** | `^5.4` | MIT | [vitejs/vite](https://github.com/vitejs/vite) |
| **Vitest** | `^1.6` | MIT | [vitest-dev/vitest](https://github.com/vitest-dev/vitest) |
| **Lucide React** | `^0.446` | ISC | [lucide-icons/lucide](https://github.com/lucide-icons/lucide) |
| **TailwindCSS** | `^3.4` | MIT | [tailwindlabs/tailwindcss](https://github.com/tailwindlabs/tailwindcss) |
| **Axe Core** | `^4.9` | MPL-2.0 | [dequelabs/axe-core](https://github.com/dequelabs/axe-core) |

---

## 3. Planetary Science Datasets & Ephemerides

| Dataset / Product | Originator / Agency | Terms of Use / License | Notes |
| :--- | :--- | :--- | :--- |
| **LRO LOLA Polar DEMs** | NASA / Goddard Space Flight Center / PDS | Public Domain (NASA Open Data) | Free for scientific, commercial, and educational reuse with attribution. |
| **LRO LROC NAC Orthoimagery** | NASA / Arizona State University / PDS | Public Domain (NASA Open Data) | Free for scientific, commercial, and educational reuse with attribution. |
| **NAIF SPICE Kernels** | NASA JPL / NAIF | Public Domain (NASA Open Data) | Planetary ephemeris kernels free for mission design and navigation use. |
| **ISRO Chandrayaan Products** | ISRO PRADAN | Data Policy / Restricted | Evaluated during onboarding; ingested solely when terms permit redistribution. |
