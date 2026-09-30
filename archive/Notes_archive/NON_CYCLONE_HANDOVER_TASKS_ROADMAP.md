# Non-Cyclone Handover Tasks & Technical Roadmap

> **Document Name**: `NON_CYCLONE_HANDOVER_TASKS_ROADMAP.md`  
> **Location**: `Africa-Cyclone-Study/Notes/NON_CYCLONE_HANDOVER_TASKS_ROADMAP.md`  
> **Project**: ASR Multi-Peril Parametric Research Study (Handover & Governance)  
> **Created**: September 2026  
> **Target Handover Date**: September 9th, 2026  

---

## 📌 Executive Overview

Per the September 2026 Leadership Meeting review, this document isolates and tracks all non-cyclone handover tasks and operational requirements across the **Flood** and **Drought** parametric research studies. All cyclone-specific technical models and documentation are managed independently in the `Africa-Cyclone-Study/` module.

---

## 🌊 1. Parametric Flood Study Handover Tasks

### Objective
Provide comprehensive, self-contained documentation and validation metrics for the **Copernicus Global Land Service Soil Water Index (SWI V3)** parametric flood model.

### Key Deliverables & Specifications:
1. **Technical Methodology Document (`FLOOD_PARAMETRIC_METHODOLOGY_GUIDE.md`)**:
   - **Satellite Data**: Copernicus Global Land Service SWI V3 (1 km daily resolution, derived from Metop ASCAT backscatter).
   - **Dual Soil Layer Penetration**:
     - Topsoil layer ($T=10$ / $Q=10$, superficial surface moisture $0-5\text{ cm}$).
     - Root-zone depth ($T=40$ / $Q=40$, deeper soil moisture $0-100\text{ cm}$).
   - **Trigger Formulation**:
     - Consecutive 5-day continuous streak threshold ($\text{SWI} \ge 85\%-90\%$).
     - Historical event calibration against Dartmouth Flood Observatory (DFO) and EM-DAT international disaster records.
   - **Agro Phenology Windows**: Restricting payout evaluation strictly to active crop emergence and vegetative periods (GEOGLAM / FAO crop calendars).
2. **README.md Creation**:
   - Location: `Africa-Flood-Study/README.md`
   - Content: Map of `data/`, `core_analysis/`, and `outputs/`; script execution pipeline; and explanation of interactive Plotly dashboards.

---

## 🌾 2. Parametric Drought Study Handover Tasks

### Objective
Restructure and reorganize the drought study repository, resolve redundant experimental files, and formalize the SPI / NDVI drought index methodology.

### Key Deliverables & Specifications:
1. **Repository Cleanup & Restructuring**:
   - Reorganize messy directories in `Africa-Drought-Study/`:
     - `data/`: Raw district boundary shapefiles and climate datasets.
     - `core_analysis/`: Production-ready Python analysis scripts.
     - `outputs/`: Consolidated metrics CSVs, static plots, and interactive HTML dashboards.
     - `docs/`: Methodology notes and execution guides.
     - `archive/`: Deprecated exploratory scratch scripts and temporary intermediate dumps.
2. **Technical Methodology Document (`DROUGHT_PARAMETRIC_METHODOLOGY_GUIDE.md`)**:
   - **Datasets**: UCSB CHIRPS high-resolution ($0.05^\circ$) daily precipitation and MODIS/Copernicus NDVI vegetation anomaly time series.
   - **Index Formulation**:
     - Standardized Precipitation Index (SPI-1, SPI-3) for meteorological drought.
     - Normalized Difference Vegetation Index (NDVI) anomaly / Vegetation Condition Index (VCI) for agricultural drought.
   - **Payout Function**: Stepwise / linear payout curve tied to historical crop yield losses.
3. **README.md Creation**:
   - Location: `Africa-Drought-Study/README.md`
   - Content: Step-by-step instructions for reproducing drought analyses across Africa.

---

## 📋 Action Items & Status Tracking

| Task ID | Component | Task Description | Priority | Status |
| :---: | :---: | :--- | :---: | :---: |
| **NC-01** | Flood | Draft `FLOOD_PARAMETRIC_METHODOLOGY_GUIDE.md` covering SWI V3 $T=10/T=40$ streak mechanics. | High | **QUEUED** |
| **NC-02** | Flood | Create standardized `Africa-Flood-Study/README.md` file. | Medium | **QUEUED** |
| **NC-03** | Drought | Restructure `Africa-Drought-Study/` folder hierarchy (`data/`, `core_analysis/`, `outputs/`, `docs/`, `archive/`). | High | **QUEUED** |
| **NC-04** | Drought | Draft `DROUGHT_PARAMETRIC_METHODOLOGY_GUIDE.md` covering CHIRPS SPI and NDVI Anomaly models. | High | **QUEUED** |
| **NC-05** | Drought | Create standardized `Africa-Drought-Study/README.md` file. | Medium | **QUEUED** |
| **NC-06** | General | Finalize root workspace `README.md` and synchronize all deliverables. | High | **QUEUED** |
