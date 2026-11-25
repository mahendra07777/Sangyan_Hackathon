# Sample Document Preparation & Ingestion Guide

> **SANGYAN 2026 — IIT BHU | Bharat Investor Copilot**  
> **Core Principle:** **UNDERSTANDING BEFORE ACTION**

This guide instructs evaluators and researchers on how to obtain, prepare, and upload public corporate financial disclosures for testing the **Compare Documents** feature.

---

## 1. Notice Regarding Bundled Sample Documents

To respect intellectual property rights and distribution terms of corporate issuers, **actual third-party corporate annual reports are not pre-packaged or redistributed in this repository**.

Instead, evaluators can easily download public annual reports or quarterly filings directly from official exchange and corporate sources as detailed below.

---

## 2. Recommended Official Sources for Public Filings

When selecting financial documents for evaluation, download genuine, publicly available statutory disclosures from official repositories:

1. **BSE India (Bombay Stock Exchange):**
   - URL: `https://www.bseindia.com/`
   - Path: Navigate to *Corporates ➔ Corporate Filings ➔ Financial Results / Annual Reports*.
   - Filter by Company Name or Scrip Code.
2. **NSE India (National Stock Exchange):**
   - URL: `https://www.nseindia.com/`
   - Path: Navigate to *Companies ➔ Corporate Disclosures ➔ Annual Reports*.
3. **Official Corporate Investor Relations Portals:**
   - Examples of public investor portals:
     - Tata Motors Limited: `https://www.tatamotors.com/investors/`
     - Maruti Suzuki India Limited: `https://www.marutisuzuki.com/corporate/investors`
     - Infosys Limited: `https://www.infosys.com/investors.html`
     - Tata Consultancy Services (TCS): `https://www.tcs.com/investor-relations`

---

## 3. Selecting Comparable Documents

To observe optimal comparison accuracy and avoid compatibility warnings:

### A. Choose Peer Companies or Multi-Year Comparisons
- **Peer Comparison (Recommended for Competition Demo):**
  - Download two peer filings from the same industry and fiscal period.
  - *Example:* **Tata Motors Limited (Annual Report FY 2023-24)** vs **Maruti Suzuki India Limited (Annual Report FY 2023-24)**.
- **Temporal Trend Comparison:**
  - Download two consecutive fiscal years of the same company.
  - *Example:* **Infosys Limited FY 2023-24** vs **Infosys Limited FY 2022-23**.

### B. Verification & Alignment Criteria
Before uploading, verify the following parameters to ensure fair comparison:
1. **Reporting Period:** Both disclosures should cover the same duration (e.g., full 12-month fiscal year, or matching 3-month quarterly reporting).
2. **Reporting Currency:** Ensure both filings report in Indian Rupees (`INR` / `₹`). The system flags cross-currency comparisons as a warning.
3. **Accounting Scope:** Match **Consolidated** with **Consolidated** statements (or Standalone with Standalone). Comparing Consolidated to Standalone figures will trigger an explanatory compatibility warning.
4. **Financial Scale:** Indian corporate statements typically report in `₹ Crores` or `₹ Lakhs`. While the platform automatically detects and normalizes scales, selecting matching scales simplifies manual verification.
5. **Text Layer Quality:** Ensure the downloaded PDF has a selectable digital text layer. Scanned, image-only PDFs lacking embedded text cannot be parsed without local OCR tools.

---

## 4. Staging Files in This Directory

1. Download the chosen public annual reports (in `.pdf`, `.xlsx`, `.csv`, `.docx`, or `.txt` format).
2. Place the downloaded files directly into this directory:
   ```
   sample_documents/
   ├── <CompanyA_Annual_Report_FY24>.pdf
   └── <CompanyB_Annual_Report_FY24>.pdf
   ```
3. *(Optional)* Confirm file sizes meet platform boundaries:
   - Each file must be $\le 20\text{ MiB}$.
   - Aggregate session size must be $\le 100\text{ MiB}$.

---

## 5. Ingestion & Comparison via the Application

1. **Start the Application:**
   ```powershell
   # Start backend (Terminal 1)
   cd backend
   python main.py

   # Start frontend (Terminal 2)
   cd app
   npm run dev
   ```
2. **Access the Interface:**
   - Open your browser at `http://localhost:5173/`.
   - Click **"Compare Documents"** from the navigation bar.
3. **Upload Files:**
   - Drag and drop 2 to 5 files from your `sample_documents/` folder into the dropzone (or click "Browse files").
   - Inspect the file validation indicators (file format badge, size indicator, total session size).
4. **Review Metadata:**
   - Click **"Continue to Metadata Review"**.
   - Verify detected company names, reporting periods, currency, and accounting standards.
   - Review any compatibility warnings or blockers identified by the engine.
5. **Analyze Financials:**
   - Click **"Run Comparison"** to enter the Comparison Dashboard.
   - Inspect the 9 core financial cards, change baseline selections, review directional variances, and click any number to view primary source evidence.
