# Executive Meeting Directives & Technical Task Log (August 20, 2026)

> **Location**: `script/cyclone/MEETING_DIRECTIVES_AUGUST_20.md`  
> **Project**: ASR Parametric Cyclone Risk Study  
> **Key Focus**: Historical Record Extension (1980–2026), Holland vs. ERA5 ML Regression Metrics, & Simplified Agro/Non-Agro Multi-Threshold Annual Aggregation  

---

## 📌 Summary of Approved Tasks from August 20 Meeting

### Task 1: Historical Record Extension (1980 - 2026)
- Extend the cyclone track analysis from the earliest available NOAA IBTrACS v4 best-track archive year (**1980 to 2026**).
- Significantly expands the spatial location/district coverage and historical sample size of tropical cyclones in the South Indian Ocean (SWIO) and North Indian Ocean (Somalia).

---

### Task 2: Holland (1980) vs. ERA5 Reanalysis Regression Comparison
- Perform a quantitative Machine Learning (ML) regression comparison between Holland (1980) modeled local wind speed ($V_{\text{Holland}}$) and ERA5 10m wind speed ($V_{\text{ERA5}}$) across district centroids.
- Compute key regression metrics per the reference framework ([Codepointtech Regression Metrics Guide](https://codepointtech.com/mastering-regression-metrics-r%c2%b2-mse-mae-explained-2/)):
  1. **$R^2$ (Coefficient of Determination)**: $R^2 = 1 - \frac{\sum (y_i - \hat{y}_i)^2}{\sum (y_i - \bar{y})^2}$
  2. **MSE (Mean Squared Error)**: $\text{MSE} = \frac{1}{N} \sum (y_i - \hat{y}_i)^2$
  3. **RMSE (Root Mean Squared Error)**: $\text{RMSE} = \sqrt{\text{MSE}}$
  4. **MAE (Mean Absolute Error)**: $\text{MAE} = \frac{1}{N} \sum |y_i - \hat{y}_i|$
- **Underwriting Takeaway**: Quantifies why ERA5 underestimates local peak extreme winds due to spatial grid smoothing ($31\text{ km}$ resolution), reinforcing the use of Holland (1980) best-track radial decay.

---

### Task 3: Simplified Agro and Non-Agro Yearly Aggregations
- **Simplified Agro Location Definition**:
  - A location/district is an **Agro Location** if:
    1. It is classified as risky (experienced $V_{\text{local}} > 64\text{ km/h} \ [34\text{ kt}]$ at least once in the 1980–2026 historical record).
    2. It has an active crop calendar with valid planting and harvesting dates (`planting_d` to `harvest_do`).
    3. *(Note: The 95% cumulative area filter is removed per meeting directives to keep the model simple).*
  - **Agro Cyclone Definition**:
    - A cyclone event is counted as an **Agro Cyclone** ONLY if its occurrence date falls **during the active crop calendar season** (`planting_d` to `harvest_do`).
- **Non-Agro Location Definition**:
  - Non-Agro (Property & Infrastructure) exposures are evaluated across the **entire calendar year (all 365 days)**.

---

### Task 4: Multi-Threshold Risk Aggregation
- Evaluate annual aggregations across multiple wind speed thresholds:
  - **$34\text{ kt} \ (63\text{ km/h})$** $\rightarrow$ **(Recommended for Agricultural Crop Lodging)**
  - **$50\text{ kt} \ (93\text{ km/h})$** $\rightarrow$ Moderate Severe Storm
  - **$64\text{ kt} \ (119\text{ km/h})$** $\rightarrow$ **(Recommended for Property & Infrastructure Structural Loss)**
